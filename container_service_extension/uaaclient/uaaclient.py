# container-service-extension
# This file is a modified version of https://github.com/dattnguyen82/PyUaaClient/blob/master/PyUaaClient.py
# The license agreement is still being worked on.

import requests
import json
import base64


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