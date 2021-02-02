# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Thread utils for managing multiple threads in the server."""

import functools
import threading

import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501


def _transfer_thread_local_data_wrapper(func):
    cur_thread_data = thread_local_data.get_thread_local_data_as_dict()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread_local_data.set_thread_local_data_from_dict(cur_thread_data)
        func(*args, **kwargs)
        thread_local_data.reset_thread_local_data()
    return wrapper


def run_async(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread_local_data_wrapper = _transfer_thread_local_data_wrapper(func)
        t = threading.Thread(name=generate_thread_name(func.__name__),
                             target=thread_local_data_wrapper, args=args, kwargs=kwargs,  # noqa: E501
                             daemon=True)
        t.start()
        return t
    return wrapper


def generate_thread_name(function_name):
    parent_thread_id = threading.current_thread().ident
    return function_name + ':' + str(parent_thread_id)
