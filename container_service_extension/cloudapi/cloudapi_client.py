# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

import requests

from container_service_extension.cloudapi.constants \
    import CLOUDAPI_DEFAULT_VERSION


class CloudApiClient(object):
    """REST based client for cloudapi server."""

    def __init__(self,
                 base_url,
                 token,
                 is_jwt_token,
                 verify_ssl=True,
                 api_version=CLOUDAPI_DEFAULT_VERSION,
                 logger_instance=None,
                 log_requests=False,
                 log_headers=False,
                 log_body=False):
        self._base_url = base_url
        self._versioned_url = f"{self._base_url}/{api_version}/"
        if is_jwt_token:
            self._headers = {"Authorization": f"Bearer {token}"}
        else:
            self._headers = {"x-vcloud-authorization": token}
        self._verify_ssl = verify_ssl
        self.LOGGER = logger_instance
        self._log_requests = log_requests
        self._log_headers = log_headers
        self._log_body = log_body

    def get_versioned_url(self):
        return self._versioned_url

    def do_request(self, method, resource_url_relative_path=None,
                   payload=None):
        """Make a request to cloudpai server.

        :param shared_constants.RequestMethod method: One of the HTTP verb
        defined in the enum.
        :param str resource_url_relative_path: part of the url that identifies
        just the resource (the host and the common /cloudapi/1.0.0 should be
        omitted). E.g .vdcComputePolicies,
        vdcComputePolicies/urn:vcloud:vdcComputePolicy:ac313b07-21df-45d2 etc.
        :param dict payload: JSON payload for the REST call.

        :return: body of the response text (JSON) in form of a dictionary.

        :rtype: dict

        :raises HTTPError: if the underlying REST call fails.
        """
        # TODO this only sends a request to the first page found.
        # TODO this should instead be able to deal with pagination
        url = f"{self._versioned_url}{resource_url_relative_path}"

        response = requests.request(
            method.value,
            url,
            headers=self._headers,
            json=payload,
            verify=self._verify_ssl)

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
