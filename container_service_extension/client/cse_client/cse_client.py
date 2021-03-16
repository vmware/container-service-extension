# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import os

import pyvcloud.vcd.client as vcd_client
import requests

import container_service_extension.client.constants as cli_constants
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.utils.core_utils import str_to_bool
from container_service_extension.exception.exceptions import CseResponseError
from container_service_extension.exception.minor_error_codes import MinorErrorCode  # noqa: E501
from container_service_extension.logging.logger import CLIENT_WIRE_LOGGER
from container_service_extension.logging.logger import NULL_LOGGER

wire_logger = NULL_LOGGER
if str_to_bool(os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING)):
    wire_logger = CLIENT_WIRE_LOGGER


def _deserialize_response_content(response):
    """Convert utf-8 encoded string to a dict.

    Since the response is encoded in utf-8, it gets decoded to regular python
    string that will be a json string. That gets converted to python
    dictionary.

    Note: Do not use this method to process non-json response.content

    :param requests.models.Response response: object that includes attributes
        status code and content

    :return: response content as decoded dictionary

    :rtype: dict
    """
    if response.content:
        decoded = response.content.decode("utf-8")
        if len(decoded) > 0:
            return json.loads(decoded)
    return {}


def _response_to_exception(response):
    """Return exception object with appropriate messages.

    :param requests.models.Response response: object that has attributes
        status code and content

    :return: exception with proper error message

    :rtype: CseResponseError
    """
    error_message = ""
    minor_error_code = MinorErrorCode.DEFAULT_ERROR_CODE

    # in case of 401, content type is not set in the response and body is empty
    if response.status_code == requests.codes.unauthorized:
        error_message = 'Session has expired or user not logged in.' \
                        ' Please re-login.'
    elif response.status_code == requests.codes.too_many_requests:
        error_message = 'Server is busy. Please try again later.'
    elif 'json' in response.headers['Content-Type']:
        response_dict = _deserialize_response_content(response)
        if shared_constants.RESPONSE_MESSAGE_KEY in response_dict:
            message = response_dict[shared_constants.RESPONSE_MESSAGE_KEY]
            if isinstance(message, dict):
                if shared_constants.ERROR_DESCRIPTION_KEY in message:
                    error_message = message[shared_constants.ERROR_DESCRIPTION_KEY]  # noqa: E501
                if shared_constants.ERROR_MINOR_CODE_KEY in message:
                    minor_error_code = MinorErrorCode(message[shared_constants.ERROR_MINOR_CODE_KEY])  # noqa: E501
            else:
                error_message = message
    if not error_message:
        error_message = shared_constants.UNKNOWN_ERROR_MESSAGE

    raise CseResponseError(
        response.status_code, error_message, minor_error_code)


class CseClient:
    def __init__(self, client: vcd_client.Client):
        self._client = client
        self._uri = self._client.get_api_uri()
        self._request_page_size = 10

    def do_request(self,
                   uri: str,
                   method: str,
                   params: dict = None,
                   accept_type: str = None,
                   media_type: str = None,
                   payload: dict = None,
                   timeout: float = None):
        """."""
        wire_logger.debug(f"Made request to: {method} {uri}")
        wire_logger.debug(f"Accept type : {accept_type}")
        if params:
            wire_logger.debug(f"Query params : {params}")
        if payload:
            wire_logger.debug(f"Content-Type: {media_type}")
            wire_logger.debug(f"Content : {payload}")
        if timeout:
            wire_logger.debug(f"Timeout : {timeout}")

        # ToDo: Add support for timeout later
        response = self._client._do_request_prim(
            method,
            uri,
            self._client._session,
            accept_type=accept_type,
            contents=payload,
            media_type=media_type,
            params=params)

        wire_logger.debug(f"Request headers: {response.request.headers}")

        return response

    def iterate_results(self, base_url, filters=None):
        """Iterate over paginated response until all the results are obtained.

        :param str base_url: initial url
        :param dict filters: filters for making the API call
        :returns: Generator which yields values and a boolean indicating if
            more results are present
        :rtype: Generator[(List[dict], bool), None, None]

        page and pageSize is not needed if iteration should start from the
        first page.

        Example: Iterating through all the pages for get cluster
            (/cse/3.0/clusters) response from CSE server:
                self.iterate_results("https://vcd-api/api/cse/3.0/clusters")

        Example: Iterating through all the pages for get cluster starting from
            page 3:
                self.iterate_results("https://vcd-ip/api/cse/3.0/clusters?page=3&pageSize=25")
        """  # noqa: E501
        if filters is None:
            filters = {}
        # NOTE: This method is added here to reduce dependency between
        # cse_client package and the rest of the code.
        url = base_url
        while url:
            response = self.do_request(
                uri=url,
                method=shared_constants.RequestMethod.GET,
                params=filters,
                accept_type='application/json')
            processed_response = self.process_response(response)
            url = processed_response.get(shared_constants.PaginationKey.NEXT_PAGE_URI)  # noqa: E501
            yield processed_response[shared_constants.PaginationKey.VALUES], bool(url)  # noqa: E501

    @staticmethod
    def process_response(response):
        """Process the given response dictionary with following keys.

        Log the response if wire logging is enabled.

        If the value of status code is 2xx, return the response content, else
        raise exception with proper error message

        :param requests.models.Response response: object with attributes viz.
            status code and content
            status_code: http status code
            content: response result as string

        :return: decoded response content, if status code is 2xx or 429.

        :rtype: dict

        :raises CseResponseError: if response http status code is not 2xx or
            429
        """
        wire_logger.debug(f"Response status code: {response.status_code}")
        wire_logger.debug(f"Response headers: {response.headers}")

        response_content = _deserialize_response_content(response)
        wire_logger.debug(f"Response content: {response_content}")

        if response.status_code in [
            requests.codes.ok,
            requests.codes.created,
            requests.codes.accepted,
            requests.codes.no_content
        ]:
            return response_content

        raise _response_to_exception(response)
