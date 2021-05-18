# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from copy import deepcopy
import json
import logging
from urllib import parse

import requests

from container_service_extension.lib.cloudapi.constants import ResponseKeys


class CloudApiClient(object):
    """REST based client for cloudapi server."""

    def __init__(self,
                 base_url: str,
                 token: str,
                 is_jwt_token: str,
                 api_version: str,
                 logger_debug: logging.Logger,
                 logger_wire: logging.Logger,
                 verify_ssl: bool = True,
                 is_sys_admin: bool = False):
        if not base_url.endswith('/'):
            base_url += '/'
        self._base_url = base_url

        self._headers = {}
        if is_jwt_token:
            self._headers["Authorization"] = f"Bearer {token}"
        else:
            self._headers["x-vcloud-authorization"] = token
        self._headers["Accept"] = f"application/json;version={api_version}"
        self._headers["Content-Type"] = "application/json"

        self._verify_ssl = verify_ssl
        self.LOGGER = logger_debug
        self.LOGGER_WIRE = logger_wire
        self._last_response = None
        self.is_sys_admin = is_sys_admin
        self._api_version = api_version

    def get_api_version(self):
        return self._api_version

    def get_base_url(self):
        return self._base_url

    def get_last_response(self):
        return self._last_response

    def get_last_response_headers(self):
        if self._last_response:
            return self._last_response.headers

    def get_org_urn_from_id(self, org_id):
        return f"urn:vcloud:org:{org_id}"

    def do_request(self,
                   method,
                   cloudapi_version=None,
                   resource_url_relative_path=None,
                   resource_url_absolute_path=None,
                   payload=None,
                   content_type=None,
                   additional_request_headers=None,
                   return_response_headers=False):
        """Make a request to vCD server at /cloudapi endpoint.

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
        :param str content_type: content type of the body of the request
        :param dict additional_request_headers: request specific headers
        :param bool return_response_headers: should return response_headers?

        :return: body of the response text (JSON) in form of a dictionary and
            the response headers if return_headers is set

        :rtype: dict or (dict, dict)

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

        self.LOGGER_WIRE.debug(f"Request uri : {method.value.upper()} {url}")
        headers = deepcopy(self._headers)
        if additional_request_headers:
            headers.update(additional_request_headers)
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

        self.LOGGER_WIRE.debug("Request headers :"
                               f" {response.request.headers}")
        self.LOGGER_WIRE.debug(f"Request body : {response.request.body}")

        self.LOGGER_WIRE.debug(f"Response status code: {response.status_code}")
        self.LOGGER_WIRE.debug(f"Response headers : {response.headers}")
        self.LOGGER_WIRE.debug(f"Response body : {response.text}")

        response.raise_for_status()
        if response.text:
            if return_response_headers:
                return json.loads(response.text), response.headers
            else:
                return json.loads(response.text)
        elif return_response_headers:
            return None, response.headers

    def get_cursor_param(self) -> str:
        """Get cursor param from response header links.

        Example: Finding the next page link
        'https://XXX.com/cloudapi/1.0.0/edgeGateways/{gateway-id}}/nat/rules?cursor=abcde
        would return 'abcde'

        :return: cursor param
        :rtype: str
        """  # noqa: E501
        last_response_headers = self.get_last_response_headers()
        if not last_response_headers:
            return ''

        # Find link corresponding to the next page
        unparsed_links = last_response_headers[ResponseKeys.LINK]
        parsed_links = requests.utils.parse_header_links(unparsed_links)
        for link in parsed_links:
            if link[ResponseKeys.REL] == 'nextPage':
                # Parse cursor param
                cursor_url = link[ResponseKeys.URL]
                parsed_result: parse.ParseResult = parse.urlparse(cursor_url)
                parsed_query_map = parse.parse_qs(parsed_result.query)

                # The parse_qs function maps each query key to a list,
                # so we assume there is at most one cursor param and get that
                # element if the list is not empty
                cursor_list = parsed_query_map.get('cursor')
                if cursor_list:
                    return cursor_list[0]
                else:
                    return ''
        return ''
