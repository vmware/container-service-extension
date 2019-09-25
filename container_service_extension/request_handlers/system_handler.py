# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


import container_service_extension.utils as utils


def system_info(request_data, tenant_auth_token):
    """Request handler for system info operation.

    :return: Dictionary with system info data.
    """
    # TODO: circular dependency with request_processor.py
    import container_service_extension.service as service
    return service.Service().info(tenant_auth_token)


def system_update(request_data, tenant_auth_token):
    """Request handler for system update operation.

    :return: Dictionary with system update status.
    """
    required = [
        RequestKey.SERVER_ACTION
    ]
    utils.ensure_keys_in_dict(required, request_data, dict_name='data')

    # TODO: circular dependency with request_processor.py
    import container_service_extension.service as service
    return {
        'message': service.Service().update_status(tenant_auth_token,
                                                   request_data)
    }
