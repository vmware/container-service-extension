# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from typing import Dict, List

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.rde.models.common_models as common_models


class NativeClusterApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}/{ shared_constants.CSE_3_0_URL_FRAGMENT}"  # noqa: E501
        self._clusters_uri = f"{self._uri}/clusters"
        self._cluster_uri = f"{self._uri}/cluster"
        self._request_page_size = 10

    def create_cluster(self, cluster_create_spec: dict):
        """Call create native cluster CSE server endpoint.

        :param dict cluster_create_spec: Cluster create specification
        :return: defined entity object representing the response
        :rtype: common_models.DefEntity
        """
        uri = self._clusters_uri
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.POST,
            accept_type='application/json',
            media_type='application/json',
            payload=cluster_create_spec)

        return common_models.DefEntity(**self.process_response(response))

    def update_cluster_by_cluster_id(self, cluster_id: str, cluster_update_spec: dict):  # noqa: E501
        """Call update native cluster CSE server endpoint.

        :param str cluster_id: ID of the cluster
        :param dict cluster_update_spec: Update cluster specification
        :return: defined entity object representing the response
        :rtype: common_models.DefEntity
        """
        uri = f"{self._cluster_uri}/{cluster_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=cluster_update_spec)

        return common_models.DefEntity(**self.process_response(response))

    def delete_cluster_by_cluster_id(self, cluster_id):
        uri = f"{self._cluster_uri}/{cluster_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.DELETE,
            accept_type='application/json')

        return common_models.DefEntity(**self.process_response(response))

    def delete_nfs_node_by_node_name(self, cluster_id: str, node_name: str):
        uri = f"{self._cluster_uri}/{cluster_id}/nfs/{node_name}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.DELETE,
            accept_type='application/json')

        return common_models.DefEntity(**self.process_response(response))

    def get_cluster_config_by_cluster_id(self, cluster_id: str) -> dict:
        uri = f"{self._cluster_uri}/{cluster_id}/config"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')

        return self.process_response(response)

    def get_upgrade_plan_by_cluster_id(self, cluster_id: str):
        uri = f'{self._cluster_uri}/{cluster_id}/upgrade-plan'
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')

        return self.process_response(response)

    def upgrade_cluster_by_cluster_id(self, cluster_id: str,
                                      cluster_upgrade_definition: common_models.DefEntity):  # noqa: E501
        uri = f'{self._uri}/cluster/{cluster_id}/action/upgrade'
        entity_dict = cluster_upgrade_definition.entity.to_dict()
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.POST,
            accept_type='application/json',
            media_type='application/json',
            payload=entity_dict)

        return common_models.DefEntity(**self.process_response(response))

    def get_single_page_cluster_acl(self, cluster_id,
                                    page=shared_constants.CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                    page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE):  # noqa: E501
        query_uri = f"{self._cluster_uri}/{cluster_id}/acl"
        filters = {
            shared_constants.PaginationKey.PAGE_NUMBER: page,
            shared_constants.PaginationKey.PAGE_SIZE: page_size
        }
        response = self.do_request(
            uri=query_uri,
            method=shared_constants.RequestMethod.GET,
            params=filters,
            accept_type='application/json')

        return self.process_response(response)

    def list_native_cluster_acl_entries(self, cluster_id):
        page_num = 0
        while True:
            page_num += 1
            acl_response = self.get_single_page_cluster_acl(
                cluster_id=cluster_id,
                page=page_num,
                page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE)
            acl_values = acl_response['values']
            if len(acl_values) == 0:
                break
            for acl_value in acl_values:
                yield common_models.ClusterAclEntry(**acl_value)

    def put_cluster_acl(self, cluster_id: str, acl_entries: List[Dict]):
        uri = f'{self._cluster_uri}/{cluster_id}/acl'
        payload = {
            shared_constants.ClusterAclKey.ACCESS_SETTING: acl_entries
        }
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)

        self.process_response(response)
