# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
from cluster import Cluster
from cluster import Node
import json
import logging
from provisioner import Provisioner
from pyvcloud.vcloudair import VCA
from pyvcloud.task import Task
from task import create_or_update_task
from threading import Thread
import time
import traceback
import uuid

LOGGER = logging.getLogger(__name__)

OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_SERVER_ERROR = 500


def process_create_cluster_thread(cluster_id,
                                  body,
                                  prov,
                                  task,
                                  task_id,
                                  vca_system,
                                  config):
    cluster_name = body['name']
    node_count = body['node_count']
    vdc_name = body['vdc']
    network_name = body['network']

    cluster = Cluster(cluster_name, cluster_id)
    master = Node('%s-m-%02d' % (cluster_name, 1), node_type='master')
    cluster.master_nodes = [master]
    cluster.nodes = []

    for n in range(node_count):
        node = Node('%s-%02d' % (cluster_name, n+1))
        cluster.nodes.append(node)

    success = False
    try:
        all_nodes = cluster.master_nodes + cluster.nodes
        for node in all_nodes:
            status = 'running'
            operation_description = 'creating cluster %s' % \
                                    (cluster_name)
            create_or_update_task(task,
                                  operation_description,
                                  cluster_name,
                                  cluster_id,
                                  status,
                                  prov,
                                  task_id=task_id)
            vm = node.name
            if node.node_type == 'master':
                template = 'template_master'
            else:
                template = 'template_node'
            node.task_id, node.href = prov.create_vm(
                    config['service']['catalog'],
                    config['service'][template],
                    vdc_name,
                    vm,
                    network_name,
                    None,
                    node.node_type)
        success = False
        error = False
        while not success and not error:
            if len(all_nodes) == 0:
                raise Exception('no nodes were created')
            success = True
            error = False
            for node in all_nodes:
                status = prov.get_task_status(node.task_id)
                success = success and status == 'success'
                error = error or (status != 'success' and status != 'running')
                LOGGER.debug('node: %s, task: %s' % (node.name, status))
                time.sleep(1)

        operation_description = 'created cluster %s' % cluster_name
    except Exception as e:
        success = False
        operation_description = 'failed to create cluster %s: %s' % \
            (cluster_name, str(e).replace('"', ''))
        LOGGER.error(traceback.format_exc())

    cluster.update_vm_tags(vca_system)

    status = 'success' if success else 'error'
    create_or_update_task(task,
                          operation_description,
                          cluster_name,
                          cluster_id,
                          status,
                          prov,
                          task_id=task_id)


def process_delete_cluster_thread(cluster_id,
                                  body,
                                  prov,
                                  task,
                                  task_id,
                                  vca_system,
                                  config):
    clusters = Cluster.load_from_metadata(prov.vca_tenant)
    success = False
    operation_description = 'deleting cluster %s' % cluster_id
    cluster_name = cluster_id
    LOGGER.debug(operation_description)
    try:
        all_nodes = []
        for cluster in clusters:
            if cluster.cluster_id == cluster_id:
                all_nodes = cluster.master_nodes + cluster.nodes
                for node in all_nodes:
                    LOGGER.debug('deleting vm %s %s (%s)',
                                 node.name, node.node_type, cluster.vdc)
                    node.task_id = prov.delete_vm(cluster.vdc, node.name)
        success = False
        error = False
        while not success and not error:
            if len(all_nodes) == 0:
                raise Exception(
                    'cluster does not exist or does not have any nodes')
            success = True
            error = False
            for node in all_nodes:
                status = prov.get_task_status(node.task_id)
                success = success and status == 'success'
                error = error or (status != 'success' and status != 'running')
                LOGGER.debug('node: %s, task: %s' % (node.name, status))
                time.sleep(1)

        operation_description = 'deleted cluster %s' % cluster_name
    except Exception as e:
        success = False
        operation_description = 'failed to delete cluster %s: %s' % \
            (cluster_id, str(e).replace('"', ''))
        LOGGER.error(traceback.format_exc())

    status = 'success' if success else 'error'
    create_or_update_task(task,
                          operation_description,
                          cluster_name,
                          cluster_id,
                          status,
                          prov,
                          task_id=task_id)


class ServiceProcessor(object):

    def __init__(self, config, verify, log):
        self.config = config
        self.verify = verify
        self.log = log

    def process_request(self, body):
        LOGGER.debug(json.dumps(body))
        reply = {}
        request_headers = body['headers']
        request_host = request_headers['Host']
        request_vcloud_token = request_headers['x-vcloud-authorization']
        requestUri = body['requestUri']
        request_version = request_headers['Accept'].split('version=')[-1]
        tokens = requestUri.split('/')
        cluster_id = None
        cluster_op = None
        if len(tokens) > 3:
            cluster_id = tokens[3]
            if cluster_id == '':
                cluster_id = None
        if len(tokens) > 4:
            cluster_op = tokens[4]
            if cluster_op == '':
                cluster_op = None
        if len(body['body']) > 0:
            try:
                request_body = json.loads(base64.b64decode(body['body']))
            except:
                request_body = None
        else:
            request_body = None
        try:
            prov = Provisioner(request_host, request_vcloud_token,
                               request_version, self.verify, self.log)
            r = prov.connect()
            assert(r)
            request_username = prov.vca_tenant.vcloud_session.username
            request_org_id = prov.vca_tenant.vcloud_session.org_id
        except:
            prov = None
            request_username = None
            request_org_id = None
            tb = traceback.format_exc()
            LOGGER.error(tb)
        if body['method'] == 'GET':
            if cluster_id is None:
                reply = self.list_clusters(prov)
        elif body['method'] == 'POST':
            if cluster_id is None:
                reply = self.create_cluster(request_body, prov)
        elif body['method'] == 'DELETE':
            reply = self.delete_cluster(request_body, prov, cluster_id)
        LOGGER.debug('---\nid=%s\nmethod=%s\nuser=%s\norg_id=%s\n'
                     'vcloud_token=%s\ncluster_id=%s\ncluster_op=%s' %
                     (body['id'], body['method'], request_username,
                      request_org_id, request_vcloud_token, cluster_id,
                      cluster_op))
        LOGGER.debug('request:\n%s' % json.dumps(request_body))
        return reply

    def list_clusters(self, prov):
        result = {}
        result['body'] = Cluster.load_from_metadata(prov.vca_tenant)
        result['status_code'] = OK
        return result

    def create_cluster(self, body, prov):
        result = {}
        result['body'] = {}
        cluster_name = body['name']
        node_count = body['node_count']
        LOGGER.debug('about to create cluster with %s nodes', node_count)
        result['status_code'] = INTERNAL_SERVER_ERROR
        if prov.connect():
            vca_system = VCA(host=self.config['vcd']['host'],
                             username=self.config['vcd']['username'],
                             service_type='standalone',
                             version=self.config['vcd']['api_version'],
                             verify=self.config['vcd']['verify'],
                             log=self.config['vcd']['log'])

            org_url = 'https://%s/cloud' % self.config['vcd']['host']
            r = vca_system.login(password=self.config['vcd']['password'],
                                 org='System',
                                 org_url=org_url)
            if not r:
                return result
            r = vca_system.login(token=vca_system.token,
                                 org='System',
                                 org_url=vca_system.vcloud_session.org_url)
            if not r:
                return result
            task = Task(session=vca_system.vcloud_session,
                        verify=self.config['vcd']['verify'],
                        log=self.config['vcd']['log'])
            cluster_id = str(uuid.uuid4())
            operation_description = 'creating cluster %s' % cluster_name
            LOGGER.info(operation_description)
            status = 'running'
            t = create_or_update_task(task,
                                      operation_description,
                                      cluster_name,
                                      cluster_id,
                                      status,
                                      prov)
            if t is None:
                return result
            response_body = {}
            response_body['id'] = cluster_id
            response_body['name'] = cluster_name
            response_body['task_id'] = t.get_id().split(':')[-1]
            response_body['status'] = status
            response_body['progress'] = None
            result['body'] = response_body
            result['status_code'] = ACCEPTED

            t = Thread(target=process_create_cluster_thread,
                       args=(cluster_id, body, prov, task,
                             response_body['task_id'], vca_system,
                             self.config, ))
            t.daemon = True
            t.start()

        return result

    def delete_cluster(self, body, prov, cluster_id):
        result = {}
        result['body'] = {}
        LOGGER.debug('about to delete cluster with id=%s', cluster_id)
        result['status_code'] = INTERNAL_SERVER_ERROR
        if prov.connect():
            vca_system = VCA(host=self.config['vcd']['host'],
                             username=self.config['vcd']['username'],
                             service_type='standalone',
                             version=self.config['vcd']['api_version'],
                             verify=self.config['vcd']['verify'],
                             log=self.config['vcd']['log'])

            org_url = 'https://%s/cloud' % self.config['vcd']['host']
            r = vca_system.login(password=self.config['vcd']['password'],
                                 org='System',
                                 org_url=org_url)
            if not r:
                return result
            r = vca_system.login(token=vca_system.token,
                                 org='System',
                                 org_url=vca_system.vcloud_session.org_url)
            if not r:
                return result
            task = Task(session=vca_system.vcloud_session,
                        verify=self.config['vcd']['verify'],
                        log=self.config['vcd']['log'])
            cluster_name = cluster_id
            operation_description = 'deleting cluster %s' % cluster_id
            LOGGER.info(operation_description)
            status = 'running'
            t = create_or_update_task(task,
                                      operation_description,
                                      cluster_name,
                                      cluster_id,
                                      status,
                                      prov)
            if t is None:
                return result
            response_body = {}
            response_body['id'] = cluster_id
            response_body['task_id'] = t.get_id().split(':')[-1]
            response_body['status'] = status
            response_body['progress'] = None
            result['body'] = response_body
            result['status_code'] = ACCEPTED

            t = Thread(target=process_delete_cluster_thread,
                       args=(cluster_id, body, prov, task,
                             response_body['task_id'], vca_system,
                             self.config, ))
            t.daemon = True
            t.start()

        return result
