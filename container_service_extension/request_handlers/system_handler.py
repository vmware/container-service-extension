# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.exceptions as e
import container_service_extension.request_context as ctx
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action_telemetry


@record_user_action_telemetry(CseOperation.SYSTEM_INFO)
def system_info(request_data, request_context: ctx.RequestContext):
    """Request handler for system info operation.

    :return: Dictionary with system info data.
    """
    # TODO: circular dependency with request_processor.py
    import container_service_extension.service as service
    return service.Service().info(
        get_sysadmin_info=request_context.client.is_sysadmin())


def system_update(request_data, request_context: ctx.RequestContext):
    """Request handler for system update operation.

    :return: Dictionary with system update status.
    """
    required = [
        RequestKey.SERVER_ACTION
    ]
    req_utils.validate_payload(request_data, required)

    # Telemetry data preparation
    cse_operation = CseOperation.SYSTEM_UNKNOWN
    if request_data.get(RequestKey.SERVER_ACTION) == 'enable':
        cse_operation = CseOperation.SYSTEM_ENABLE
    elif request_data.get(RequestKey.SERVER_ACTION) == 'disable':
        cse_operation = CseOperation.SYSTEM_DISABLE
    elif request_data.get(RequestKey.SERVER_ACTION) == 'stop':
        cse_operation = CseOperation.SYSTEM_STOP

    status = OperationStatus.FAILED
    if request_context.client.is_sysadmin:
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
