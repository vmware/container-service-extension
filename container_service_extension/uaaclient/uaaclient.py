# container-service-extension
# This file is a modified version of https://github.com/dattnguyen82/
# PyUaaClient/blob/master/PyUaaClient.py
# The license agreement is still being worked on.

import base64
import json

import requests


class UaaClient(object):

    tokenService = '/oauth/token'
    baseUrl = ''
    clientId = ''
    clientSecret = ''
    payload = "grant_type=client_credentials"
    authString = ''

    def __init__(self, baseUrl, clientId, clientSecret, proxy_uri=None):
        self.baseUrl = baseUrl
        self.clientId = clientId
        self.clientSecret = clientSecret
        self.proxy_uri = proxy_uri
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
        proxy_env={}
        if self.proxy_uri is not None:
            proxy_env = {
                'http_proxy': self.proxy_uri,
                'https_proxy': self.proxy_uri,
                'http': self.proxy_uri,
                'https': self.proxy_uri,
            }

        response = requests.request("POST", url, verify=False,
                                    data=self.payload, headers=headers,
                                    proxies=proxy_env)

        access_token = json.loads(response.text)

        return access_token['access_token']
