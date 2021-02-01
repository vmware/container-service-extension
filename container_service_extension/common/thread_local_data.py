# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import threading

from container_service_extension.common.utils.init_utils import run_once


# Thread data to be initialized once. This data is specific to each thread.
THREAD_DATA = None


@run_once
def init_thread_local_data():
    """Initialize THREAD_DATA once for all threads.

    Running this function more than once creates a new instance of
    threading.local() each time, overwriting the original THREAD_DATA. The
    value of THREAD_DATA will look different to each thread.
    """
    global THREAD_DATA
    THREAD_DATA = threading.local()


def set_thread_local_data(name: str, value):
    """Set the attribute of current thread to the given value."""
    global THREAD_DATA
    setattr(THREAD_DATA, name, value)


def get_thread_local_data(name: str):
    """Get the value of given attribute from the current thread."""
    global THREAD_DATA
    return getattr(THREAD_DATA, name, None)


def get_thread_local_data_as_dict() -> dict:
    """Get all the current thread attributes as dictionary."""
    global THREAD_DATA
    return THREAD_DATA.__dict__


def set_thread_local_data_from_dict(data_dict: dict = {}):
    """Set the current thread attributes to given values found in dictionary.

    :param dict data_dict: input attributes
    :return:
    """
    global THREAD_DATA
    for key in data_dict:
        THREAD_DATA.__dict__[key] = data_dict.get(key)


def reset_thread_local_data():
    """Reset the current thread attributes.

    :param dict data_dict: input attributes
    :return:
    """
    global THREAD_DATA
    THREAD_DATA.__dict__.clear()
