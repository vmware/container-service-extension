# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from copy import deepcopy
import json

import requests


class CloudApiClient(object):
    """REST based client for cloudapi server."""

    def __init__(self,
                 base_url,
                 token,
                 is_jwt_token,
                 api_version,
                 verify_ssl=True,
                 logger_instance=None,
                 log_requests=False,
                 log_headers=False,
                 log_body=False):
        if not base_url.endswith('/'):
            base_url += '/'
        self._base_url = base_url

        self._headers = {}
        if is_jwt_token:
            self._headers["Authorization"] = f"Bearer {token}"
        else:
            self._headers["x-vcloud-authorization"] = token
        self._headers["Accept"] = f"application/json;version={api_version}"

        self._verify_ssl = verify_ssl
        self.LOGGER = logger_instance
        self._log_requests = log_requests
        self._log_headers = log_headers
        self._log_body = log_body
        self._last_response = None

    def get_base_url(self):
        return self._base_url

    def get_last_response(self):
        return self._last_response

    def get_last_response_headers(self):
        if self._last_response:
            return self._last_response.headers
        else:
            return None

    def do_request(self,
                   method,
                   cloudapi_version=None,
                   resource_url_relative_path=None,
                   resource_url_absolute_path=None,
                   payload=None,
                   content_type=None):
        """Make a request to cloudpai server.

        :param shared_constants.RequestMethod method: One of the HTTP verb
            defined in the enum.
        :param str cloudapi_version: cloudapi version that's part of the url
            e.g. 1.0.0 in /cloudapi/1.0.0/vdcComputePolicies
        :param str resource_url_relative_path: part of the url that identifies
            just the resource (the host and the common /cloudapi/ should be
            omitted). E.g .vdcComputePolicies,
            vdcComputePolicies/urn:vcloud:vdcComputePolicy:ac313b07-21df-45d2
            etc.
        :param str resource_url_absolute_path: absolute path for a resource,
            e.g. https://<vcd fqdn>/transfer/{id}/{file name}
        :param dict payload: JSON payload for the REST call.

        :return: body of the response text (JSON) in form of a dictionary.

        :rtype: dict

        :raises HTTPError: if the underlying REST call fails.
        """
        # TODO pagination support in relative resource path
        if resource_url_absolute_path:
            url = resource_url_absolute_path
        else:
            url = self._base_url
            if cloudapi_version:
                url += f"{cloudapi_version}/"
            url += f"{resource_url_relative_path}"

        headers = deepcopy(self._headers)
        if content_type and 'json' not in content_type:
            headers['Content-type'] = content_type
            response = requests.request(
                method.value,
                url,
                headers=headers,
                data=payload,
                verify=self._verify_ssl)
        else:
            response = requests.request(
                method.value,
                url,
                headers=headers,
                json=payload,
                verify=self._verify_ssl)
        self._last_response = response

        if self._log_requests:
            self.LOGGER.debug(f"Request uri : {(method.value).upper()} {url}")
            if self._log_headers:
                self.LOGGER.debug("Request hedears : "
                                  f"{response.request.headers}")
            if self._log_body and payload:
                self.LOGGER.debug(f"Request body : {response.request.body}")

        if self._log_requests:
            self.LOGGER.debug(f"Response status code: {response.status_code}")
            if self._log_headers:
                self.LOGGER.debug(f"Response hedears : {response.headers}")
            if self._log_body:
                self.LOGGER.debug(f"Response body : {response.text}")

        response.raise_for_status()

        if response.text:
            return json.loads(response.text)
