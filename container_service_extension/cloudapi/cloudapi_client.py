# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from http import HTTPStatus
import json

import requests
from requests.exceptions import RequestException

from container_service_extension.cloudapi.constants \
    import CLOUDAPI_DEFAULT_VERSION
from container_service_extension.cloudapi.constants import CLOUDAPI_ROOT
from container_service_extension.shared_constants import RequestMethod


class CloudApiClient(object):
    """REST based client for cloudapi server."""

    def __init__(self,
                 host,
                 auth_token,
                 verify_ssl=True,
                 api_version=CLOUDAPI_DEFAULT_VERSION,
                 logger_instance=None,
                 log_requests=False,
                 log_headers=False,
                 log_body=False):
        self._base_url = f"https://{host}/{CLOUDAPI_ROOT}/"
        self._versioned_url = f"{self._base_url}{api_version}/"
        self._headers = {"x-vcloud-authorization": auth_token}
        self._verify_ssl = verify_ssl
        if logger_instance:
            self.LOGGER = logger_instance
        else:
            from container_service_extension.logger import SERVER_LOGGER
            self.LOGGER = SERVER_LOGGER
        self._log_requests = log_requests
        self._log_headers = log_headers
        self._log_body = log_body

    def test_connectivity(self):
        """Test connectivity to the openapi server.

        :return: True, if server is alive, else False

        :rtype: bool
        """
        try:
            self.do_request(RequestMethod.GET)
        except RequestException as err:
            print(err)
            if err.response is not None and \
                    (err.response.status_code == HTTPStatus.NOT_FOUND):
                return True
            else:
                return False
        except Exception as err:
            print(err)
            return False

    def do_request(self, method, resource_url_relative_path=None,
                   payload=None):
        """Make a request to cloudpai server.

        :param shared_constants.RequestMethodVerb method: One of the HTTP verb
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
        if resource_url_relative_path:
            url = f"{self._versioned_url}{resource_url_relative_path}"
        else:
            url = self._base_url

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
