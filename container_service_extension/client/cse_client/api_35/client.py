import pyvcloud.vcd.client as vcd_client


class CseClientV35:
    def __init__(self, client: vcd_client.Client):
        self._client = client
        self._uri = f"{self._client.get_api_uri()}/{shared_constants.CSE_URL_FRAGMENT}/{shared_constants.CSE_3_0_URL_FRAGMENT}"  # noqa: E501
