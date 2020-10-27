import pyvcloud.vcd.client as vcd_client


class CseClient:
    def __init__(self, client: vcd_client.Client):
        self._client = client
        self._uri = self._client.get_api_uri()
