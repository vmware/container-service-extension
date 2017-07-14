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
from vc_adapter import VC_Adapter

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

    success = False
    operation_description = 'creating cluster %s (%s)' % \
        (cluster_name, cluster_id)
    LOGGER.debug(operation_description)
    try:
        adapter = VC_Adapter(vca_system, prov)
        kov_input = adapter.get_create_params(body)

        time.sleep(5)
        raise Exception('not implemented')
    except Exception as e:
        success = False
        operation_description = 'failed to create cluster %s: %s' % \
            (cluster_name, str(e).replace('"', ''))
        LOGGER.error(traceback.format_exc())

    status = 'success' if success else 'error'
    create_or_update_task(task,
                          operation_description,
                          cluster_name,
                          cluster_id,
                          status,
                          prov,
                          task_id=task_id)


def process_delete_cluster_thread(details,
                                  body,
                                  prov,
                                  task,
                                  task_id,
                                  vca_system,
                                  config):
    success = False
    cluster_name = details['name']
    cluster_id = details['cluster_id']
    operation_description = 'deleting cluster %s (%s)' % \
        (cluster_name, cluster_id)
    LOGGER.debug(operation_description)
    try:
        adapter = VC_Adapter(vca_system, prov)
        kov_input = adapter.get_delete_params(body)

        time.sleep(5)
        raise Exception('not implemented')
    except Exception as e:
        success = False
        operation_description = 'failed to delete cluster %s (%s): %s' % \
            (cluster_name, cluster_id, str(e).replace('"', ''))
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
        cluster_op = None
        cluster_id = None
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
        result['body'] = []
        result['status_code'] = OK
        return result

    def create_cluster(self, body, prov):
        result = {}
        result['body'] = {}
        cluster_name = body['name']
        node_count = body['node_count']
        LOGGER.debug('about to create cluster with %s nodes', node_count)
        result['body'] = 'can''t create cluster'
        result['status_code'] = INTERNAL_SERVER_ERROR
        if prov.connect():
            if not prov.validate_name(cluster_name):
                result['body'] = {'message': 'name is not valid'}
                return result
            if prov.search_by_name(cluster_name)['cluster_id'] is not None:
                result['body'] = {'message': 'cluster already exists'}
                return result
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
            operation_description = 'creating cluster %s (%s)' % \
                (cluster_name, cluster_id)
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
            response_body['name'] = cluster_name
            response_body['cluster_id'] = cluster_id
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
        LOGGER.debug('about to delete cluster with id: %s', cluster_id)
        result['status_code'] = INTERNAL_SERVER_ERROR
        if prov.connect():
            details = prov.search_by_id(cluster_id)
            if details['name'] is None:
                result['body'] = {'message': 'cluster not found'}
                return result
            cluster_name = details['cluster']
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
            operation_description = 'deleting cluster %s (%s)' % \
                (cluster_name, cluster_id)
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
            response_body['name'] = cluster_name
            response_body['cluster_id'] = cluster_id
            response_body['task_id'] = t.get_id().split(':')[-1]
            response_body['status'] = status
            response_body['progress'] = None
            result['body'] = response_body
            result['status_code'] = ACCEPTED

            t = Thread(target=process_delete_cluster_thread,
                       args=(details, body, prov, task,
                             response_body['task_id'], vca_system,
                             self.config, ))
            t.daemon = True
            t.start()

        return result
