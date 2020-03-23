# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.response_processor import process_response # noqa: E501
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RequestMethod


class PksCluster:
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/pks'

    def get_clusters(self, vdc=None, org=None):
        method = RequestMethod.GET
        uri = f"{self._uri}/clusters"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_cluster_info(self, name, org=None, vdc=None):
        method = RequestMethod.GET
        uri = f'{self._uri}/cluster/{name}'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def create_cluster(self,
                       vdc,
                       name,
                       node_count=None,
                       org=None):
        """Create a new Kubernetes cluster.

        :param vdc: (str): The name of the vdc in which the cluster will be
            created
        :param name: (str): The name of the cluster
        :param node_count: (str): Number of nodes
        :param org: (str): name of the organization in which the vdc to be
        used for cluster creation.

        :return: (json) A parsed json object describing the requested cluster.
        """
        method = RequestMethod.POST
        uri = f"{self._uri}/clusters"
        data = {
            RequestKey.CLUSTER_NAME: name,
            RequestKey.NUM_WORKERS: node_count,
            RequestKey.OVDC_NAME: vdc,
            RequestKey.ORG_NAME: org
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def resize_cluster(self,
                       cluster_name,
                       node_count,
                       org=None,
                       vdc=None):
        method = RequestMethod.PUT
        uri = f"{self._uri}/cluster/{cluster_name}"
        data = {
            RequestKey.CLUSTER_NAME: cluster_name,
            RequestKey.NUM_WORKERS: node_count,
            RequestKey.ORG_NAME: org,
            RequestKey.OVDC_NAME: vdc
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        method = RequestMethod.DELETE
        uri = f"{self._uri}/cluster/{cluster_name}"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        method = RequestMethod.GET
        uri = f"{self._uri}/cluster/{cluster_name}/config"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})

        return process_response(response)
