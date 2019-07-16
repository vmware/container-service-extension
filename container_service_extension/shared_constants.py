# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

ERROR_DESCRIPTION_KEY = "description"
ERROR_MESSAGE_KEY = "message"
ERROR_REASON_KEY = "reason"
ERROR_STACKTRACE_KEY = "stacktrace"
UNKNOWN_ERROR_MESSAGE = "Unknown error. Please contact your system " \
                        "administrator"

@unique
class RequestMethod(str, Enum):
    GET = 'GET'
    POST = 'POST'
    DELETE = 'DELETE'
    PUT = 'PUT'
