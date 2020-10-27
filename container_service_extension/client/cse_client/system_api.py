import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
from container_service_extension.client.response_processor import process_response  # noqa: E501
import container_service_extension.shared_constants as shared_constants


class SystemApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}"
        self._system_uri = f"{self._uri}/system"

    def get_system_details(self):
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            self._system_uri,
            self._client._session,
            accept_type='application/json')
        return process_response(response)

    def update_system(self, action):
        payload = {
            shared_constants.RequestKey.SERVER_ACTION: action
        }
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.PUT,
            self._system_uri,
            self._client._session,
            contents=payload,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)
