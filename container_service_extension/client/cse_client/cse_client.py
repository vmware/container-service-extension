import pyvcloud.vcd.client as vcd_client
import container_service_extension.shared_constants as shared_constants

class CseClient:
    def __init__(self, client: vcd_client.Client):
        self._client = client
        self._uri = f"{self._client.get_api_uri()}/{shared_constants.CSE_URL_FRAGMENT}/{shared_constants.CSE_3_0_URL_FRAGMENT}"
