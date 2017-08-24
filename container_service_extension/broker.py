# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import load_from_metadata_by_id
from container_service_extension.cluster import TYPE_NODE
from container_service_extension.cluster import TYPE_MASTER
import logging
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
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

OP_CREATE_CLUSTER = 'CLUSTER_CREATE'
OP_DELETE_CLUSTER = 'CLUSTER_DELETE'


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
        # print(client._get_wk_endpoint(_WellKnownEndpoint.LOGGED_IN_ORG))
        return {'user_name': session.get('user'),
                'org_name': session.get('org')}

    def _validate_name(self, name):
        """
        Validates that the cluster name against the pattern.
        """
        # TODO (validate against pattern)
        # pattern = '^[a-zA-Z](([-0-9a-zA-Z]+)?[0-9a-zA-Z])?(\.[a-zA-Z](([-0-9a-zA-Z]+)?[0-9a-zA-Z])?)*$'  # NOQA
        return True

    def _search_by_name(self, name):
        """
        check that the cluster name exists in the current VDC.
        It exists, it returns the cluster id
        """
        return None

    def _search_by_id(self, cluster_id):
        """
        check that the cluster with cluster_id exists in the current VDC.
        It exists, it returns the cluster name and details.
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
        result['body'] = 'can''t create cluster'
        result['status_code'] = INTERNAL_SERVER_ERROR
        # if not self.provisioner.validate_name(cluster_name):
        #     result['body'] = {'message': 'name is not valid'}
        #     return result
        # if self.provisioner.search_by_name(cluster_name) is not None:
        #     result['body'] = {'message': 'cluster already exists'}
        #     return result
        try:
            # self._connect_sysadmin()
            self._connect_tenant(headers)
            self.headers = headers
            self.body = body
            self.cluster_id = str(uuid.uuid4())
            self.op = OP_CREATE_CLUSTER
            self.daemon = True
            self.start()
            response_body = {}
            response_body['name'] = cluster_name
            response_body['cluster_id'] = self.cluster_id
            # response_body['task_id'] = create_task.get_id().split(':')[-1]
            # response_body['status'] = status
            # response_body['progress'] = None
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = e.message
            LOGGER.error(traceback.format_exc())
        return result

    def create_cluster_thread(self):
        org_resource = self.client_tenant.get_org()
        org = Org(self.client_tenant, org_resource=org_resource)
        vdc_resource = org.get_vdc(self.body['vdc'])

        cluster_name = self.body['name']
        master_count = 1
        node_count = int(self.body['node_count'])
        catalog = self.config['broker']['catalog']
        master_template = self.config['broker']['master_template']
        node_template = self.config['broker']['node_template']

        vdc = VDC(self.client_tenant, vdc_resource=vdc_resource)

        masters = []
        for n in range(master_count):
            time.sleep(1)
            name = cluster_name + '-m%s' % str(n+1)
            masters.append(vdc.instantiate_vapp(name,
                                                catalog,
                                                master_template))
        nodes = []
        for n in range(node_count):
            time.sleep(1)
            name = cluster_name + '-n%s' % str(n+1)
            nodes.append(vdc.instantiate_vapp(name, catalog, node_template))

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
                    for k, v in tags.items():
                        vapp = VApp(self.client_tenant,
                                    vapp_href=node.get('href'))
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
                except:
                    LOGGER.error(
                        'can''t tag %s at this moment, will retry later',
                        node.get('name'))
                    LOGGER.error(traceback.format_exc())
                    time.sleep(1)

    def delete_cluster(self, cluster_id, headers, body):
        result = {}
        result['body'] = {}
        LOGGER.debug('about to delete cluster with id: %s', cluster_id)
        result['status_code'] = INTERNAL_SERVER_ERROR
        # details = self.provisioner.search_by_id(cluster_id)
        # if details is None or details['name'] is None:
        #     result['body'] = {'message': 'cluster not found'}
        #     return result
        # cluster_name = details['name']
        try:
            # self._connect_sysadmin()
            self._connect_tenant(headers)
            self.headers = headers
            self.body = body
            self.cluster_id = cluster_id
            self.op = OP_DELETE_CLUSTER
            self.daemon = True
            self.start()
            response_body = {}
            response_body['cluster_id'] = self.cluster_id
            # response_body['task_id'] = create_task.get_id().split(':')[-1]
            result['body'] = response_body
            result['status_code'] = ACCEPTED
        except Exception as e:
            result['body'] = e.message
            LOGGER.error(traceback.format_exc())
        return result

    def delete_cluster_thread(self):
        print('about to delete cluster %s' % self.cluster_id)
        nodes = load_from_metadata_by_id(self.client_tenant, self.cluster_id)
        vdc = None
        for node in nodes:
            if vdc is None:
                vdc = VDC(self.client_tenant, vdc_href=node['vdc_href'])
            LOGGER.debug('about to delete vapp %s', node['vapp_name'])
            vdc.delete_vapp(node['vapp_name'], force=True)
            time.sleep(1)
