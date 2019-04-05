# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

import requests
from requests.auth import HTTPBasicAuth

from container_service_extension.logger import SERVER_NSXT_LOGGER as LOGGER


class NSXTClient(object):
    """."""

    def __init__(self,
                 host,
                 username,
                 password,
                 http_proxy=None,
                 https_proxy=None,
                 verify_ssl=True,
                 log_requests=False,
                 log_headers=False,
                 log_body=False):
        self._base_url = f"https://{host}/api/v1/"
        self._auth = HTTPBasicAuth(username, password)
        self._proxies = {}
        if http_proxy is not None:
            self._proxies['http'] = http_proxy
        if https_proxy is not None:
            self._proxies['https'] = https_proxy
        self._verify_ssl = verify_ssl
        self._log_requests = log_requests
        self._log_headers = log_headers
        self._log_body = log_body

    def do_request(self, method, resource_url_fragment, payload=None):
        url = self._base_url + resource_url_fragment

        response = requests.request(
            method.value,
            url,
            auth=self._auth,
            json=payload,
            proxies=self._proxies,
            verify=self._verify_ssl)

        if self._log_requests:
            LOGGER.debug(f"Request uri : {(method.value).upper()} {url}")
            if self._log_headers:
                LOGGER.debug(f"Request hedears : {response.request.headers}")
            if self._log_body and payload is not None:
                LOGGER.debug(f"Request body : {response.request.body}")

        if self._log_requests:
            LOGGER.debug(f"Response status code: {response.status_code}")
            if self._log_headers:
                LOGGER.debug(f"Response hedears : {response.headers}")
            if self._log_body:
                LOGGER.debug(f"Response body : {response.text}")

        response.raise_for_status()

        if response.text:
            return json.loads(response.text)

