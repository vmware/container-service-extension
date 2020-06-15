# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.exceptions as e
import container_service_extension.request_handlers.request_utils as req_utils
import container_service_extension.security_context as ctx
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action_telemetry


@record_user_action_telemetry(CseOperation.SYSTEM_INFO)
def system_info(request_data, security_ctx: ctx.SecurityContext):
    """Request handler for system info operation.

    :return: Dictionary with system info data.
    """
    # TODO: circular dependency with request_processor.py
    import container_service_extension.service as service
    return service.Service().info(
        get_sysadmin_info=security_ctx.client.is_sysadmin())


def system_update(request_data, security_ctx: ctx.SecurityContext):
    """Request handler for system update operation.

    :return: Dictionary with system update status.
    """
    required = [
        RequestKey.SERVER_ACTION
    ]
    req_utils.validate_payload(request_data, required)

    # Telemetry data preparation
    server_action = request_data.get(RequestKey.SERVER_ACTION)
    cse_operation = server_action or 'invalid server action'
    if server_action == 'enable':
        cse_operation = CseOperation.SYSTEM_ENABLE
    elif server_action == 'disable':
        cse_operation = CseOperation.SYSTEM_DISABLE
    elif server_action == 'stop':
        cse_operation = CseOperation.SYSTEM_STOP

    status = OperationStatus.FAILED
    if security_ctx.client.is_sysadmin:
        # circular dependency between request_processor.py and service.py
        import container_service_extension.service as service
        try:
            result = service.Service().update_status(
                request_data.get(RequestKey.SERVER_ACTION))
            status = OperationStatus.SUCCESS
            return result
        finally:
            record_user_action(cse_operation=cse_operation, status=status)

    record_user_action(cse_operation=cse_operation, status=status)
    raise e.UnauthorizedRequestError(
        error_message='Unauthorized to update CSE')
