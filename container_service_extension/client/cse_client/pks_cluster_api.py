# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class PksClusterApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.PKS_URL_FRAGMENT}"
        self._clusters_uri = f"{self._uri}/clusters"
        self._cluster_uri = f"{self._uri}/cluster"

    def list_clusters(self, filters=None):
        if filters is None:
            filters = {}
        response = self.do_request(
            uri=self._clusters_uri,
            method=shared_constants.RequestMethod.GET,
            params=filters,
            accept_type='application/json')
        return self.process_response(response)

    def get_cluster(self, cluster_name, filters=None):
        if filters is None:
            filters = {}
        uri = f'{self._cluster_uri}/{cluster_name}'
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            params=filters,
            accept_type='application/json')
        return self.process_response(response)

    def create_cluster(self, cluster_name, ovdc_name, node_count=None, org_name=None):  # noqa: E501
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.ORG_NAME: org_name
        }
        response = self.do_request(
            uri=self._clusters_uri,
            method=shared_constants.RequestMethod.POST,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)

    def update_cluster(self, cluster_name, node_count, org_name=None,
                       ovdc_name=None):
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name
        }
        uri = f"{self._cluster_uri}/{cluster_name}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)

    def delete_cluster(self, cluster_name, org_name=None, ovdc_name=None):
        uri = f"{self._cluster_uri}/{cluster_name}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.DELETE,
            accept_type='application/json')
        return self.process_response(response)

    def get_cluster_config(self, cluster_name, org_name=None, ovdc_name=None):
        uri = f"{self._cluster_uri}/{cluster_name}/config"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')
        return self.process_response(response)
