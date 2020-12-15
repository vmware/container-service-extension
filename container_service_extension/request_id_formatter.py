# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging

from container_service_extension.server_constants import REQUEST_ID_FORMAT
import container_service_extension.thread_local_data as thread_local_data


class RequestIdFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def format(self, record):
        orig_format = self._style._fmt

        # Remove the request id from being printed if there is no request id
        req_start = orig_format.find(REQUEST_ID_FORMAT)
        if req_start != -1 and thread_local_data.get_thread_local_data(thread_local_data.REQUEST_ID) is None:  # noqa: E501
            req_end = req_start + len(REQUEST_ID_FORMAT)
            self._style._fmt = orig_format[:req_start] + orig_format[req_end:]

        result = logging.Formatter.format(self, record)

        # Restore format
        self._style._fmt = orig_format

        return result
