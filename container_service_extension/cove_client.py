# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from bravado.client import SwaggerClient
from bravado.requests_client import RequestsClient
import requests

TIMEOUT_SECONDS = 20


class CoveClient(object):

    def __init__(self, host, port, verify):
        self.host = host
        self.port = port
        self.verify = verify
        self.client = None

    def connect(self):
        response = requests.get(
            'https://%s:%s/swagger.json' % (self.host, self.port),
            verify=self.verify)
        if response.status_code == requests.status_codes.codes.OK:
            spec = response.json()
            spec['host'] = '%s:%s' % (self.host, self.port)
            http_client = RequestsClient()
            http_client.session.verify = self.verify
            config = {
                'validate_swagger_spec': True
            }
            self.client = SwaggerClient.from_spec(spec,
                                                  http_client=http_client,
                                                  config=config)
        else:
            raise Exception(response)

    def _request_options(self, vc_info=None):
        opt = {'connect_timeout': TIMEOUT_SECONDS,
               'timeout': TIMEOUT_SECONDS}
        if vc_info is not None:
            opt['headers'] = {'X-VC-Username': vc_info['username'],
                              'X-VC-Password': vc_info['password'],
                              'X-VC-Endpoint': '%s:%s' % (vc_info['host'],
                                                          vc_info['port']),
                              'X-VC-Thumbprint': vc_info['thumbprint']}
        return opt

    def get_clusters(self, vc_info):
        clusters = self.client.clusters.listClusters(
            _request_options=self._request_options(vc_info)).result(
                timeout=TIMEOUT_SECONDS)
        for cluster in clusters:
            if len(cluster.name) > 2:
                cluster.name = cluster.name[2:]
        return clusters

    def create_cluster(self, vc_info, cluster_config):
        return self.client.clusters.createCluster(
            _request_options=self._request_options(vc_info),
            clusterConfig=cluster_config).result(timeout=TIMEOUT_SECONDS)

    def delete_cluster(self, vc_info, cluster_id):
        return self.client.clusters.deleteCluster(
            _request_options=self._request_options(vc_info),
            name=cluster_id).result(timeout=TIMEOUT_SECONDS)

    def get_task(self, task_id):
        return self.client.tasks.getTask(
            taskid=task_id,
            _request_options=self._request_options()).result(
                timeout=TIMEOUT_SECONDS)

    def get_tasks(self):
        return self.client.tasks.listTaskIDs(
                _request_options=self._request_options).result(
                    timeout=TIMEOUT_SECONDS)
