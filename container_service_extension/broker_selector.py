# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.broker import DefaultBroker
from container_service_extension.utils import get_server_runtime_config


def get_new_broker(headers, request_body):
    server_config = get_server_runtime_config()
    if server_config['broker']['type'] == 'default':
        return DefaultBroker(headers, request_body)
    else:
        return None
