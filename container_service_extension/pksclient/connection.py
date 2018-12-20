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
        self.authString = base64.b64encode(auth.encode())
        self.authString = b'Basic ' + self.authString

    def getToken(self):
        url = self.baseUrl + self.tokenService

        headers = {
            'content-type': "application/x-www-form-urlencoded",
            'authorization': self.authString,
            'cache-control': "no-cache"

        }
        http_proxy = f"http://10.161.148.112:80"
        proxy_env = {
            'http_proxy': http_proxy,
            'https_proxy': http_proxy,
            'http': http_proxy,
            'https': http_proxy,
        }

        response = requests.request("POST", url, verify=False, data=self.payload, headers=headers, proxies=proxy_env)

        access_token = json.loads(response.text)

        return access_token['access_token']



uaaClient = UaaClient('https://api.pks.local:8443', 'admin', 'YtAU6Rl2dEvj1_hH9wEQxDUkxO1Lcjm3')
token = uaaClient.getToken()
print(token)

config = Configuration()
config.proxy = 'http://10.161.148.112:80'
config.host = 'https://api.pks.local:9021/v1'
config.access_token = token
config.username = 'admin'
config.verify_ssl = False

pksClient = ApiClient(configuration=config)

clusterApi = ClusterApi(api_client=pksClient)
clusters = clusterApi.list_clusters()
print(clusters)
#plansApi = PlansApi(api_client=pksClient)
#plans = plansApi.list_plans()
