# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.response_processor import process_response # noqa: E501
import container_service_extension.shared_constants as shared_constants


class PksCluster:
    def __init__(self, client):
        self.client = client
        self._uri = f"{self.client.get_api_uri()}/{shared_constants.PKS_URL_FRAGMENT}"  # noqa: E501

    def get_clusters(self, vdc=None, org=None):
        method = shared_constants.RequestMethod.GET
        uri = f"{self._uri}/clusters"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={shared_constants.RequestKey.ORG_NAME: org,
                    shared_constants.RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_cluster_info(self, name, org=None, vdc=None):
        method = shared_constants.RequestMethod.GET
        uri = f'{self._uri}/cluster/{name}'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={shared_constants.RequestKey.ORG_NAME: org,
                    shared_constants.RequestKey.OVDC_NAME: vdc})
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
        method = shared_constants.RequestMethod.POST
        uri = f"{self._uri}/clusters"
        data = {
            shared_constants.RequestKey.CLUSTER_NAME: name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.OVDC_NAME: vdc,
            shared_constants.RequestKey.ORG_NAME: org
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
        method = shared_constants.RequestMethod.PUT
        uri = f"{self._uri}/cluster/{cluster_name}"
        data = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.ORG_NAME: org,
            shared_constants.RequestKey.OVDC_NAME: vdc
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
        method = shared_constants.RequestMethod.DELETE
        uri = f"{self._uri}/cluster/{cluster_name}"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={shared_constants.RequestKey.ORG_NAME: org,
                    shared_constants.RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        method = shared_constants.RequestMethod.GET
        uri = f"{self._uri}/cluster/{cluster_name}/config"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={shared_constants.RequestKey.ORG_NAME: org,
                    shared_constants.RequestKey.OVDC_NAME: vdc})

        return process_response(response)
