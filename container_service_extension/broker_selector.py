# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.broker import DefaultBroker


def get_new_broker(headers, request_body):
    from container_service_extension.service import Service
    server_run_config = Service().get_service_run_config()
    if server_run_config['broker']['type'] == 'default':
        return DefaultBroker(headers, request_body)
    else:
        return None
