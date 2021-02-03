# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import traceback

import requests

from container_service_extension.common.constants.shared_constants import ERROR_DESCRIPTION_KEY  # noqa: E501
from container_service_extension.common.constants.shared_constants import ERROR_MINOR_CODE_KEY   # noqa: E501
from container_service_extension.common.constants.shared_constants import RESPONSE_MESSAGE_KEY   # noqa: E501
from container_service_extension.exception.exceptions import CseRequestError
from container_service_extension.exception.minor_error_codes import MinorErrorCode # noqa: E501
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER


def handle_exception(func):
    """Decorate to trap exceptions and process them.

    If there are any exceptions, a dictionary containing the status code, body
        and stacktrace will be returned.

    This decorator should be applied only on those functions that constructs
    the final HTTP responses and also needs exception handler as additional
    behaviour.

    :param method func: decorated function

    :return: reference to the function that executes the decorated function
        and traps exceptions raised by it.
    """
    @functools.wraps(func)
    def exception_handler_wrapper(*args, **kwargs):
        result = {}
        try:
            result = func(*args, **kwargs)
        except Exception as err:
            if isinstance(err, CseRequestError):
                result['status_code'] = err.status_code
                minor_error_code = err.minor_error_code
            else:
                result['status_code'] = requests.codes.internal_server_error
                minor_error_code = MinorErrorCode.DEFAULT_ERROR_CODE

            error_string = str(err if err else '')
            result['body'] = {
                RESPONSE_MESSAGE_KEY: {
                    ERROR_MINOR_CODE_KEY: int(minor_error_code),
                    ERROR_DESCRIPTION_KEY: error_string
                }
            }
            LOGGER.error(traceback.format_exc())
        return result
    return exception_handler_wrapper
