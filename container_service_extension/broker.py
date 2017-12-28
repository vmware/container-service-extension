# SPDX-License-Identifier: BSD-2-Clause

import click

from container_service_extension.cluster import add_nodes
from container_service_extension.cluster import get_cluster_config
from container_service_extension.cluster import get_master_ip
from container_service_extension.cluster import init_cluster
from container_service_extension.cluster import join_cluster
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import TYPE_MASTER
from container_service_extension.cluster import TYPE_NODE

import logging

import pkg_resources

from pyvcloud.vcd.client import _WellKnownEndpoint
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC

import re
import requests
import threading
import traceback
import uuid
import yaml

LOGGER = logging.getLogger(__name__)

OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_SERVER_ERROR = 500

OP_CREATE_CLUSTER = 'create_cluster'
OP_DELETE_CLUSTER = 'delete_cluster'

OP_MESSAGE = {
    OP_CREATE_CLUSTER: 'create cluster',
    OP_DELETE_CLUSTER: 'delete cluster'
}

MAX_HOST_NAME_LENGTH = 25 - 4

SAMPLE_TEMPLATE_PHOTON_V1 = {
    'name':
    'photon-v1',
    'catalog_item':
    'photon-custom-hw11-1.0-62c543d-k8s',
    'source_ova_name':
    'photon-custom-hw11-1.0-62c543d.ova',
    'source_ova':
    'https://bintray.com/vmware/photon/download_file?file_path=photon-custom-hw11-1.0-62c543d.ova',  # NOQA
    'sha1_ova':
    '18c1a6d31545b757d897c61a0c3cc0e54d8aeeba',
    'temp_vapp':
    'photon1-temp',
    'cleanup':
    True,
    'cpu':
    2,
    'mem':
    2048,
    'admin_password':
    'guest_os_admin_password',
    'description':
    "PhotonOS v1\nDocker 17.06.0-1\nKubernetes 1.8.1\nweave 2.0.5"
}

SAMPLE_TEMPLATE_UBUNTU_16_04 = {
    'name':
    'ubuntu-16.04',
    'catalog_item':
    'ubuntu-16.04-server-cloudimg-amd64-k8s',
    'source_ova_name':
    'ubuntu-16.04-server-cloudimg-amd64.ova',
    'source_ova':
    'https://cloud-images.ubuntu.com/releases/xenial/release-20171011/ubuntu-16.04-server-cloudimg-amd64.ova',  # NOQA
    'sha1_ova':
    '1bddf68820c717e13c6d1acd800fb7b4d197b411',
    'temp_vapp':
    'ubuntu1604-temp',
    'cleanup':
    True,
    'cpu':
    2,
    'mem':
    2048,
    'admin_password':
    'guest_os_admin_password',
    'description':
    'Ubuntu 16.04\nDocker 17.09.0~ce\nKubernetes 1.8.2\nweave 2.0.5'
}

SAMPLE_CONFIG = {
    'broker': {
        'type': 'default',
        'org': 'Admin',
        'vdc': 'Catalog',
        'catalog': 'cse',
        'network': 'admin_network',
        'ip_allocation_mode': 'pool',
        'storage_profile': '*',
        'default_template': SAMPLE_TEMPLATE_PHOTON_V1['name'],
        'templates': [SAMPLE_TEMPLATE_PHOTON_V1, SAMPLE_TEMPLATE_UBUNTU_16_04],
        'cse_msg_dir': '/tmp/cse'
    }
}


def get_sample_broker_config(labels):
    return yaml.safe_dump(SAMPLE_CONFIG, default_flow_style=False)


def validate_broker_config_elements(config):
    for k, v in SAMPLE_CONFIG['broker'].items():
        if k not in config.keys():
            raise Exception('missing key: %s' % k)
    for k, v in config.items():
        if k not in SAMPLE_CONFIG['broker'].keys():
            raise Exception('invalid key: %s' % k)
    for template in config['templates']:
        for k, v in SAMPLE_TEMPLATE_PHOTON_V1.items():
            if k not in template.keys():
                raise Exception('missing key: %s' % k)
        for k, v in template.items():
            if k not in SAMPLE_TEMPLATE_PHOTON_V1.keys():
                raise Exception('invalid key: %s' % k)


def validate_broker_config_content(config, client, template):
    from container_service_extension.config import bool_to_msg
    logged_in_org = client.get_org()
    org = Org(client, resource=logged_in_org)
    org.get_catalog(config['broker']['catalog'])
    click.echo('Find catalog \'%s\': %s' % (config['broker']['catalog'],
                                            bool_to_msg(True)))
    default_template_found = False
    for t in config['broker']['templates']:
        if template == '*' or template == t['name']:
            click.secho('Validating template: %s' % t['name'])
            if config['broker']['default_template'] == t['name']:
                default_template_found = True
                click.secho('  Is default template: %s' % True)
            else:
                click.secho('  Is default template: %s' % False)
            org.get_catalog_item(config['broker']['catalog'],
                                 t['catalog_item'])
            click.echo('Find template \'%s\', \'%s\': %s' %
                       (config['broker']['catalog'], t['catalog_item'],
                        bool_to_msg(True)))

    assert default_template_found


def get_new_broker(config):
    if config['broker']['type'] == 'default':
        return DefaultBroker(config)
    else:
        return None


def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor


spinner = spinning_cursor()


def task_callback(task):
    message = '\x1b[2K\r{}: {}, status: {}'.format(
        task.get('operationName'), task.get('operation'), task.get('status'))
    if hasattr(task, 'Progress'):
        message += ', progress: %s%%' % task.Progress
    if task.get('status').lower() in [
            TaskStatus.QUEUED.value, TaskStatus.PENDING.value,
            TaskStatus.PRE_RUNNING.value, TaskStatus.RUNNING.value
    ]:
        message += ' %s ' % spinner.next()
    click.secho(message)


class DefaultBroker(threading.Thread):
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config
        self.host = config['vcd']['host']
        self.username = config['vcd']['username']
        self.password = config['vcd']['password']
        self.version = config['vcd']['api_version']
        self.verify = config['vcd']['verify']
        self.log = config['vcd']['log']

    def _connect_sysadmin(self):
        if not self.verify:
            LOGGER.warning('InsecureRequestWarning: '
                           'Unverified HTTPS request is being made. '
                           'Adding certificate verification is strongly '
                           'advised.')
            requests.packages.urllib3.disable_warnings()
        self.client_sysadmin = Client(
            uri=self.host,
            api_version=self.version,
            verify_ssl_certs=self.verify,
            log_file='sysadmin.log',
            log_headers=True,
            log_bodies=True)
        self.client_sysadmin.set_credentials(
            BasicLoginCredentials(self.username, 'System', self.password))

    def _connect_tenant(self, headers):
        token = headers.get('x-vcloud-authorization')
        accept_header = headers.get('Accept')
        version = accept_header.split('version=')[1]
        self.client_tenant = Client(
            uri=self.host,
            api_version=version,
            verify_ssl_certs=self.verify,
            log_file='tenant.log',
            log_headers=True,
            log_bodies=True)
        session = self.client_tenant.rehydrate_from_token(token)
        return {
            'user_name':
            session.get('user'),
            'user_id':
            session.get('userId'),
            'org_name':
            session.get('org'),
            'org_href':
            self.client_tenant._get_wk_endpoint(
                _WellKnownEndpoint.LOGGED_IN_ORG)
        }

    def update_task(self, status, operation, message=None, error_message=None):
        if not hasattr(self, 'task'):
            self.task = Task(self.client_sysadmin)
        if message is None:
            message = OP_MESSAGE[operation]
        if hasattr(self, 't'):
            task_href = self.t.get('href')
        else:
            task_href = None
        self.t = self.task.update(
            status.value,
            'vcloud.cse',
            message,
            operation,
            '',
            None,
            'urn:cse:cluster:%s' % self.cluster_id,
            self.cluster_name,
            'application/vcloud.cse.cluster+xml',
            self.tenant_info['user_id'],
            self.tenant_info['user_name'],
            org_href=self.tenant_info['org_href'],
            task_href=task_href,
            error_message=error_message)

    def is_valid_name(self, name):
        """Validates that the cluster name against the pattern.

        """
        if len(name) > MAX_HOST_NAME_LENGTH:
            return False
        if name[-1] == '.':
            name = name[:-1]
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in name.split("."))

    def get_template(self, name=None):
        if name is None:
            if 'template' in self.body and self.body['template'] is not None:
                name = self.body['template']
            else:
                name = self.config['broker']['default_template']
        for template in self.config['broker']['templates']:
            if template['name'] == name:
                return template
        raise Exception('Template %s not found' % name)

    def run(self):
        LOGGER.debug('thread started op=%s' % self.op)
        if self.op == OP_CREATE_CLUSTER:
            self.create_cluster_thread()
        elif self.op == OP_DELETE_CLUSTER:
            self.delete_cluster_thread()

    def list_clusters(self, headers, body):
        result = {}
        try:
            result['body'] = []
            result['status_code'] = OK
            self._connect_tenant(headers)
            clusters = load_from_metadata(
                self.client_tenant, get_leader_ip=True)
            result['body'] = clusters
        except Exception:
            LOGGER.error(traceback.format_exc())
            result['body'] = []
            result['status_code'] = INTERNAL_SERVER_ERROR
            result['message'] = traceback.format_exc()
        return result

    def create_cluster(self, headers, body):
        result = {}
        result['body'] = {}
        cluster_name = body['name']
        vdc_name = body['vdc']
        node_count = body['node_count']
        LOGGER.debug('about to create cluster %s on %s with %s nodes, sp=%s',
                     cluster_name, vdc_name, node_count,
                     body['storage_profile'])
        result['body'] = {'message': 'can\'t create cluster %s' % cluster_name}
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            if not self.is_valid_name(cluster_name):
                raise Exception('Invalid cluster name')
            self.tenant_info = self._connect_tenant(headers)
            self.headers = headers
            self.body = body
            self.cluster_name = cluster_name
            self.cluster_id = str(uuid.uuid4())
            self.op = OP_CREATE_CLUSTER
            self._connect_sysadmin()
            self.update_task(
                TaskStatus.RUNNING,
                self.op,
                message='Creating cluster %s(%s)' % (cluster_name,
                                                     self.cluster_id))
            self.daemon = True
            self.start()
            response_body = {}
            response_body['name'] = self.cluster_name
            response_body['cluster_id'] = self.cluster_id
            response_body['task_href'] = self.t.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = {'message': e.message}
            LOGGER.error(traceback.format_exc())
        return result

    def create_cluster_thread(self):
        network_name = self.body['network']
        try:
            clusters = load_from_metadata(
                self.client_tenant, name=self.cluster_name)
            if len(clusters) != 0:
                raise Exception('Cluster already exists.')
            org_resource = self.client_tenant.get_org()
            org = Org(self.client_tenant, resource=org_resource)
            vdc_resource = org.get_vdc(self.body['vdc'])
            vdc = VDC(self.client_tenant, resource=vdc_resource)
            template = self.get_template()
            self.update_task(
                TaskStatus.RUNNING,
                self.op,
                message='Creating cluster vApp %s(%s)' % (self.cluster_name,
                                                          self.cluster_id))
            vapp_resource = vdc.create_vapp(
                self.cluster_name,
                description='cluster %s' % self.cluster_name,
                network=network_name,
                fence_mode='bridged')
            t = self.client_tenant.get_task_monitor().wait_for_status(
                task=vapp_resource.Tasks.Task[0],
                timeout=60,
                poll_frequency=2,
                fail_on_status=None,
                expected_target_statuses=[
                    TaskStatus.SUCCESS, TaskStatus.ABORTED, TaskStatus.ERROR,
                    TaskStatus.CANCELED
                ],
                callback=None)
            assert t.get('status').lower() == TaskStatus.SUCCESS.value
            tags = {}
            tags['cse.cluster.id'] = self.cluster_id
            tags['cse.version'] = pkg_resources.require(
                'container-service-extension')[0].version
            tags['cse.template'] = template['name']
            vapp = VApp(self.client_tenant, href=vapp_resource.get('href'))
            for k, v in tags.items():
                t = vapp.set_metadata('GENERAL', 'READWRITE', k, v)
                self.client_tenant.get_task_monitor().\
                    wait_for_status(
                        task=t,
                        timeout=600,
                        poll_frequency=5,
                        fail_on_status=None,
                        expected_target_statuses=[TaskStatus.SUCCESS],
                        callback=None)
            self.update_task(
                TaskStatus.RUNNING,
                self.op,
                message='Creating master node for %s(%s)' % (self.cluster_name,
                                                             self.cluster_id))
            vapp.reload()
            add_nodes(
                1,
                template,
                TYPE_MASTER,
                self.config,
                self.client_tenant,
                org,
                vdc,
                vapp,
                self.body,
                wait=True)

            self.update_task(
                TaskStatus.RUNNING,
                self.op,
                message='Initializing cluster %s(%s)' % (self.cluster_name,
                                                         self.cluster_id))

            vapp.reload()
            init_cluster(self.config, vapp, template)

            master_ip = get_master_ip(self.config, vapp, template)
            t = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                  master_ip)
            self.client_tenant.get_task_monitor().\
                wait_for_status(
                    task=t,
                    timeout=600,
                    poll_frequency=5,
                    fail_on_status=None,
                    expected_target_statuses=[TaskStatus.SUCCESS],
                    callback=None)

            if self.body['node_count'] > 0:

                self.update_task(
                    TaskStatus.RUNNING,
                    self.op,
                    message='Creating %s node(s) for %s(%s)' %
                    (self.body['node_count'], self.cluster_name,
                     self.cluster_id))
                add_nodes(
                    self.body['node_count'],
                    template,
                    TYPE_NODE,
                    self.config,
                    self.client_tenant,
                    org,
                    vdc,
                    vapp,
                    self.body,
                    wait=True)
                self.update_task(
                    TaskStatus.RUNNING,
                    self.op,
                    message='Adding %s node(s) to %s(%s)' %
                    (self.body['node_count'], self.cluster_name,
                     self.cluster_id))
                vapp.reload()
                join_cluster(self.config, vapp, template)

            self.update_task(
                TaskStatus.SUCCESS,
                self.op,
                message='Created cluster %s(%s)' % (self.cluster_name,
                                                    self.cluster_id))

        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(TaskStatus.ERROR, self.op, error_message=str(e))

    def delete_cluster(self, headers, body):
        result = {}
        result['body'] = {}
        LOGGER.debug('about to delete cluster with name: %s' % body['name'])
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            self.cluster_name = body['name']
            self.tenant_info = self._connect_tenant(headers)
            self.headers = headers
            self.body = body
            self.op = OP_DELETE_CLUSTER
            self._connect_sysadmin()
            clusters = load_from_metadata(
                self.client_tenant, name=self.cluster_name)
            if len(clusters) != 1:
                raise Exception('Cluster %s not found.' % self.cluster_name)
            self.cluster = clusters[0]
            self.cluster_id = self.cluster['cluster_id']

            self.update_task(
                TaskStatus.RUNNING,
                self.op,
                message='Deleting cluster %s(%s)' % (self.cluster_name,
                                                     self.cluster_id))
            self.daemon = True
            self.start()
            response_body = {}
            response_body['cluster_name'] = self.cluster_name
            response_body['task_href'] = self.t.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            if hasattr(e, 'message'):
                result['body'] = {'message': e.message}
            else:
                result['body'] = {'message': str(e)}
            LOGGER.error(traceback.format_exc())
        return result

    def delete_cluster_thread(self):
        LOGGER.debug('about to delete cluster with name: %s',
                     self.cluster_name)
        try:
            vdc = VDC(self.client_tenant, href=self.cluster['vdc_href'])
            delete_task = vdc.delete_vapp(self.cluster['name'], force=True)
            self.client_tenant.get_task_monitor().\
                wait_for_status(
                    task=delete_task,
                    timeout=600,
                    poll_frequency=5,
                    fail_on_status=None,
                    expected_target_statuses=[TaskStatus.SUCCESS],
                    callback=None)
            self.update_task(
                TaskStatus.SUCCESS,
                self.op,
                message='Deleted cluster %s(%s)' % (self.cluster_name,
                                                    self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(
                self.cluster_name,
                self.cluster_id,
                TaskStatus.ERROR,
                self.op,
                error_message=str(e))

    def get_cluster_config(self, cluster_name, headers):
        result = {}
        try:
            self._connect_tenant(headers)
            clusters = load_from_metadata(
                self.client_tenant, name=cluster_name)
            if len(clusters) != 1:
                raise Exception('Cluster \'%s\' not found' % cluster_name)
            vapp = VApp(self.client_tenant, href=clusters[0]['vapp_href'])
            template = self.get_template(name=clusters[0]['template'])
            result['body'] = get_cluster_config(self.config, vapp,
                                                template['admin_password'])
            result['status_code'] = OK
        except Exception as e:
            result['body'] = str(e)
            result['status_code'] = INTERNAL_SERVER_ERROR
        return result
