# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.broker import DefaultBroker
# to avoid circular imports
import container_service_extension.service

def get_new_broker(headers, request_body):
    server_run_config = service.Service().get_service_run_config()
    if server_run_config['broker']['type'] == 'default':
        return DefaultBroker(headers, request_body)
    else:
        return None