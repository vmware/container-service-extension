# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
import container_service_extension.telemetry.payload_generator as\
    payload_generator
from container_service_extension.telemetry.payload_generator \
    import get_payload_for_user_action
from container_service_extension.telemetry.vac_client import VacClient
from container_service_extension.utils import get_server_runtime_config

# Payload generator function mappings for CSE operations
# Each command has its own payload generator
OPERATION_TO_PAYLOAD_GENERATOR = {
    CseOperation.CLUSTER_LIST: payload_generator.get_payload_for_list_clusters,
    CseOperation.CLUSTER_CREATE: payload_generator.get_payload_for_create_cluster,  # noqa: E501
    CseOperation.INSTALL_SERVER: payload_generator.get_payload_for_install_server   # noqa: E501
}


def telemetry_logger(cse_operation):
    """Decorate to make access to cse_operation to decorated function.

    This decorator is applicable only for CSE user commands.
    :param CseOperation cse_operation: CSE operation

    :return: reference to the wrapper function that decorates the
    actual CSE operation.
    """
    def decorator_logger(func):
        """Decorate to log cse operation and status to analytics server.

        No exception raised by the decorated function is recorded/logged
        with status: SUCCESS and FAILURE otherwise.

        :param method func: decorated function

        :return: reference to the function that executes the decorated
        function.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                ret_value = func(*args, **kwargs)
                record_user_action(cse_operation)
                return ret_value
            except Exception as err:
                record_user_action(cse_operation,
                                   status=OperationStatus.FAILED,
                                   message=str(err))
                raise err
        return wrapper
    return decorator_logger


def record_user_action(cse_operation, status=OperationStatus.SUCCESS,
                       message=None, telemetry=None):
    """Record CSE user action information in analytics server.

    No exception should be leaked. Catch all exceptions and log them.

    :param CseOperation cse_operation:
    :param OperationStatus status: SUCCESS/FAILURE of the user action
    :param str message: any information about failure or custom message
    :param dict telemetry: telemetry section CSE config->service
    """
    if not telemetry:
        telemetry = get_server_runtime_config()['service']['telemetry']

    if telemetry['enable']:
        try:
            payload = get_payload_for_user_action(cse_operation, status, message)  # noqa: E501
            _send_data_to_analytics_server(payload, telemetry)
        except Exception as err:
            LOGGER.warning(f"Error in recording user action information:{str(err)}")  # noqa: E501


def record_cse_operation_details(cse_operation, cse_params, telemetry=None):
    """Record CSE operation details in analytics server.

    No exception should be leaked. Catch all exceptions and log them.

    :param CseOperation cse_operation: CSE operation information
    :param dict cse_params: CSE operation parameters
    :param dict telemetry: telemetry section of config->service
    """
    if not telemetry:
        telemetry = get_server_runtime_config()['service']['telemetry']

    if telemetry['enable']:
        try:
            payload = OPERATION_TO_PAYLOAD_GENERATOR[cse_operation](cse_operation, cse_params)  # noqa: E501
            _send_data_to_analytics_server(payload, telemetry)
        except Exception as err:
            LOGGER.warning(f"Error in recording CSE operation details :{str(err)}")  # noqa: E501


def _send_data_to_analytics_server(payload, telemetry):
    """Send the given payload to analytics server.

    :param dict payload: json metadata about CSE operation
    :param dict telemetry: telemetry section of config->service
    """
    vac_client = VacClient(base_url=telemetry['vac_url'],
                           collector_id=telemetry['collector_id'],
                           instance_id=telemetry['instance_id'],
                           logger_instance=LOGGER)
    vac_client.send_data(payload)
