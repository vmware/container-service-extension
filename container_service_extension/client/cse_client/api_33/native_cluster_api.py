# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class NativeClusterApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}"
        self._native_clusters_uri = f"{self._uri}/nativeclusters"
        self._cluster_uri = f"{self._uri}/cluster"
        self._clusters_uri = f"{self._uri}/clusters"
        self._node_uri = f"{self._uri}/node"
        self._nodes_uri = f"{self._uri}/nodes"

    def get_all_clusters(self, filters=None):
        processed_filters = {}
        if filters:
            processed_filters = {
                k: v for k, v in filters.items() if v is not None}
        processed_filters[shared_constants.PaginationKey.PAGE_SIZE.value] = \
            self._request_page_size

        return self.iterate_results(
            self._native_clusters_uri, filters=processed_filters)

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

    def get_cluster_upgrade_plan(self, cluster_name, filters=None):
        if filters is None:
            filters = {}
        uri = f'{self._cluster_uri}/{cluster_name}/upgrade-plan'
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            params=filters,
            accept_type='application/json')
        return self.process_response(response)

    def upgrade_cluster(self, cluster_name, template_name, template_revision,
                        org_name=None, ovdc_name=None):
        uri = f'{self._cluster_uri}/{cluster_name}/action/upgrade'
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.TEMPLATE_NAME: template_name,
            shared_constants.RequestKey.TEMPLATE_REVISION: template_revision,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
        }
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.POST,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)

    def create_cluster(self, cluster_name, ovdc_name, network_name, node_count=None,  # noqa: E501
                       org_name=None, cpu=None, memory=None,
                       storage_profile=None, ssh_key=None, template_name=None,
                       template_revision=None, enable_nfs=False, rollback=True):  # noqa: E501
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.NUM_CPU: cpu,
            shared_constants.RequestKey.MB_MEMORY: memory,
            shared_constants.RequestKey.NETWORK_NAME: network_name,
            shared_constants.RequestKey.STORAGE_PROFILE_NAME: storage_profile,
            shared_constants.RequestKey.SSH_KEY: ssh_key,
            shared_constants.RequestKey.TEMPLATE_NAME: template_name,
            shared_constants.RequestKey.TEMPLATE_REVISION: template_revision,
            shared_constants.RequestKey.ENABLE_NFS: enable_nfs,
            shared_constants.RequestKey.ROLLBACK: rollback,
            shared_constants.RequestKey.ORG_NAME: org_name
        }
        response = self.do_request(
            uri=self._clusters_uri,
            method=shared_constants.RequestMethod.POST,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)

    def update_cluster(self, cluster_name, network_name, node_count,
                       org_name=None, ovdc_name=None, template_name=None,
                       template_revision=None, cpu=None, memory=None,
                       ssh_key=None, rollback=True):
        uri = f"{self._cluster_uri}/{cluster_name}"
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.NETWORK_NAME: network_name,
            shared_constants.RequestKey.ROLLBACK: rollback,
            shared_constants.RequestKey.TEMPLATE_NAME: template_name,
            shared_constants.RequestKey.TEMPLATE_REVISION: template_revision,
            shared_constants.RequestKey.NUM_CPU: cpu,
            shared_constants.RequestKey.MB_MEMORY: memory,
            shared_constants.RequestKey.SSH_KEY: ssh_key
        }
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)

    def delete_cluster(self, cluster_name, filters=None):
        if filters is None:
            filters = {}
        uri = f"{self._cluster_uri}/{cluster_name}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.DELETE,
            params=filters,
            accept_type='application/json')
        return self.process_response(response)

    def get_cluster_config(self, cluster_name, filters=None):
        if filters is None:
            filters = {}
        uri = f"{self._cluster_uri}/{cluster_name}/config"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            params=filters,
            accept_type='application/json')
        return self.process_response(response)

    def add_node(self, cluster_name, network_name, node_count=1, org_name=None,
                 ovdc_name=None, cpu=None, memory=None, storage_profile=None,
                 ssh_key=None, template_name=None, template_revision=None,
                 enable_nfs=False, rollback=True):
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.NUM_CPU: cpu,
            shared_constants.RequestKey.MB_MEMORY: memory,
            shared_constants.RequestKey.NETWORK_NAME: network_name,
            shared_constants.RequestKey.STORAGE_PROFILE_NAME: storage_profile,
            shared_constants.RequestKey.SSH_KEY: ssh_key,
            shared_constants.RequestKey.TEMPLATE_NAME: template_name,
            shared_constants.RequestKey.TEMPLATE_REVISION: template_revision,
            shared_constants.RequestKey.ENABLE_NFS: enable_nfs,
            shared_constants.RequestKey.ROLLBACK: rollback
        }
        response = self.do_request(
            uri=self._nodes_uri,
            method=shared_constants.RequestMethod.POST,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)

    def get_node_info(self, cluster_name, node_name, filters=None):
        if filters is None:
            filters = {}
        uri = f"{self._node_uri}/{node_name}"
        filters[shared_constants.RequestKey.CLUSTER_NAME] = cluster_name
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            params=filters,
            accept_type='application/json')
        return self.process_response(response)

    def delete_nodes(self, cluster_name, nodes_list,
                     org_name=None, ovdc_name=None):
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.NODE_NAMES_LIST: nodes_list
        }
        response = self.do_request(
            uri=self._nodes_uri,
            method=shared_constants.RequestMethod.DELETE,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)
