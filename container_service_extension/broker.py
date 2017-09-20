# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import load_from_metadata_by_id
from container_service_extension.cluster import load_from_metadata_by_name
from container_service_extension.cluster import TYPE_MASTER
from container_service_extension.cluster import TYPE_NODE
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


LOGGER = logging.getLogger(__name__)


OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_SERVER_ERROR = 500

OP_CREATE_CLUSTER = 'create_cluster'
OP_DELETE_CLUSTER = 'delete_cluster'

MAX_HOST_NAME_LENGTH = 25 - 4


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
        if name[-1] == ".":
            name = name[:-1]
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in name.split("."))

    def _search_by_name(self, name):
        """check that the cluster name exists in the current VDC.

        If exists, it returns the cluster id.

        """
        return None

    def _search_by_id(self, cluster_id):
        """check that the cluster with cluster_id exists in the current VDC.

        If exists, it returns the cluster name and details.

        """
        return None

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
            clusters = load_from_metadata(self.client_tenant)
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
        LOGGER.debug('about to create cluster %s on %s with %s nodes',
                     cluster_name,
                     vdc_name,
                     node_count)
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

        task = Task(self.client_sysadmin)
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
        org = Org(self.client_tenant, org_resource=org_resource)
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

        vdc = VDC(self.client_tenant, vdc_resource=vdc_resource)

        masters = []
        for n in range(master_count):
            time.sleep(1)
            name = cluster_name + '-m%s' % str(n+1)
            masters.append(vdc.instantiate_vapp(name,
                                                catalog,
                                                master_template,
                                                memory=master_mem,
                                                cpu=master_cpu))
        nodes = []
        for n in range(node_count):
            time.sleep(1)
            name = cluster_name + '-n%s' % str(n+1)
            nodes.append(vdc.instantiate_vapp(name,
                                              catalog,
                                              node_template,
                                              memory=node_mem,
                                              cpu=node_cpu))

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
            time.sleep(15)
            if node is not None:
                LOGGER.debug('about to tag %s, href=%s',
                             node.get('name'),
                             node.get('href'))
                try:
                    tags = {}
                    tags['cse.cluster.id'] = self.cluster_id
                    tags['cse.node.type'] = node_type
                    tags['cse.cluster.name'] = cluster_name
                    vapp = VApp(self.client_tenant,
                                vapp_href=node.get('href'))
                    for k, v in tags.items():
                        task = vapp.set_metadata('GENERAL', 'READWRITE', k, v)
                        self.client_tenant.get_task_monitor().\
                            wait_for_status(
                                task=task,
                                timeout=600,
                                poll_frequency=5,
                                fail_on_status=None,
                                expected_target_statuses=[TaskStatus.SUCCESS],
                                callback=None)
                    tagged.update([node.get('name')])
                    LOGGER.debug('tagged %s', node.get('name'))
                except Exception:
                    LOGGER.error(
                        'can''t tag %s at this moment, will retry later',
                        node.get('name'))
                    LOGGER.error(traceback.format_exc())
                    time.sleep(1)
        time.sleep(4)
        self.customize_nodes()

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
            self.cluster_id = '?'
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
        nodes = load_from_metadata_by_name(self.client_tenant,
                                           self.cluster_name)
        vdc = None
        tasks = []
        for node in nodes:
            if vdc is None:
                vdc = VDC(self.client_tenant, vdc_href=node['vdc_href'])
            LOGGER.debug('about to delete vapp %s', node['vapp_name'])
            try:
                tasks.append(vdc.delete_vapp(node['vapp_name'], force=True))
            except Exception:
                pass
            time.sleep(1)
        task = Task(self.client_sysadmin)
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

    def customize_nodes(self, max_retries=60):
        cluster_name = self.body['name']
        node_count = int(self.body['node_count'])
        task = Task(self.client_sysadmin)
        self.t = task.update(
            TaskStatus.RUNNING.value,
            'vcloud.cse',
            'Customizing nodes %s(%s)' % (cluster_name, self.cluster_id),
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
                nodes = load_from_metadata_by_id(self.client_tenant,
                                                 self.cluster_id)
                LOGGER.debug(nodes)
                for node in nodes:
                    if 'ip' in node.keys() and len(node['ip']) > 0:
                        pass
                    else:
                        n += 1
                        raise Exception('missing ip, retry %s', n)
                all_nodes_configured = True
                break
            except Exception as e:
                LOGGER.error(e.message)
                time.sleep(5)
        if not all_nodes_configured:
            LOGGER.error('ip not configured in at least one node')
            return
        LOGGER.debug('ip configured in all nodes')
        vs = VSphere(self.config['vcs']['host'],
                     self.config['vcs']['username'],
                     self.config['vcs']['password'],
                     port=int(self.config['vcs']['port']))
        vs.connect()
        master_node = None
        for node in nodes:
            vm = vs.get_vm_by_moid(node['moid'])
            commands = [
                ['/bin/echo', '\'127.0.0.1    localhost\' | sudo tee /etc/hosts'],  # NOQA
                ['/bin/echo', '\'127.0.1.1    %s\' | sudo tee -a /etc/hosts' % node['vapp_name']],  # NOQA
                ['/bin/echo', '\'::1          localhost ip6-localhost ip6-loopback\' | sudo tee -a /etc/hosts'],  # NOQA
                ['/bin/echo', '\'ff02::1      ip6-allnodes\' | sudo tee -a /etc/hosts'],  # NOQA
                ['/bin/echo', '\'ff02::2      ip6-allrouters\' | sudo tee -a /etc/hosts'],  # NOQA
                ['/usr/bin/sudo', 'hostnamectl set-hostname %s' % node['vapp_name']],  # NOQA
                ['/bin/mkdir', '$HOME/.ssh'],
                ['/bin/chmod', 'go-rwx $HOME/.ssh'],
                ['/bin/echo', '\'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDFS5HL4CBlWrZscohhqdVwUa815Pi3NaCijfdvs0xCNF2oP458Xb3qYdEmuFWgtl3kEM4hR60/Tzk7qr3dmAfY7GPqdGhQsZEnvUJq0bfDAh0KqhdrqiIqx9zlKWnR65gl/u7Qkck2jiKkqjfxZwmJcuVCu+zQZCRC80XKwpyOudLKd/zJz9tzJxJ7+yltu9rNdshCEfP+OR1QoY2hFRH1qaDHTIbDdlF/m0FavapH7+ScufOY/HNSSYH7/SchsxK3zywOwGV1e1z//HHYaj19A3UiNdOqLkitKxFQrtSyDfClZ/0SwaVxh4jqrKuJ5NT1fbN2bpDWMgffzD9WWWZbDvtYQnl+dBjDnzBZGo8miJ87lYiYH9N9kQfxXkkyPziAjWj8KZ8bYQWJrEQennFzsbbreE8NtjsM059RXz0kRGeKs82rHf0mTZltokAHjoO5GmBZb8sZTdZyjfo0PTgaNCENe0bRDTrAomM99LhW2sJ5ZjK7SIqpWFaU+P+qgj4s88btCPGSqnh0Fea1foSo5G57l5YvfYpJalW0IeiynrO7TRuxEVV58DJNbYyMCvcZutuyvNq0OpEQYXRM2vMLQX3ZX3YhHMTlSXXcriqvhOJ7aoNae5aiPSlXvgFi/wP1x1aGYMEsiqrjNnrflGk9pIqniXsJ/9TFwRh9m4GktQ== contact@pacogomez.com\' > $HOME/.ssh/authorized_keys'],   # NOQA
                ['/bin/chmod', 'go-rwx $HOME/.ssh/authorized_keys']
            ]
            if node['node_type'] == TYPE_MASTER:
                master_node = node
                commands.append(['/bin/rm', '-f /tmp/kubeadm-init.out'])
                commands.append(['/usr/bin/sudo', '/usr/bin/kubeadm init --pod-network-cidr=10.244.0.0/16 --apiserver-advertise-address={ip} > /tmp/kubeadm-init.out'.format(ip=node['ip'])])  # NOQA
            for command in commands:
                LOGGER.debug('executing %s %s on %s',
                             command[0],
                             command[1],
                             vm)
                result = vs.execute_program_in_guest(
                            vm,
                            self.config['broker']['username'],
                            self.config['broker']['password'],
                            command[0],
                            command[1],
                            wait_for_completion=True)
                LOGGER.debug('executed %s %s on %s: %s',
                             command[0],
                             command[1],
                             vm,
                             result)
        if master_node is not None:
            vm = vs.get_vm_by_moid(master_node['moid'])
            response = vs.download_file_from_guest(
                        vm,
                        self.config['broker']['username'],
                        self.config['broker']['password'],
                        '/tmp/kubeadm-init.out'
                        )
            token = [x for x in response.content.splitlines() if x.strip().startswith('[token] Using token: ')][0].split()[-1]  # NOQA
            cmd = '/usr/bin/sudo'
            args = '/usr/bin/kubeadm join --token %s %s:6443' % (token, master_node['ip'])  # NOQA
            for node in nodes:
                vm = vs.get_vm_by_moid(node['moid'])
                if node['node_type'] == TYPE_NODE:
                    LOGGER.debug('executing %s %s on %s', cmd, args, vm)
                    cmd = '/usr/bin/sudo'
                    result = vs.execute_program_in_guest(
                                vm,
                                self.config['broker']['username'],
                                self.config['broker']['password'],
                                cmd,
                                args,
                                wait_for_completion=True
                            )
                    LOGGER.debug('executed %s %s on %s: %s',
                                 cmd,
                                 args,
                                 vm,
                                 result)
                elif node['node_type'] == TYPE_MASTER:
                    commands = [
                            # ['/usr/bin/sudo', 'kubectl --kubeconfig=/etc/kubernetes/admin.conf taint nodes --all node-role.kubernetes.io/master-'],  # NOQA
                            ['/usr/bin/sudo', 'kubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel-rbac.yml'],  # NOQA
                            ['/usr/bin/sudo', 'kubectl --kubeconfig=/etc/kubernetes/admin.conf create -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml']  # NOQA
                        ]
                    if node_count == 0:
                        commands.append(['/usr/bin/sudo', 'kubectl --kubeconfig=/etc/kubernetes/admin.conf taint nodes --all node-role.kubernetes.io/master-'])  # NOQA
                    for command in commands:
                        LOGGER.debug('executing %s %s on %s',
                                     command[0],
                                     command[1],
                                     vm)
                        result = vs.execute_program_in_guest(
                                    vm,
                                    self.config['broker']['username'],
                                    self.config['broker']['password'],
                                    command[0],
                                    command[1],
                                    wait_for_completion=True)
                        LOGGER.debug('executed %s %s on %s: %s',
                                     command[0],
                                     command[1],
                                     vm,
                                     result)
            task = Task(self.client_sysadmin)
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
            nodes = load_from_metadata_by_name(self.client_tenant,
                                               self.cluster_name)
            LOGGER.debug(nodes)
            result['body'] = {'cluster_config': '\'%s\'' % cluster_name}
            for node in nodes:
                if node['node_type'] == TYPE_MASTER:
                    vs = VSphere(self.config['vcs']['host'],
                                 self.config['vcs']['username'],
                                 self.config['vcs']['password'],
                                 port=int(self.config['vcs']['port']))
                    vs.connect()
                    vm = vs.get_vm_by_moid(node['moid'])
                    commands = [
                        ['/usr/bin/sudo', 'chmod a+r /etc/kubernetes/admin.conf']  # NOQA
                    ]
                    for command in commands:
                        LOGGER.debug('executing %s on %s', command[0], vm)
                        r = vs.execute_program_in_guest(
                                    vm,
                                    self.config['broker']['username'],
                                    self.config['broker']['password'],
                                    command[0],
                                    command[1]
                                )
                        time.sleep(1)
                        LOGGER.debug('executed %s on %s: %s',
                                     command[0],
                                     vm,
                                     r)
                    response = vs.download_file_from_guest(
                                            vm,
                                            self.config['broker']['username'],
                                            self.config['broker']['password'],
                                            '/etc/kubernetes/admin.conf')
                    result['body'] = response.content
                    result['status_code'] = response.status_code
                    break
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            result['body'] = {'message': e.message}
        return result
