# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import os

import requests
from pyvcloud.vcd.client import Client

import container_service_extension.client.constants as cli_constants
import container_service_extension.common.constants.shared_constants as shared_constants
from container_service_extension.common.constants.shared_constants import ERROR_DESCRIPTION_KEY  # noqa: E501
from container_service_extension.common.constants.shared_constants import ERROR_MINOR_CODE_KEY  # noqa: E501
from container_service_extension.common.constants.shared_constants import RESPONSE_MESSAGE_KEY  # noqa: E501
from container_service_extension.common.constants.shared_constants import UNKNOWN_ERROR_MESSAGE  # noqa: E501
from container_service_extension.common.utils.core_utils import str_to_bool
from container_service_extension.exception.exceptions import CseResponseError
from container_service_extension.exception.minor_error_codes import MinorErrorCode  # noqa: E501
from container_service_extension.logging.logger import CLIENT_WIRE_LOGGER
from container_service_extension.logging.logger import NULL_LOGGER

wire_logger = NULL_LOGGER
if str_to_bool(os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING)):
    wire_logger = CLIENT_WIRE_LOGGER


def make_request(client: Client,
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

    # ToDo: Add back support for timeout later
    response = client._do_request_prim(
        method,
        uri,
        client._session,
        accept_type=accept_type,
        contents=payload,
        media_type=media_type,
        params=params)

    wire_logger.debug(f"Request headers: {response.request.headers}")

    return response
