# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action_telemetry


@record_user_action_telemetry(CseOperation.SYSTEM_INFO)
def system_info(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for system info operation.

    :return: Dictionary with system info data.
    """
    # TODO: circular dependency with request_processor.py
    import container_service_extension.service as service
    return service.Service().info(tenant_auth_token, is_jwt_token)


def system_update(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for system update operation.

    :return: Dictionary with system update status.
    """
    required = [
        RequestKey.SERVER_ACTION
    ]
    req_utils.validate_payload(request_data, required)

    # Telemetry data preparation
    if request_data.get(RequestKey.SERVER_ACTION) == 'enable':
        cse_operation = CseOperation.SYSTEM_ENABLE
    elif request_data.get(RequestKey.SERVER_ACTION) == 'disable':
        cse_operation = CseOperation.SYSTEM_DISABLE
    elif request_data.get(RequestKey.SERVER_ACTION) == 'stop':
        cse_operation = CseOperation.SYSTEM_STOP
    else:
        cse_operation = CseOperation.SYSTEM_UNKNOWN

    try:
        # TODO: circular dependency with request_processor.py
        import container_service_extension.service as service
        status = service.Service().update_status(
            tenant_auth_token, is_jwt_token, request_data)
        # Record telemetry data on successful system update
        record_user_action(cse_operation=cse_operation)

        return status
    except Exception as err:
        # Record telemetry data on failure
        record_user_action(cse_operation=cse_operation,
                           status=OperationStatus.FAILED,
                           message=str(err))
        raise err
