# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import pkg_resources, os
from cluster import Cluster
from cluster import Node
from cluster import TYPE_MASTER
import json
import logging
from provisioner import Provisioner
from pyvcloud.task import Task
from task import create_or_update_task
from task import update_task_thread
from threading import Thread
import traceback
import uuid
from vc_adapter import VC_Adapter

LOGGER = logging.getLogger(__name__)

OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_SERVER_ERROR = 500

OP_CREATE_CLUSTER = 'CLUSTER_CREATE'
OP_DELETE_CLUSTER = 'CLUSTER_DELETE'


class ServiceProcessor(object):

    def __init__(self, config, cove, verify, log):
        self.config = config
        self.cove = cove
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
        get_swagger_json=False
        get_swagger_yaml = False
        if len(tokens) > 3:
            cluster_id = tokens[3]
            if cluster_id == '':
                cluster_id = None
            if cluster_id == 'swagger.json':
                get_swagger_json = True
                cluster_id = None
            if cluster_id == 'swagger.yaml':
                get_swagger_yaml = True
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
            vca_system = Provisioner.get_system_session(self.config)
            vc_adapter = VC_Adapter(self.config, vca_system, prov)
        except:
            prov = None
            request_username = None
            request_org_id = None
            vca_system = None
            vc_adapter = None
            LOGGER.error(traceback.format_exc())
        if body['method'] == 'GET':
            if get_swagger_json==True:
                reply = self.get_swagger_json_file()
            elif get_swagger_yaml ==True:
                reply = self.get_swagger_yaml_file()
            elif cluster_id is None:
                reply = self.list_clusters(prov, vca_system, vc_adapter)
        elif body['method'] == 'POST':
            if cluster_id is None:
                reply = self.create_cluster(request_body, prov,
                                            vca_system, vc_adapter)
        elif body['method'] == 'DELETE':
            reply = self.delete_cluster(request_body, prov,
                                        vca_system, vc_adapter, cluster_id)
        LOGGER.debug('---\nid=%s\nmethod=%s\nuser=%s\norg_id=%s\n'
                     'vcloud_token=%s\ncluster_id=%s\ncluster_op=%s' %
                     (body['id'], body['method'], request_username,
                      request_org_id, request_vcloud_token, cluster_id,
                      cluster_op))
        LOGGER.debug('request:\n%s' % json.dumps(request_body))
        return reply

    def get_swagger_json_file(self):
        file_path='/usr/local/swagger/swagger.yaml'
        yamlresponse=None
        if os.path.exists(file_path):
            with open(file_path, 'r') as fi:
                yamlresponse=yaml.load(fi)
        elif os.path.exists('usr/swagger/swagger.yaml'):
            with open('usr/swagger/swagger.yaml', 'r') as fi:
                yamlresponse=yaml.load(fi)
        else:
            raise Exception("Swagger file not found")
        jsonresponse=yaml.dump(yamlresponse)
        realResponse={}
        realResponse['body']=jsonresponse
        realResponse['status_code'] = OK
        return realResponse

    def get_swagger_yaml_file(self):
        file_path='/usr/local/swagger/swagger.yaml'
        yamlresponse=None
        if os.path.exists(file_path):
            with open(file_path, 'r') as fi:
                yamlresponse=yaml.load(fi)
        elif os.path.exists('usr/swagger/swagger.yaml'):
            with open('usr/swagger/swagger.yaml', 'r') as fi:
                yamlresponse=yaml.load(fi)
        else:
            raise Exception("Swagger file not found")
        realResponse={}
        realResponse['body']=yamlresponse
        realResponse['status_code'] = OK
        return realResponse

    def list_clusters(self, prov, vca_system, vc_adapter):
        result = {}
        clusters = []
        try:
            cluster_list = self.cove.get_clusters(vc_adapter.get_list_params())
            for cluster in cluster_list:
                c = Cluster('')
                c.cluster_id = cluster.name
                if cluster.numMasters:
                    for n in range(cluster.numMasters):
                        node = Node('', TYPE_MASTER)
                        c.master_nodes.append(node)
                if cluster.numWorkers:
                    for n in range(cluster.numWorkers):
                        node = Node('')
                        c.nodes.append(node)
                c.status = cluster.status
                c.leader_endpoint = cluster.leaderEndpoint
                clusters.append(c)
            result['body'] = clusters
            result['status_code'] = OK
        except Exception:
            LOGGER.error(traceback.format_exc())
            result['body'] = []
            result['status_code'] = INTERNAL_SERVER_ERROR
            result['message'] = traceback.format_exc()
        return result

    def create_cluster(self, body, prov, vca_system, vc_adapter):
        result = {}
        result['body'] = {}
        cluster_name = body['name']
        node_count = body['node_count']
        LOGGER.debug('about to create cluster with %s nodes', node_count)
        result['body'] = 'can''t create cluster'
        result['status_code'] = INTERNAL_SERVER_ERROR
        if not prov.validate_name(cluster_name):
            result['body'] = {'message': 'name is not valid'}
            return result
        if prov.search_by_name(cluster_name)['cluster_id'] is not None:
            result['body'] = {'message': 'cluster already exists'}
            return result
        cluster_id = str(uuid.uuid4())
        create_params = vc_adapter.get_create_params(body, cluster_id)
        try:
            cove_task_id = self.cove.create_cluster(create_params[0],
                                                    create_params[1])
        except Exception:
            result['body'] = 'can''t create cluster on Cove'
            LOGGER.error(traceback.format_exc())
            return result
        # TODO (update VDC metadata with cluster_id/name)
        task = Task(session=vca_system.vcloud_session,
                    verify=self.config['vcd']['verify'],
                    log=self.config['vcd']['log'])
        operation_description = 'creating cluster %s (%s)' % \
            (cluster_name, cluster_id)
        LOGGER.info(operation_description)
        status = 'running'
        details = '{"name": "%s", "cove_task_id": "%s"}' % \
                  (cluster_name, cove_task_id)
        t = create_or_update_task(task,
                                  OP_CREATE_CLUSTER,
                                  operation_description,
                                  cluster_name,
                                  cluster_id,
                                  status,
                                  details,
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
        t = Thread(target=update_task_thread,
                   args=(task,
                         OP_CREATE_CLUSTER,
                         operation_description,
                         cluster_name,
                         cluster_id,
                         status,
                         details,
                         prov,
                         self.cove,
                         response_body['task_id'],
                         )
                   )
        t.daemon = True
        t.start()
        return result

    def delete_cluster(self, body, prov, vca_system, vc_adapter, cluster_id):
        result = {}
        result['body'] = {}
        LOGGER.debug('about to delete cluster with id: %s', cluster_id)
        result['status_code'] = INTERNAL_SERVER_ERROR
        details = prov.search_by_id(cluster_id)
        if details['name'] is None:
            result['body'] = {'message': 'cluster not found'}
            return result
        cluster_name = details['name']
        delete_params = vc_adapter.get_delete_params(body, cluster_id)
        try:
            cove_task_id = self.cove.delete_cluster(delete_params[0],
                                                    delete_params[1])
        except Exception:
            result['body'] = 'can''t delete cluster on Cove'
            LOGGER.error(traceback.format_exc())
            return result
        # TODO (delete VDC metadata related to the cluster_id/name)
        task = Task(session=vca_system.vcloud_session,
                    verify=self.config['vcd']['verify'],
                    log=self.config['vcd']['log'])
        operation_description = 'deleting cluster %s (%s)' % \
            (cluster_name, cluster_id)
        LOGGER.info(operation_description)
        status = 'running'
        details = '{"name": "%s", "cove_task_id": "%s"}' % \
                  (cluster_name, cove_task_id)
        t = create_or_update_task(task,
                                  OP_DELETE_CLUSTER,
                                  operation_description,
                                  cluster_name,
                                  cluster_id,
                                  status,
                                  details,
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

        t = Thread(target=update_task_thread,
                   args=(task,
                         OP_DELETE_CLUSTER,
                         operation_description,
                         cluster_name,
                         cluster_id,
                         status,
                         details,
                         prov,
                         self.cove,
                         response_body['task_id'],
                         )
                   )
        t.daemon = True
        t.start()
        return result
