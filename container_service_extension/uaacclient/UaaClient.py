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
        self.authString = base64.b64encode(auth)
        self.authString = 'Basic ' + self.authString

    def getToken(self):
        url = self.baseUrl + self.tokenService

        headers = {
            'content-type': "application/x-www-form-urlencoded",
            'authorization': self.authString,
            'cache-control': "no-cache"
        }

        response = requests.request("POST", url, data=self.payload, headers=headers)

        access_token = json.loads(response.text)

        return access_token['access_token']