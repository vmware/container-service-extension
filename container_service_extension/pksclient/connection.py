import requests
import json
import base64
from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pksclient.api_client import ApiClient
from container_service_extension.pksclient.api.plans_api import PlansApi
from container_service_extension.pksclient.api.cluster_api import ClusterApi


class UaaClient:

    tokenService = '/oauth/token'
    baseUrl = ''
    clientId = ''
    clientSecret = ''
    payload = "grant_type=client_credentials"
    authString = ''

    def __init__(self, baseUrl, clientId, clientSecret):
        self.baseUrl = baseUrl
        self.clientId = clientId
        self.clientSecret = clientSecret
        auth = self.clientId + ':' + self.clientSecret
        self.authString = base64.b64encode(auth)
        self.authString = 'Basic ' + self.authString

    def getToken(self):
        url = self.baseUrl + self.tokenService

        headers = {
            'content-type': "application/x-www-form-urlencoded",
            'authorization': self.authString,
            'cache-control': "no-cache"

        }

        response = requests.request("POST", url, verify=False, data=self.payload, headers=headers)

        access_token = json.loads(response.text)

        return access_token['access_token']



uaaClient = UaaClient('https://api.pks.local:8443', 'admin', 'VqROLWFRunBghy_GIjfHzOwBm82bAWVg')
token = uaaClient.getToken()
print(token)

config = Configuration()
config.host = 'https://api.pks.local:9021/v1'
config.access_token = token
config.username = 'admin'
config.verify_ssl = False

pksClient = ApiClient(configuration=config)

clusterApi = ClusterApi(api_client=pksClient)
clusters = clusterApi.list_clusters()
#plansApi = PlansApi(api_client=pksClient)
#plans = plansApi.list_plans()
