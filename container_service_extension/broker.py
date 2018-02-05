# SPDX-License-Identifier: BSD-2-Clause

import logging
import re
import threading
import traceback
import uuid

import click
import pkg_resources
from pyvcloud.vcd.client import _WellKnownEndpoint
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.client import VCLOUD_STATUS_MAP
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM
import requests
import yaml

from container_service_extension.cluster import add_nodes
from container_service_extension.cluster import delete_nodes_from_cluster
from container_service_extension.cluster import get_cluster_config
from container_service_extension.cluster import get_master_ip
from container_service_extension.cluster import init_cluster
from container_service_extension.cluster import join_cluster
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import TYPE_MASTER
from container_service_extension.cluster import TYPE_NODE

LOGGER = logging.getLogger('cse.broker')

OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_SERVER_ERROR = 500

OP_CREATE_CLUSTER = 'create_cluster'
OP_DELETE_CLUSTER = 'delete_cluster'
OP_CREATE_NODES = 'create_nodes'
OP_DELETE_NODES = 'delete_nodes'

OP_MESSAGE = {
    OP_CREATE_CLUSTER: 'create cluster',
    OP_DELETE_CLUSTER: 'delete cluster',
    OP_CREATE_NODES: 'create nodes in cluster',
    OP_DELETE_NODES: 'delete nodes from cluster',
}

MAX_HOST_NAME_LENGTH = 25

SAMPLE_TEMPLATE_PHOTON_V2 = {
    'name':
    'photon-v2',
    'catalog_item':
    'photon-custom-hw11-2.0-304b817-k8s',
    'source_ova_name':
    'photon-custom-hw11-2.0-304b817.ova',
    'source_ova':
    'http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova',  # NOQA
    'sha1_ova':
    'b8c183785bbf582bcd1be7cde7c22e5758fb3f16',
    'temp_vapp':
    'photon2-temp',
    'cleanup':
    True,
    'cpu':
    2,
    'mem':
    2048,
    'admin_password':
    'guest_os_admin_password',
    'description':
    "PhotonOS v2\nDocker 17.06.0-1\nKubernetes 1.8.1\nweave 2.0.5"
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
    'Ubuntu 16.04\nDocker 17.12.0~ce\nKubernetes 1.9.1\nweave 2.1.3'
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
        'default_template': SAMPLE_TEMPLATE_PHOTON_V2['name'],
        'templates': [SAMPLE_TEMPLATE_PHOTON_V2, SAMPLE_TEMPLATE_UBUNTU_16_04],
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
        for k, v in SAMPLE_TEMPLATE_PHOTON_V2.items():
            if k not in template.keys():
                raise Exception('missing key: %s' % k)
        for k, v in template.items():
            if k not in SAMPLE_TEMPLATE_PHOTON_V2.keys():
                raise Exception('invalid key: %s' % k)


def validate_broker_config_content(config, client, template='*'):
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

    def _to_message(self, e):
        if hasattr(e, 'message'):
            return {'message': e.message}
        else:
            return {'message': str(e)}

    def update_task(self, status, message=None, error_message=None):
        if not hasattr(self, 'task'):
            self.task = Task(self.client_sysadmin)
        if message is None:
            message = OP_MESSAGE[self.op]
        if hasattr(self, 'task_resource'):
            task_href = self.task_resource.get('href')
        else:
            task_href = None
        self.task_resource = self.task.update(
            status.value,
            'vcloud.cse',
            message,
            self.op,
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
        """Validate that the cluster name against the pattern."""
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
        elif self.op == OP_CREATE_NODES:
            self.create_nodes_thread()
        elif self.op == OP_DELETE_NODES:
            self.delete_nodes_thread()

    def list_clusters(self, headers, body):
        result = {}
        try:
            result['body'] = []
            result['status_code'] = OK
            self._connect_tenant(headers)
            clusters = load_from_metadata(self.client_tenant)
            result['body'] = clusters
        except Exception:
            LOGGER.error(traceback.format_exc())
            result['body'] = []
            result['status_code'] = INTERNAL_SERVER_ERROR
            result['message'] = traceback.format_exc()
        return result

    def get_cluster_info(self, name, headers, body):
        result = {}
        try:
            result['body'] = []
            result['status_code'] = OK
            self._connect_tenant(headers)
            clusters = load_from_metadata(self.client_tenant, name=name)
            if len(clusters) == 0:
                raise Exception('Cluster \'%s\' not found.' % name)
            vapp = VApp(self.client_tenant, href=clusters[0]['vapp_href'])
            vms = vapp.get_all_vms()
            for vm in vms:
                node_info = {
                    'name': vm.get('name'),
                    'numberOfCpus': '',
                    'memoryMB': '',
                    'status': VCLOUD_STATUS_MAP.get(int(vm.get('status'))),
                    'ipAddress': ''
                }
                if hasattr(vm, 'VmSpecSection'):
                    node_info['numberOfCpus'] = vm.VmSpecSection.NumCpus.text
                    node_info[
                        'memoryMB'] = \
                        vm.VmSpecSection.MemoryResourceMb.Configured.text
                try:
                    node_info['ipAddress'] = vapp.get_primary_ip(
                        vm.get('name'))
                except Exception:
                    LOGGER.debug(
                        'cannot get ip address for node %s' % vm.get('name'))
                if vm.get('name').startswith(TYPE_MASTER):
                    node_info['node_type'] = 'master'
                    clusters[0].get('master_nodes').append(node_info)
                elif vm.get('name').startswith(TYPE_NODE):
                    node_info['node_type'] = 'node'
                    clusters[0].get('nodes').append(node_info)
            result['body'] = clusters[0]
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            result['body'] = []
            result['status_code'] = INTERNAL_SERVER_ERROR
            result['message'] = str(e)
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
        result['body'] = {
            'message': 'can\'t create cluster \'%s\'' % cluster_name
        }
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
                message='Creating cluster %s(%s)' % (cluster_name,
                                                     self.cluster_id))
            self.daemon = True
            self.start()
            response_body = {}
            response_body['name'] = self.cluster_name
            response_body['cluster_id'] = self.cluster_id
            response_body['task_href'] = self.task_resource.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = self._to_message(e)
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
                message='Creating cluster vApp %s(%s)' % (self.cluster_name,
                                                          self.cluster_id))
            vapp_resource = vdc.create_vapp(
                self.cluster_name,
                description='cluster %s' % self.cluster_name,
                network=network_name,
                fence_mode='bridged')
            self.client_tenant.get_task_monitor().wait_for_status(
                vapp_resource.Tasks.Task[0])
            tags = {}
            tags['cse.cluster.id'] = self.cluster_id
            tags['cse.version'] = pkg_resources.require(
                'container-service-extension')[0].version
            tags['cse.template'] = template['name']
            vapp = VApp(self.client_tenant, href=vapp_resource.get('href'))
            for k, v in tags.items():
                task = vapp.set_metadata('GENERAL', 'READWRITE', k, v)
                self.client_tenant.get_task_monitor().wait_for_status(task)
            self.update_task(
                TaskStatus.RUNNING,
                message='Creating master node for %s(%s)' % (self.cluster_name,
                                                             self.cluster_id))
            vapp.reload()
            add_nodes(1, template, TYPE_MASTER, self.config,
                      self.client_tenant, org, vdc, vapp, self.body)
            self.update_task(
                TaskStatus.RUNNING,
                message='Initializing cluster %s(%s)' % (self.cluster_name,
                                                         self.cluster_id))
            vapp.reload()
            init_cluster(self.config, vapp, template)
            master_ip = get_master_ip(self.config, vapp, template)
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     master_ip)
            self.client_tenant.get_task_monitor().wait_for_status(task)
            if self.body['node_count'] > 0:
                self.update_task(
                    TaskStatus.RUNNING,
                    message='Creating %s node(s) for %s(%s)' %
                    (self.body['node_count'], self.cluster_name,
                     self.cluster_id))
                add_nodes(self.body['node_count'], template, TYPE_NODE,
                          self.config, self.client_tenant, org, vdc, vapp,
                          self.body)
                self.update_task(
                    TaskStatus.RUNNING,
                    message='Adding %s node(s) to %s(%s)' %
                    (self.body['node_count'], self.cluster_name,
                     self.cluster_id))
                vapp.reload()
                join_cluster(self.config, vapp, template)
            self.update_task(
                TaskStatus.SUCCESS,
                message='Created cluster %s(%s)' % (self.cluster_name,
                                                    self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(TaskStatus.ERROR, error_message=str(e))

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
                message='Deleting cluster %s(%s)' % (self.cluster_name,
                                                     self.cluster_id))
            self.daemon = True
            self.start()
            response_body = {}
            response_body['cluster_name'] = self.cluster_name
            response_body['task_href'] = self.task_resource.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = self._to_message(e)
            LOGGER.error(traceback.format_exc())
        return result

    def delete_cluster_thread(self):
        LOGGER.debug('about to delete cluster with name: %s',
                     self.cluster_name)
        try:
            vdc = VDC(self.client_tenant, href=self.cluster['vdc_href'])
            task = vdc.delete_vapp(self.cluster['name'], force=True)
            self.client_tenant.get_task_monitor().wait_for_status(task)
            self.update_task(
                TaskStatus.SUCCESS,
                message='Deleted cluster %s(%s)' % (self.cluster_name,
                                                    self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(TaskStatus.ERROR, error_message=str(e))

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
            result['body'] = self._to_message(e)
            result['status_code'] = INTERNAL_SERVER_ERROR
        return result

    def create_nodes(self, headers, body):
        result = {'body': {}}
        self.cluster_name = body['name']
        LOGGER.debug('about to add %s nodes to cluster %s on VDC %s, sp=%s',
                     body['node_count'], self.cluster_name, body['vdc'],
                     body['storage_profile'])
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            if body['node_count'] < 1:
                raise Exception('Invalid node count: %s.' % body['node_count'])
            self.tenant_info = self._connect_tenant(headers)
            clusters = load_from_metadata(
                self.client_tenant, name=self.cluster_name)
            if len(clusters) != 1:
                raise Exception(
                    'Cluster \'%s\' not found.' % self.cluster_name)
            self.cluster = clusters[0]
            self.headers = headers
            self.body = body
            self.op = OP_CREATE_NODES
            self._connect_sysadmin()
            self.cluster_id = self.cluster['cluster_id']
            self.update_task(
                TaskStatus.RUNNING,
                message='Adding %s node(s) to cluster %s(%s)' %
                (body['node_count'], self.cluster_name, self.cluster_id))
            self.daemon = True
            self.start()
            response_body = {}
            response_body['cluster_name'] = self.cluster_name
            response_body['task_href'] = self.task_resource.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = self._to_message(e)
            LOGGER.error(traceback.format_exc())
        return result

    def create_nodes_thread(self):
        LOGGER.debug('about to add nodes to cluster with name: %s',
                     self.cluster_name)
        try:
            org_resource = self.client_tenant.get_org()
            org = Org(self.client_tenant, resource=org_resource)
            vdc = VDC(self.client_tenant, href=self.cluster['vdc_href'])
            vapp = VApp(self.client_tenant, href=self.cluster['vapp_href'])
            template = self.get_template()
            self.update_task(
                TaskStatus.RUNNING,
                message='Creating %s node(s) for %s(%s)' %
                (self.body['node_count'], self.cluster_name, self.cluster_id))
            new_nodes = add_nodes(self.body['node_count'], template, TYPE_NODE,
                                  self.config, self.client_tenant, org, vdc,
                                  vapp, self.body)
            self.update_task(
                TaskStatus.RUNNING,
                message='Adding %s node(s) to %s(%s)' %
                (self.body['node_count'], self.cluster_name, self.cluster_id))
            target_nodes = []
            for spec in new_nodes['specs']:
                target_nodes.append(spec['target_vm_name'])
            vapp.reload()
            join_cluster(self.config, vapp, template, target_nodes)
            self.update_task(
                TaskStatus.SUCCESS,
                message='Added %s node(s) to cluster %s(%s)' %
                (self.body['node_count'], self.cluster_name, self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(TaskStatus.ERROR, error_message=str(e))

    def delete_nodes(self, headers, body):
        result = {'body': {}}
        self.cluster_name = body['name']
        LOGGER.debug(
            'about to delete nodes from cluster with name: %s' % body['name'])
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            if len(body['nodes']) < 1:
                raise Exception('Invalid list of nodes: %s.' % body['nodes'])
            for node in body['nodes']:
                if node.startswith(TYPE_MASTER):
                    raise Exception(
                        'Can\'t delete a master node: \'%s\'.' % node)
            self.tenant_info = self._connect_tenant(headers)
            clusters = load_from_metadata(
                self.client_tenant, name=self.cluster_name)
            if len(clusters) != 1:
                raise Exception(
                    'Cluster \'%s\' not found.' % self.cluster_name)
            self.cluster = clusters[0]
            self.headers = headers
            self.body = body
            self.op = OP_DELETE_NODES
            self._connect_sysadmin()
            self.cluster_id = self.cluster['cluster_id']
            self.update_task(
                TaskStatus.RUNNING,
                message='Deleting %s node(s) from cluster %s(%s)' %
                (len(body['nodes']), self.cluster_name, self.cluster_id))
            self.daemon = True
            self.start()
            response_body = {}
            response_body['cluster_name'] = self.cluster_name
            response_body['task_href'] = self.task_resource.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = self._to_message(e)
            LOGGER.error(traceback.format_exc())
        return result

    def delete_nodes_thread(self):
        LOGGER.debug('about to delete nodes from cluster with name: %s',
                     self.cluster_name)
        try:
            vapp = VApp(self.client_tenant, href=self.cluster['vapp_href'])
            template = self.get_template()
            self.update_task(
                TaskStatus.RUNNING,
                message='Deleting %s node(s) from %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
            delete_nodes_from_cluster(self.config, vapp, template,
                                      self.body['nodes'], self.body['force'])
            self.update_task(
                TaskStatus.RUNNING,
                message='Undeploying %s node(s) for %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
            for vm_name in self.body['nodes']:
                vm = VM(self.client_tenant, resource=vapp.get_vm(vm_name))
                try:
                    task = vm.undeploy()
                    self.client_tenant.get_task_monitor().wait_for_status(task)
                except Exception as e:
                    LOGGER.warning('couldn\'t undeploy VM %s' % vm_name)
            self.update_task(
                TaskStatus.RUNNING,
                message='Deleting %s VM(s) for %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
            task = vapp.delete_vms(self.body['nodes'])
            self.client_tenant.get_task_monitor().wait_for_status(task)
            self.update_task(
                TaskStatus.SUCCESS,
                message='Deleted %s node(s) to cluster %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(TaskStatus.ERROR, error_message=str(e))
