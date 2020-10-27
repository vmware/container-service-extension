from dataclasses import asdict

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.client.response_processor as response_processor  # noqa: E501
import container_service_extension.def_.models as def_models
import container_service_extension.shared_constants as shared_constants


class NativeClusterApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}/{shared_constants.CSE_3_0_URL_FRAGMENT}"  # noqa: E501
        self._clusters_uri = f"{self._uri}/clusters"
        self._cluster_uri = f"{self._uri}/cluster"

    def create_cluster(self, cluster_entity_definition: def_models.ClusterEntity):  # noqa: E501
        cluster_entity_dict = asdict(cluster_entity_definition)
        uri = self._clusters_uri
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.POST,
            uri,
            self._client._session,
            contents=cluster_entity_dict,
            media_type='application/json',
            accept_type='application/json')
        return def_models.DefEntity(
            **response_processor.process_response(response))

    def update_cluster_by_cluster_id(self, cluster_id, cluster_entity_definition: def_models.ClusterEntity):  # noqa: E501
        cluster_entity_dict = asdict(cluster_entity_definition)
        uri = f"{self._cluster_uri}/{cluster_id}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.PUT,
            uri,
            self._client._session,
            contents=cluster_entity_dict,
            media_type='application/json',
            accept_type='application/json')
        return def_models.DefEntity(
            **response_processor.process_response(response))

    def delete_cluster_by_cluster_id(self, cluster_id):
        uri = f"{self._cluster_uri}/{cluster_id}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.DELETE,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return def_models.DefEntity(**response_processor.process_response(response))  # noqa: E501

    def delete_nfs_node_by_node_name(self, cluster_id: str, node_name: str):
        uri = f"{self._cluster_uri}/{cluster_id}/nfs/{node_name}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.DELETE,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return def_models.DefEntity(
            **response_processor.process_response(response))

    def get_cluster_config_by_cluster_id(self, cluster_id: str) -> dict:
        uri = f"{self._cluster_uri}/{cluster_id}/config"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)

    def get_upgrade_plan_by_cluster_id(self, cluster_id: str):
        uri = f'{self._cluster_uri}/{cluster_id}/upgrade-plan'
        return self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            accept_type='application/json')

    def upgrade_cluster_by_cluster_id(self, cluster_id: str,
                                      cluster_upgrade_definition: def_models.DefEntity):  # noqa: E501
        uri = f'{self._uri}/cluster/{cluster_id}/action/upgrade'
        entity_dict = asdict(cluster_upgrade_definition.entity)
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.POST,
            uri,
            self._client._session,
            contents=entity_dict,
            media_type='application/json',
            accept_type='application/json')
        return def_models.DefEntity(
            **response_processor.process_response(response))
