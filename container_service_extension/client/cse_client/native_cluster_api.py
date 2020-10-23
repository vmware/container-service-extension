from container_service_extension.client.cse_client.cse_client import CseClient

import pyvcloud.vcd.client as vcd_client

class NativeClusterApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/clusters"

    def get_cluster_by_id(self, cluster_id: str) -> dict:
        