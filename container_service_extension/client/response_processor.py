# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

from lxml import objectify
import requests

from container_service_extension.exceptions import VcdResponseError
from container_service_extension.shared_constants import ERROR_MESSAGE
from container_service_extension.shared_constants import ERROR_REASON


UNKNOWN_ERROR_MESSAGE = "unknown error"


def process_response(response):
    """Process the given response dictionary with following keys.

    If the value of status code is 2xx, return the response content, else
    raise exception with proper error message

    :param requests.models.Response response: object with attributes viz.
        status code and content
        status_code: http status code
        content: response result as string

    :return: decoded response content, if status code is 2xx.

    :rtype: dict

    :raises VcdResponseError: if response http status code is not 2xx
    """
    if response.status_code in [
        requests.codes.ok, requests.codes.created,
        requests.codes.accepted
    ]:
        return deserialize_response_content(response)
    else:
        response_to_exception(response)


def deserialize_response_content(response):
    """Convert utf-8 encoded string to a dict.

    Since the response is encoded in utf-8, it gets decoded to regular python
    string that will be in json string. That gets converted to python
    dictionary.

    Note: Do not use this method to process non-json response.content

    :param requests.models.Response response: object that includes attributes
        status code and content

    :return: response content as decoded dictionary

    :rtype: dict
    """
    decoded = response.content.decode("utf-8")
    if len(decoded) > 0:
        return json.loads(decoded)
    else:
        return dict()


def response_to_exception(response):
    """Raise exception with appropriate messages.

    The class of exception raised depends on the key: status code

    :param requests.models.Response response: object that has attributes
        status code and content

    :raises: VcdResponseError
    """
    if response.status_code == requests.codes.gateway_timeout:
        message = 'An error has occurred.'
        if response.content is not None and len(response.content) > 0:
            obj = objectify.fromstring(response.content)
            message = obj.get(ERROR_MESSAGE)
    elif response.status_code == requests.codes.unauthorized:
        message = 'Session has expired or user not logged in. Please re-login.'
        if response.content is not None and len(response.content) > 0:
            obj = objectify.fromstring(response.content)
            message = obj.get(ERROR_MESSAGE)
    else:
        content = deserialize_response_content(response)
        if ERROR_MESSAGE in content:
            if ERROR_REASON in content[ERROR_MESSAGE]:
                message = content[ERROR_MESSAGE][ERROR_REASON]
            else:
                message = content[ERROR_MESSAGE]
        else:
            message = UNKNOWN_ERROR_MESSAGE

    raise VcdResponseError(response.status_code, message)
