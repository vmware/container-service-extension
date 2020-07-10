from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.configuration import Configuration
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster

tkg_config = Configuration()

tkg_config.host = f"https://bos1-vcd-sp-static-200-99.eng.vmware.com/cloudapi/1.0.0/"
tkg_config.verify_ssl = False
token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZG1pbmlzdHJhdG9yIiwiaXNzIjoiYTkzYzlkYjktNzQ3MS0zMTkyLThkMDktYThmN2VlZGE4NWY5QGRmNzNjODc3LTg4ZWQtNDgwZC1hMzgxLTA4NzE4NWQzYjc5NiIsImV4cCI6MTU5NjkyNTM4MCwidmVyc2lvbiI6InZjbG91ZF8xLjAiLCJqdGkiOiI2N2E1ZjgyMzkwYWI0NWY5OTdlNjZhYmEwMWY4MjQ5MiJ9.RBGKBt6GDTl0uaanwFOm7zBnZ2dstI82S8KSKsZONO5yMRb2Ke1Iyz9OpvwqP4RbxT3p3oqOyW1mVcBclz4fGbz5LCll8vqMuE85saz-RuMFNyYF-kC6fQEKBDQZstGaM7WBtPPHZYqWcqhMSxUo_IxtQECWz69-gNAAj2zBYEjlTEsB4F7iqPIvRFq1rRA8YLmunin0Gy2WYokN6AuT2ZB1v8LI4RNT54wXi4OAm4MAWO0pFdyyCpJxQm4VDjMw2OgCMaWXq-mpwMQJRXo99WcXfReXmkcNbd29LDgZ1m7FSHmdVewpyYDgmPpbxje5vHWBhXnEEp8a46KAuFzkjg"
client = ApiClient(configuration=tkg_config)
client.set_default_header("Accept", f"application/json;version=35.0")
client.set_default_header("Authorization", f"Bearer {token}")
#client.set_default_header("x-vcloud-authorization", "3ef3162574b840919b9d3e4c691b8c9b")
api = TkgClusterApi(api_client=client)
# Returns tuple of response_data, response_status, response_headers
response = api.get_tkg_cluster(id='urn:vcloud:entity:vmware:tkgcluster:1.0.0:99007f07-d069-49ec-b745-c83e49645a85')
cluster: TkgCluster = response[0]

print(cluster.metadata.name)
