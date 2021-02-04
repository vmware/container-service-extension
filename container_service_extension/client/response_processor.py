# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import os

import requests

import container_service_extension.client.constants as cli_constants
from container_service_extension.exceptions import CseResponseError
from container_service_extension.logger import CLIENT_WIRE_LOGGER
from container_service_extension.logger import NULL_LOGGER
from container_service_extension.minor_error_codes import MinorErrorCode
from container_service_extension.shared_constants import ERROR_DESCRIPTION_KEY
from container_service_extension.shared_constants import ERROR_MINOR_CODE_KEY
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY
from container_service_extension.shared_constants import UNKNOWN_ERROR_MESSAGE
from container_service_extension.utils import str_to_bool

wire_logger = NULL_LOGGER
if str_to_bool(os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING)):
    wire_logger = CLIENT_WIRE_LOGGER


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

    :raises CseResponseError: if response http status code is not 2xx or 429
    """
    wire_logger.debug(f"Made request to: {response.request.method} {response.request.path_url}")  # noqa: E501
    wire_logger.debug(f"Request headers: {response.request.headers}")
    wire_logger.debug(f"Request body: {response.request.body}")
    wire_logger.debug(f"Response status code: {response.status_code}")
    wire_logger.debug(f"Response headers: {response.headers}")

    response_content = deserialize_response_content(response)
    wire_logger.debug(f"Response content: {response_content}")

    if response.status_code in [
        requests.codes.ok,
        requests.codes.created,
        requests.codes.accepted,
    ]:
        return response_content

    raise response_to_exception(response)


def deserialize_response_content(response):
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


def response_to_exception(response):
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
        error_message = 'Session has expired or user not logged in.'\
                        ' Please re-login.'
    elif response.status_code == requests.codes.too_many_requests:
        error_message = 'Server is busy. Please try again later.'
    elif 'json' in response.headers['Content-Type']:
        response_dict = deserialize_response_content(response)
        if RESPONSE_MESSAGE_KEY in response_dict:
            message = response_dict[RESPONSE_MESSAGE_KEY]
            if isinstance(message, dict):
                if ERROR_DESCRIPTION_KEY in message:
                    error_message = message[ERROR_DESCRIPTION_KEY]
                if ERROR_MINOR_CODE_KEY in message:
                    minor_error_code = MinorErrorCode(message[ERROR_MINOR_CODE_KEY]) # noqa: E501
            else:
                error_message = message
    if not error_message:
        error_message = UNKNOWN_ERROR_MESSAGE

    raise CseResponseError(
        response.status_code, error_message, minor_error_code)
