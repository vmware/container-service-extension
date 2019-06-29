# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import traceback

import requests

from container_service_extension.exceptions import CseRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.shared_constants import ERROR_DESCRIPTION_KEY
from container_service_extension.shared_constants import ERROR_MESSAGE_KEY
from container_service_extension.shared_constants import ERROR_REASON_KEY
from container_service_extension.shared_constants import ERROR_STACKTRACE_KEY


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
        except CseRequestError as e:
            result['status_code'] = e.status_code
            result['body'] = {'message': str(e)}
            LOGGER.error(traceback.format_exc())
        except Exception as err:
            result['status_code'] = requests.codes.internal_server_error
            result['body'] = error_to_json(err)
            LOGGER.error(traceback.format_exc())
        return result
    return exception_handler_wrapper


def error_to_json(error):
    """Convert the given python exception object to a dictionary.

    :param error: Exception object.

    :return: dictionary with error reason, error description and stacktrace

    :rtype: dict
    """
    if error:
        error_string = str(error)
        reasons = error_string.split(',')
        return {
            ERROR_MESSAGE_KEY: {
                ERROR_REASON_KEY: reasons[0],
                ERROR_DESCRIPTION_KEY: error_string,
                ERROR_STACKTRACE_KEY: traceback.format_exception(
                    error.__class__, error, error.__traceback__)
            }
        }
    return dict()
