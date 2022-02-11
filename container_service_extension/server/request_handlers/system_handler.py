# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from copy import deepcopy

from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.exception.exceptions as e
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import OperationStatus
from container_service_extension.lib.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.lib.telemetry.telemetry_handler \
    import record_user_action_telemetry
import container_service_extension.security.context.operation_context as ctx
import container_service_extension.server.request_handlers.request_utils as req_utils  # noqa: E501


@record_user_action_telemetry(CseOperation.SYSTEM_INFO)
def system_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for system info operation.

    :return: Dictionary with system info data.
    """
    # TODO: circular dependency with request_processor.py
    import container_service_extension.server.service as service
    return service.Service().info(
        get_sysadmin_info=op_ctx.client.is_sysadmin())


def system_update(request_data, op_ctx: ctx.OperationContext):
    """Request handler for system update operation.

    :return: Dictionary with system update status.
    """
    data = req_utils.flatten_request_data(
        request_data, [RequestKey.INPUT_SPEC])

    required = [
        RequestKey.SERVER_ACTION
    ]
    req_utils.validate_payload(data, required)

    # Telemetry data preparation
    server_action = data.get(RequestKey.SERVER_ACTION)
    cse_operation = server_action or 'invalid server action'
    if server_action == 'enable':
        cse_operation = CseOperation.SYSTEM_ENABLE
    elif server_action == 'disable':
        cse_operation = CseOperation.SYSTEM_DISABLE
    elif server_action == 'stop':
        cse_operation = CseOperation.SYSTEM_STOP

    status = OperationStatus.FAILED
    if op_ctx.client.is_sysadmin:
        # circular dependency between request_processor.py and service.py
        import container_service_extension.server.service as service
        try:
            result = service.Service().update_status(
                data.get(RequestKey.SERVER_ACTION))
            status = OperationStatus.SUCCESS
            return result
        finally:
            record_user_action(cse_operation=cse_operation, status=status)

    record_user_action(cse_operation=cse_operation, status=status)
    raise e.UnauthorizedRequestError(
        error_message='Unauthorized to update CSE')


def get_server_config(request_data, op_ctx: ctx.OperationContext):
    """."""
    if op_ctx.client.is_sysadmin:
        # TODO: Find a better way to access to the config dict
        # in ServerConfig object
        server_config = deepcopy(
            server_utils.get_server_runtime_config()._config
        )

        server_config['mqtt']['token'] = "REDACTED"
        server_config['mqtt']['token_id'] = "REDACTED"

        for vc in server_config.get('vcs', []):
            vc['password'] = "REDACTED"

        server_config['vcd']['password'] = "REDACTED"

        rde_version = server_config['service']['rde_version_in_use']
        rde_version_str = f"{rde_version.major}.{rde_version.minor}.{rde_version.patch}"  # noqa: E501
        server_config['service']['rde_version_in_use'] = rde_version_str

        return server_config

    raise e.UnauthorizedRequestError(
        error_message='Unauthorized to access CSE server configuration.'
    )
