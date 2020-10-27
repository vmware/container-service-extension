import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
from container_service_extension.client.response_processor import process_response  # noqa: E501
import container_service_extension.shared_constants as shared_constants


class OvdcApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}"
        self._ovdcs_uri = f"{self._uri}/ovdcs"
        self._ovdc_uri = f"{self._uri}/ovdc"

    def list_ovdcs(self, filters={}):
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            self._ovdcs_uri,
            self._client._session,
            accept_type='application/json',
            params=filters)
        return process_response(response)

    def get_ovdc(self, ovdc_id):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            accept_type='application/json')
        return process_response(response)

    def update_ovdc_compute_policies(self, ovdc_id, compute_policy_name,
                                     compute_policy_action, force_remove=False):  # noqa: E501
        uri = f"{self._ovdc_uri}/{ovdc_id}/compute-policies"
        payload = {
            shared_constants.RequestKey.OVDC_ID: ovdc_id, # also exists in url
            shared_constants.RequestKey.COMPUTE_POLICY_NAME: compute_policy_name,  # noqa: E501
            shared_constants.RequestKey.COMPUTE_POLICY_ACTION: compute_policy_action,  # noqa: E501
            shared_constants.RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS: force_remove  # noqa: E501
        }
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.PUT,
            uri,
            self._client._session,
            contents=payload,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def list_ovdc_compute_policies(self, ovdc_id):
        uri = f'{self._ovdc_uri}/{ovdc_id}/compute-policies'
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            accept_type='application/json')
        return process_response(response)
