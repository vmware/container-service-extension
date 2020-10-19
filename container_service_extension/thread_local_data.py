# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import threading

from container_service_extension.init_utils import run_once


# Thread data to be initialized once. This data is specific to each thread.
THREAD_DATA = None


@run_once
def init_thread_local_data():
    global THREAD_DATA
    THREAD_DATA = threading.local()


def set_thread_request_id(request_id):
    global THREAD_DATA
    THREAD_DATA.request_id = request_id


def get_thread_request_id():
    global THREAD_DATA
    try:
        request_id = THREAD_DATA.request_id
    except AttributeError:
        request_id = None
    return request_id
