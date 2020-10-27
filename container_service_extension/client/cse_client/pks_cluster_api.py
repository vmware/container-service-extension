
import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.client.response_processor as response_processor  # noqa: E501
import container_service_extension.shared_constants as shared_constants


class PksClusterApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.PKS_URL_FRAGMENT}"
        self._clusters_uri = f"{self._uri}/clusters"
        self._cluster_uri = f"{self._uri}/cluster"

    def list_clusters(self, filters={}):
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            self._clusters_uri,
            self._client._session,
            accept_type='application/json',
            params=filters)
        return response_processor.process_response(response)

    def get_cluster(self, cluster_name, filters={}):
        uri = f'{self._cluster_uri}/{cluster_name}'
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            accept_type='application/json',
            params=filters)
        return response_processor.process_response(response)

    def create_cluster(self, cluster_name, ovdc_name, node_count=None, org_name=None):  # noqa: E501
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.ORG_NAME: org_name
        }
        uri = self._clusters_uri
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.POST,
            uri,
            self._client._session,
            contents=payload,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)

    def update_cluster(self, cluster_name, node_count, org_name=None,
                       ovdc_name=None):
        payload = {
            shared_constants.RequestKey.CLUSTER_NAME: cluster_name,
            shared_constants.RequestKey.NUM_WORKERS: node_count,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name
        }
        uri = f"{self._cluster_uri}/{cluster_name}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.PUT,
            uri,
            self._client._session,
            contents=payload,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)

    def delete_cluster(self, cluster_name, org_name=None, ovdc_name=None):
        uri = f"{self._cluster_uri}/{cluster_name}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.DELETE,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)

    def get_cluster_config(self, cluster_name, org_name=None, ovdc_name=None):
        uri = f"{self._cluster_uri}/{cluster_name}/config"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)
