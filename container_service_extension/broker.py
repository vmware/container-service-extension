# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import TYPE_MASTER
from container_service_extension.cluster import TYPE_NODE
import datetime
import logging
from pyvcloud.vcd.client import _WellKnownEndpoint
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vsphere import VSphere
import re
import requests
import threading
import time
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

MAX_HOST_NAME_LENGTH = 25 - 4

SAMPLE_CONFIG_PHOTON = {'broker': {
    'type': 'default',
    'org': 'Admin',
    'vdc': 'Catalog',
    'catalog': 'cse',
    'network': 'admin_network',
    'ip_allocation_mode': 'pool',
    'storage_profile': '*',
    'labels': ['photon', '1.0'],
    'source_ova_name': 'photon-custom-hw11-1.0-62c543d.ova',
    'source_ova': 'https://bintray.com/vmware/photon/download_file?file_path=photon-custom-hw11-1.0-62c543d.ova',
    'sha1_ova': '18c1a6d31545b757d897c61a0c3cc0e54d8aeeba',
    'temp_vapp': 'csetmp-p',
    'cleanup': True,
    'master_template': 'k8s-p.ova',
    'master_template_disk': 0,
    'node_template': 'k8s-p.ova',
    'password': 'root_secret_password',
    'ssh_public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDFS5HL4CBlWrZscohhqdVwUa815Pi3NaCijfdvs0xCNF2oP458Xb3qYdEmuFWgtl3kEM4hR60/Tzk7qr3dmAfY7GPqdGhQsZEnvUJq0bfDAh0KqhdrqiIqx9zlKWnR65gl/u7Qkck2jiKkqjfxZwmJcuVCu+zQZCRC80XKwpyOudLKd/zJz9tzJxJ7+yltu9rNdshCEfP+OR1QoY2hFRH1qaDHTIbDdlF/m0FavapH7+ScufOY/HNSSYH7/SchsxK3zywOwGV1e1z//HHYaj19A3UiNdOqLkitKxFQrtSyDfClZ/0SwaVxh4jqrKuJ5NT1fbN2bpDWMgffzD9WWWZbDvtYQnl+dBjDnzBZGo8miJ87lYiYH9N9kQfxXkkyPziAjWj8KZ8bYQWJrEQennFzsbbreE8NtjsM059RXz0kRGeKs82rHf0mTZltokAHjoO5GmBZb8sZTdZyjfo0PTgaNCENe0brDTrAomM99LhW2sJ5ZjK7SIqpWFaU+P+qgj4s88btCPGSqnh0Fea1foSo5G57l5YvfYpJalW0IeiynrO7TRuxEVV58DJNbYyMCvcZutuyvNq0OpEQYXRM2vMLQX3ZX3YhHMTlSXXcriqvhOJ7aoNae5aiPSlXvgFi/wP1x1aGYMEsiqrjNnrflGk9pIqniXsJ/9TFwRh9m4GktQ== cse',
    'master_cpu': 2,
    'master_mem': 2048,
    'node_cpu': 2,
    'node_mem': 2048,
    'cse_msg_dir': '/tmp/cse'
}}  # NOQA

SAMPLE_CONFIG_UBUNTU = {'broker': {
    'type': 'default',
    'org': 'Admin',
    'vdc': 'Catalog',
    'catalog': 'cse',
    'network': 'admin_network',
    'ip_allocation_mode': 'pool',
    'storage_profile': '*',
    'labels': ['ubuntu', '16.04'],
    'source_ova_name': 'ubuntu-16.04-server-cloudimg-amd64.ova',
    'source_ova': 'https://cloud-images.ubuntu.com/releases/xenial/release-20171011/ubuntu-16.04-server-cloudimg-amd64.ova',
    'sha1_ova': '1bddf68820c717e13c6d1acd800fb7b4d197b411',
    'temp_vapp': 'csetmp-u',
    'cleanup': True,
    'master_template': 'k8s-u.ova',
    'master_template_disk': 20000,
    'node_template': 'k8s-u.ova',
    'password': 'root_secret_password',
    'ssh_public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDFS5HL4CBlWrZscohhqdVwUa815Pi3NaCijfdvs0xCNF2oP458Xb3qYdEmuFWgtl3kEM4hR60/Tzk7qr3dmAfY7GPqdGhQsZEnvUJq0bfDAh0KqhdrqiIqx9zlKWnR65gl/u7Qkck2jiKkqjfxZwmJcuVCu+zQZCRC80XKwpyOudLKd/zJz9tzJxJ7+yltu9rNdshCEfP+OR1QoY2hFRH1qaDHTIbDdlF/m0FavapH7+ScufOY/HNSSYH7/SchsxK3zywOwGV1e1z//HHYaj19A3UiNdOqLkitKxFQrtSyDfClZ/0SwaVxh4jqrKuJ5NT1fbN2bpDWMgffzD9WWWZbDvtYQnl+dBjDnzBZGo8miJ87lYiYH9N9kQfxXkkyPziAjWj8KZ8bYQWJrEQennFzsbbreE8NtjsM059RXz0kRGeKs82rHf0mTZltokAHjoO5GmBZb8sZTdZyjfo0PTgaNCENe0brDTrAomM99LhW2sJ5ZjK7SIqpWFaU+P+qgj4s88btCPGSqnh0Fea1foSo5G57l5YvfYpJalW0IeiynrO7TRuxEVV58DJNbYyMCvcZutuyvNq0OpEQYXRM2vMLQX3ZX3YhHMTlSXXcriqvhOJ7aoNae5aiPSlXvgFi/wP1x1aGYMEsiqrjNnrflGk9pIqniXsJ/9TFwRh9m4GktQ== cse',
    'master_cpu': 2,
    'master_mem': 2048,
    'node_cpu': 2,
    'node_mem': 2048,
    'cse_msg_dir': '/tmp/cse'
}}  # NOQA

SAMPLE_CONFIG = SAMPLE_CONFIG_UBUNTU

def get_sample_broker_config():
    return yaml.safe_dump(SAMPLE_CONFIG, default_flow_style=False)


def validate_broker_config(config):
    for k, v in SAMPLE_CONFIG['broker'].items():
        if k not in config.keys():
            raise Exception('missing key: %s' % k)
    for k, v in config.items():
        if k not in SAMPLE_CONFIG['broker'].keys():
            raise Exception('invalid key: %s' % k)


def get_new_broker(config):
    if config['broker']['type'] == 'default':
        return DefaultBroker(config)
    else:
        return None


def wait_until_ready(vs, vm, password, file='/proc/version'):
    while True:
        try:
            f = vs.download_file_from_guest(
                vm,
                'root',
                password,
                file)
            LOGGER.debug('vm %s is ready' % vm)
            return
        except:
            LOGGER.error(traceback.format_exc())
            LOGGER.debug('waiting for vm %s to be ready' % vm)
            time.sleep(1)


def wait_until_tools_ready(vm):
    while True:
        try:
            status = vm.guest.toolsRunningStatus
            if 'guestToolsRunning' == status:
                LOGGER.debug('vm tools %s are ready' % vm)
                return
            LOGGER.debug('waiting for vm tools %s to be ready (%s)' % (vm, status))
            time.sleep(1)
        except:
            LOGGER.debug('waiting for vm tools %s to be ready (%s)* ' % (vm, status))
            time.sleep(1)


def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor


spinner = spinning_cursor()


def task_callback(task):
    message = '\x1b[2K\r{}: {}, status: {}'.format(
        task.get('operationName'), task.get('operation'), task.get('status')
    )
    if hasattr(task, 'Progress'):
        message += ', progress: %s%%' % task.Progress
    if task.get('status').lower() in [TaskStatus.QUEUED.value,
                                      TaskStatus.PENDING.value,
                                      TaskStatus.PRE_RUNNING.value,
                                      TaskStatus.RUNNING.value]:
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
        self.client_sysadmin = Client(uri=self.host,
                                      api_version=self.version,
                                      verify_ssl_certs=self.verify,
                                      log_file='sysadmin.log',
                                      log_headers=True,
                                      log_bodies=True
                                      )
        self.client_sysadmin.set_credentials(
            BasicLoginCredentials(self.username,
                                  'System',
                                  self.password))

    def _connect_tenant(self, headers):
        token = headers.get('x-vcloud-authorization')
        accept_header = headers.get('Accept')
        version = accept_header.split('version=')[1]
        self.client_tenant = Client(uri=self.host,
                                    api_version=version,
                                    verify_ssl_certs=self.verify,
                                    log_file='tenant.log',
                                    log_headers=True,
                                    log_bodies=True
                                    )
        session = self.client_tenant.rehydrate_from_token(token)
        return {'user_name': session.get('user'),
                'user_id': session.get('userId'),
                'org_name': session.get('org'),
                'org_href': self.client_tenant._get_wk_endpoint(
                    _WellKnownEndpoint.LOGGED_IN_ORG)
                }

    def is_valid_name(self, name):
        """Validates that the cluster name against the pattern.

        """
        if len(name) > MAX_HOST_NAME_LENGTH:
            return False
        if name[-1] == '.':
            name = name[:-1]
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in name.split("."))

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
            clusters = load_from_metadata(self.client_tenant,
                                          get_leader_ip=True)
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
                     cluster_name,
                     vdc_name,
                     node_count,
                     body['storage_profile'])
        result['body'] = {'message': 'can\'t create cluster'}
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            if not self.is_valid_name(cluster_name):
                raise Exception('Invalid cluster name')
            self.tenant_info = self._connect_tenant(headers)
            self.headers = headers
            self.body = body
            self.cluster_id = str(uuid.uuid4())
            self.op = OP_CREATE_CLUSTER
            self._connect_sysadmin()
            task = Task(self.client_sysadmin)
            self.t = task.update(
                TaskStatus.RUNNING.value,
                'vcloud.cse',
                'Creating cluster %s(%s)' % (cluster_name, self.cluster_id),
                self.op,
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href']
            )
            self.daemon = True
            self.start()
            response_body = {}
            response_body['name'] = cluster_name
            response_body['cluster_id'] = self.cluster_id
            response_body['task_href'] = self.t.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = {'message': e.message}
            LOGGER.error(traceback.format_exc())
        return result

    def create_cluster_thread(self):
        cluster_name = self.body['name']
        network_name = self.body['network']

        task = Task(self.client_sysadmin)
        try:
            clusters = load_from_metadata(self.client_tenant,
                                          name=cluster_name)
            LOGGER.debug(clusters)
            if len(clusters) != 0:
                raise Exception('Cluster already exists.')

            self.t = task.update(
                TaskStatus.RUNNING.value,
                'vcloud.cse',
                'Creating nodes %s(%s)' % (cluster_name, self.cluster_id),
                self.op,
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href'],
                task_href=self.t.get('href'))
            org_resource = self.client_tenant.get_org()
            org = Org(self.client_tenant, resource=org_resource)
            vdc_resource = org.get_vdc(self.body['vdc'])

            master_count = 1
            node_count = int(self.body['node_count'])
            catalog = self.config['broker']['catalog']
            master_template = self.config['broker']['master_template']
            node_template = self.config['broker']['node_template']
            master_cpu = self.config['broker']['master_cpu']
            master_mem = self.config['broker']['master_mem']
            node_cpu = self.config['broker']['node_cpu']
            node_mem = self.config['broker']['node_mem']
            storage_profile = self.body['storage_profile']

            vdc = VDC(self.client_tenant, resource=vdc_resource)

            if 'photon' in self.config['broker']['labels']:
                cmd_prefix = '/usr/bin/'
            elif 'ubuntu' in self.config['broker']['labels']:
                cmd_prefix = '/bin/'
            else:
                cmd_prefix = '/bin/'
            masters = []
            for n in range(master_count):
                time.sleep(1)
                name = cluster_name + '-m%s' % str(n+1)
                self.t = task.update(
                    TaskStatus.RUNNING.value,
                    'vcloud.cse',
                    'Creating master node %s(%s)' % (name, self.cluster_id),
                    self.op,
                    '',
                    None,
                    'urn:cse:cluster:%s' % self.cluster_id,
                    cluster_name,
                    'application/vcloud.cse.cluster+xml',
                    self.tenant_info['user_id'],
                    self.tenant_info['user_name'],
                    org_href=self.tenant_info['org_href'],
                    task_href=self.t.get('href'))
                vapp_resource = vdc.instantiate_vapp(
                    name,
                    catalog,
                    master_template,
                    memory=master_mem,
                    cpu=master_cpu,
                    network=network_name,
                    deploy=True,
                    power_on=True,
                    cust_script=None,
                    ip_allocation_mode='pool',
                    accept_all_eulas=True,
                    vm_name=name,
                    hostname=name,
                    storage_profile=storage_profile)
                t = self.client_tenant.get_task_monitor().wait_for_status(
                                    task=vapp_resource.Tasks.Task[0],
                                    timeout=60,
                                    poll_frequency=2,
                                    fail_on_status=None,
                                    expected_target_statuses=[
                                        TaskStatus.SUCCESS,
                                        TaskStatus.ABORTED,
                                        TaskStatus.ERROR,
                                        TaskStatus.CANCELED],
                                    callback=None)
                masters.append(vapp_resource)
            nodes = []
            for n in range(node_count):
                time.sleep(1)
                name = cluster_name + '-n%s' % str(n+1)
                self.t = task.update(
                    TaskStatus.RUNNING.value,
                    'vcloud.cse',
                    'Creating node %s(%s)' % (name, self.cluster_id),
                    self.op,
                    '',
                    None,
                    'urn:cse:cluster:%s' % self.cluster_id,
                    cluster_name,
                    'application/vcloud.cse.cluster+xml',
                    self.tenant_info['user_id'],
                    self.tenant_info['user_name'],
                    org_href=self.tenant_info['org_href'],
                    task_href=self.t.get('href'))
                vapp_resource = vdc.instantiate_vapp(
                    name,
                    catalog,
                    node_template,
                    memory=node_mem,
                    cpu=node_cpu,
                    network=network_name,
                    deploy=True,
                    power_on=True,
                    cust_script=None,
                    ip_allocation_mode='pool',
                    accept_all_eulas=True,
                    vm_name=name,
                    hostname=name,
                    storage_profile=storage_profile)
                t = self.client_tenant.get_task_monitor().wait_for_status(
                                    task=vapp_resource.Tasks.Task[0],
                                    timeout=60,
                                    poll_frequency=2,
                                    fail_on_status=None,
                                    expected_target_statuses=[
                                        TaskStatus.SUCCESS,
                                        TaskStatus.ABORTED,
                                        TaskStatus.ERROR,
                                        TaskStatus.CANCELED],
                                    callback=None)
                nodes.append(vapp_resource)
            tagged = set([])
            while len(tagged) < (master_count + node_count):
                node = None
                node_type = None
                for n in masters:
                    if n.get('name') not in tagged:
                        node = n
                        node_type = TYPE_MASTER
                        break
                if node is None:
                    for n in nodes:
                        if n.get('name') not in tagged:
                            node = n
                            node_type = TYPE_NODE
                            break
                if node is not None:
                    LOGGER.debug('about to tag %s, href=%s',
                                 node.get('name'),
                                 node.get('href'))
                    try:
                        self.t = task.update(
                            TaskStatus.RUNNING.value,
                            'vcloud.cse',
                            'Tagging node %s(%s)' % (node.get('name'), self.cluster_id),
                            self.op,
                            '',
                            None,
                            'urn:cse:cluster:%s' % self.cluster_id,
                            cluster_name,
                            'application/vcloud.cse.cluster+xml',
                            self.tenant_info['user_id'],
                            self.tenant_info['user_name'],
                            org_href=self.tenant_info['org_href'],
                            task_href=self.t.get('href'))
                        tags = {}
                        tags['cse.cluster.id'] = self.cluster_id
                        tags['cse.node.type'] = node_type
                        tags['cse.cluster.name'] = cluster_name
                        vapp = VApp(self.client_tenant,
                                    href=node.get('href'))
                        for k, v in tags.items():
                            t = vapp.set_metadata('GENERAL',
                                                  'READWRITE',
                                                  k,
                                                  v)
                            self.client_tenant.get_task_monitor().\
                                wait_for_status(
                                    task=t,
                                    timeout=600,
                                    poll_frequency=5,
                                    fail_on_status=None,
                                    expected_target_statuses=[TaskStatus.SUCCESS], # NOQA
                                    callback=None)
                        tagged.update([node.get('name')])
                        LOGGER.debug('tagged %s', node.get('name'))
                    except Exception:
                        LOGGER.error(
                            'can''t tag %s at this moment, will retry later',
                            node.get('name'))
                        LOGGER.error(traceback.format_exc())
                        time.sleep(5)
            self.customize_nodes()
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.t = task.update(
                TaskStatus.ERROR.value,
                'vcloud.cse',
                self.op,
                'create cluster',
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href'],
                task_href=self.t.get('href'),
                error_message=str(e))

    def delete_cluster(self, cluster_name, headers, body):
        result = {}
        result['body'] = {}
        LOGGER.debug('about to delete cluster with name: %s', cluster_name)
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            self.cluster_name = cluster_name
            self.tenant_info = self._connect_tenant(headers)
            self.headers = headers
            self.body = body
            self.op = OP_DELETE_CLUSTER
            self.cluster_id = ''
            self._connect_sysadmin()
            task = Task(self.client_sysadmin)
            self.t = task.update(
                TaskStatus.RUNNING.value,
                'vcloud.cse',
                'Deleting cluster %s(%s)' % (self.cluster_name,
                                             self.cluster_id),
                self.op,
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                self.cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href']
            )
            self.daemon = True
            self.start()
            response_body = {}
            response_body['cluster_name'] = self.cluster_name
            response_body['task_href'] = self.t.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = {'message': e.message}
            LOGGER.error(traceback.format_exc())
        return result

    def delete_cluster_thread(self):
        LOGGER.debug('about to delete cluster with name: %s',
                     self.cluster_name)
        task = Task(self.client_sysadmin)
        try:
            clusters = load_from_metadata(self.client_tenant,
                                          name=self.cluster_name)
            LOGGER.debug(clusters)
            if len(clusters) != 1:
                raise Exception('Cluster not found.')
            cluster = clusters[0]
            # self.cluster_id = cluster['cluster_id']
            vdc = None
            # tasks = []
            for node in cluster['master_nodes']+cluster['nodes']:
                if vdc is None:
                    vdc = VDC(self.client_tenant, href=cluster['vdc_href'])
                LOGGER.debug('about to delete vapp %s', node['name'])
                try:
                    self.t = task.update(
                        TaskStatus.RUNNING.value,
                        'vcloud.cse',
                        'Deleting node %s(%s)' % (node['name'],
                                                     self.cluster_id),
                        self.op,
                        '',
                        None,
                        'urn:cse:cluster:%s' % self.cluster_id,
                        self.cluster_name,
                        'application/vcloud.cse.cluster+xml',
                        self.tenant_info['user_id'],
                        self.tenant_info['user_name'],
                        org_href=self.tenant_info['org_href'],
                        task_href=self.t.get('href')
                    )
                    delete_task = vdc.delete_vapp(node['name'], force=True)
                    self.client_tenant.get_task_monitor().\
                        wait_for_status(
                            task=delete_task,
                            timeout=600,
                            poll_frequency=5,
                            fail_on_status=None,
                            expected_target_statuses=[TaskStatus.SUCCESS], # NOQA
                            callback=None)
                    # tasks.append(delete_task)

                except Exception:
                    print('exception')
                    print(Exception)
                    # pass
                time.sleep(1)
            # TODO(wait until all nodes are deleted)
            self.t = task.update(
                TaskStatus.SUCCESS.value,
                'vcloud.cse',
                self.op,
                'delete cluster',
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                self.cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href'],
                task_href=self.t.get('href'))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.t = task.update(
                TaskStatus.ERROR.value,
                'vcloud.cse',
                self.op,
                'delete cluster',
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                self.cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href'],
                task_href=self.t.get('href'),
                error_message=str(e))

    def customize_nodes(self, max_retries=60):
        cluster_name = self.body['name']
        node_count = int(self.body['node_count'])
        task = Task(self.client_sysadmin)
        self.t = task.update(
            TaskStatus.RUNNING.value,
            'vcloud.cse',
            'Waiting for IPs %s(%s)' % (cluster_name, self.cluster_id),
            self.op,
            '',
            None,
            'urn:cse:cluster:%s' % self.cluster_id,
            cluster_name,
            'application/vcloud.cse.cluster+xml',
            self.tenant_info['user_id'],
            self.tenant_info['user_name'],
            org_href=self.tenant_info['org_href'],
            task_href=self.t.get('href'))
        nodes = []
        n = 0
        all_nodes_configured = False
        while n < max_retries:
            try:
                nodes = []
                clusters = load_from_metadata(self.client_tenant,
                                              cluster_id=self.cluster_id)
                LOGGER.debug(clusters)
                assert len(clusters) == 1
                cluster = clusters[0]
                for cluster_node in cluster['master_nodes'] + cluster['nodes']:
                    node = {'name': cluster_node['name'],
                            'href': cluster_node['href']}
                    vapp = VApp(self.client_tenant,
                                href=cluster_node['href'])
                    vapp.reload()
                    node['password'] = vapp.get_admin_password(
                                       cluster_node['name'])
                    node['ip'] = vapp.get_primary_ip(cluster_node['name'])
                    node['moid'] = vapp.get_vm_moid(cluster_node['name'])
                    if cluster_node['name'].endswith('-m1'):
                        node['node_type'] = TYPE_MASTER
                    else:
                        node['node_type'] = TYPE_NODE
                    nodes.append(node)
                for node in nodes:
                    if 'ip' in node.keys() and \
                       node['ip'] is not None and \
                       len(node['ip']) > 0 and \
                       not node['ip'].startswith('172.17.'):
                        pass
                    else:
                        n += 1
                        raise Exception('missing ip, retry %s' % n)
                all_nodes_configured = True
                break
            except Exception as e:
                LOGGER.error(traceback.format_exc())
                time.sleep(5)
        if not all_nodes_configured:
            message = 'ip not configured in at least one node'
            LOGGER.error(message)
            raise Exception(message)
        LOGGER.debug('ip configured in all nodes')
        master_node = None
        password = self.config['broker']['password']
        for node in nodes:
            self.t = task.update(
                TaskStatus.RUNNING.value,
                'vcloud.cse',
                'Customizing node %s(%s)' % (node['name'], self.cluster_id),
                self.op,
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href'],
                task_href=self.t.get('href'))
            vs = VSphere(self.config['vcs']['host'],
                         self.config['vcs']['username'],
                         self.config['vcs']['password'],
                         port=int(self.config['vcs']['port']))
            vs.connect()
            vm = vs.get_vm_by_moid(node['moid'])
            if 'photon' in self.config['broker']['labels']:
                cmd_prefix = '/usr/bin/'
            elif 'ubuntu' in self.config['broker']['labels']:
                cmd_prefix = '/bin/'
            else:
                cmd_prefix = '/bin/'
            wait_until_tools_ready(vm)
            while True:
                try:
                    vs.execute_program_in_guest(
                        vm,
                        'root',
                        node['password'],
                        cmd_prefix+'echo',
                        '-e "{password}\n{password}" | /usr/bin/passwd root'.
                        format(password=password),
                        wait_for_completion=False)
                    time.sleep(2)
                    break
                except:
                    LOGGER.error(traceback.format_exc())
                    time.sleep(1)
            wait_until_ready(vs, vm, password)
            if node['node_type'] == TYPE_MASTER:
                if 'photon' in self.config['broker']['labels']:
                    cust_script = """
#!/bin/bash
/usr/bin/kubeadm init --pod-network-cidr=10.244.0.0/16 --skip-preflight-checks --kubernetes-version=v1.7.7 > /tmp/kubeadm-init.out
{cmd_prefix}mkdir -p /root/.kube
{cmd_prefix}cp -f /etc/kubernetes/admin.conf /root/.kube/config
{cmd_prefix}chown $(id -u):$(id -g) /root/.kube/config
/usr/bin/kubectl apply -f /root/weave.yml
                    """.format(cmd_prefix=cmd_prefix)
                elif 'ubuntu' in self.config['broker']['labels']:
                    cust_script = """
#!/bin/bash
/usr/bin/kubeadm init --kubernetes-version=v1.8.2 > /tmp/kubeadm-init.out
{cmd_prefix}mkdir -p /root/.kube
{cmd_prefix}cp -f /etc/kubernetes/admin.conf /root/.kube/config
{cmd_prefix}chown $(id -u):$(id -g) /root/.kube/config
/usr/bin/kubectl apply -f /root/weave.yml
                    """.format(cmd_prefix=cmd_prefix)
                vs.upload_file_to_guest(
                    vm,
                    'root',
                    password,
                    cust_script,
                    '/tmp/customize.sh')
                vs.execute_program_in_guest(
                    vm,
                    'root',
                    password,
                    cmd_prefix+'chmod',
                    'u+rx /tmp/customize.sh',
                    wait_for_completion=True)
                vs.execute_program_in_guest(
                    vm,
                    'root',
                    password,
                    '/tmp/customize.sh',
                    '',
                    wait_for_completion=True)
                vs.execute_program_in_guest(
                    vm,
                    'root',
                    password,
                    cmd_prefix+'rm',
                    '-f /tmp/customize.sh',
                    wait_for_completion=True)
                response = vs.download_file_from_guest(
                            vm,
                            'root',
                            password,
                            '/tmp/kubeadm-init.out'
                            )
                content = response.content.decode('utf-8')
                if len(content) == 0:
                    raise Exception('Failed executing "kubeadm init"')
                try:
                    if 'photon' in self.config['broker']['labels']:
                        token = [x for x in content.splitlines() if x.strip().startswith('[token] Using token: ')][0].split()[-1]  # NOQA
                        token_hash = None
                    elif 'ubuntu' in self.config['broker']['labels']:
                        token = [x for x in content.splitlines() if x.strip().startswith('[bootstraptoken] Using token: ')][0].split()[-1]  # NOQA
                        token_hash = [x for x in content.splitlines() if '--discovery-token-ca-cert-hash' in x.strip()][0].split()[-1]  # NOQA
                        token_hash = None
                    else:
                        raise Exception('not supported config broker label')
                except:
                    LOGGER.error(traceback.format_exc())
                    raise Exception('Failed executing "kubeadm init", cannot find token:\%s' %
                                    content)
                vapp = VApp(self.client_tenant,
                            href=node['href'])
                vapp.reload()
                t = vapp.set_metadata('GENERAL',
                                      'READWRITE',
                                      'cse.cluster.token',
                                      token)
                self.client_tenant.get_task_monitor().\
                    wait_for_status(
                        task=t,
                        timeout=600,
                        poll_frequency=5,
                        fail_on_status=None,
                        expected_target_statuses=[TaskStatus.SUCCESS],
                        callback=None)
                node['token'] = token
                master_node = node
            LOGGER.debug('executed customization script on %s (%s)' % (node['name'], node['moid']))

        if master_node is None:
            raise Exception('No master node is configured.')
        else:
            for node in nodes:
                vs = VSphere(self.config['vcs']['host'],
                             self.config['vcs']['username'],
                             self.config['vcs']['password'],
                             port=int(self.config['vcs']['port']))
                vs.connect()
                vm = vs.get_vm_by_moid(node['moid'])
                cust_script = """
#!/bin/bash
{cmd_prefix}sed -ri 's/preserve_hostname: false/preserve_hostname: true/' /etc/cloud/cloud.cfg
""".format(cmd_prefix=cmd_prefix)
                if node['node_type'] == TYPE_MASTER:
                    if node_count == 0:
                        cust_script += """
/usr/bin/kubectl --kubeconfig=/etc/kubernetes/admin.conf taint nodes --all node-role.kubernetes.io/master-
"""  # NOQA
                else:
                    cust_script += """
/usr/bin/kubeadm join --token {token} {ip}:6443
""".format(token=master_node['token'],
                               ip=master_node['ip'])
                if token_hash is not None:
                    cust_script += ' --discovery-token-ca-cert-hash ' + token_hash
                if cust_script is not None:
                    LOGGER.debug('about to execute on %s:\n%s' %
                                 (vm, cust_script))
                    vs.upload_file_to_guest(
                        vm,
                        'root',
                        password,
                        cust_script,
                        '/tmp/customize.sh')
                    vs.execute_program_in_guest(
                        vm,
                        'root',
                        password,
                         cmd_prefix+'chmod',
                        'u+rx /tmp/customize.sh',
                        wait_for_completion=True)
                    vs.execute_program_in_guest(
                        vm,
                        'root',
                        password,
                        '/tmp/customize.sh',
                        '',
                        wait_for_completion=True)
                    vs.execute_program_in_guest(
                        vm,
                        'root',
                        password,
                        cmd_prefix+'rm',
                        '-f /tmp/customize.sh',
                        wait_for_completion=True)
                    LOGGER.debug('executed on %s:\n%s' % (vm, cust_script))
            self.t = task.update(
                TaskStatus.SUCCESS.value,
                'vcloud.cse',
                self.op,
                'create cluster',
                '',
                None,
                'urn:cse:cluster:%s' % self.cluster_id,
                cluster_name,
                'application/vcloud.cse.cluster+xml',
                self.tenant_info['user_id'],
                self.tenant_info['user_name'],
                org_href=self.tenant_info['org_href'],
                task_href=self.t.get('href'))

    def get_cluster_config(self, cluster_name, headers, body):
        result = {}
        result['body'] = {}
        result['status_code'] = INTERNAL_SERVER_ERROR
        try:
            self._connect_tenant(headers)
            self.headers = headers
            self.cluster_name = cluster_name
            clusters = load_from_metadata(self.client_tenant,
                                          name=self.cluster_name,
                                          get_leader_ip=True)
            LOGGER.debug(clusters)
            assert len(clusters) == 1
            cluster = clusters[0]
            assert len(cluster['master_nodes']) == 1
            result['body'] = {'cluster_config': '\'%s\'' % cluster_name}
            vs = VSphere(self.config['vcs']['host'],
                         self.config['vcs']['username'],
                         self.config['vcs']['password'],
                         port=int(self.config['vcs']['port']))
            vs.connect()
            vm = vs.get_vm_by_moid(cluster['leader_moid'])
            response = vs.download_file_from_guest(
                                    vm,
                                    'root',
                                    self.config['broker']['password'],
                                    '/root/.kube/config')
            result['body'] = response.content.decode('utf-8')
            result['status_code'] = response.status_code
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            result['body'] = {'message': e.message}
        return result
