# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from container_service_extension.common.utils.server_utils import get_server_runtime_config  # noqa: E501
from container_service_extension.common.utils.thread_utils import run_async
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import OperationStatus
import container_service_extension.lib.telemetry.payload_generator as\
    payload_generator
from container_service_extension.lib.telemetry.payload_generator \
    import get_payload_for_user_action
from container_service_extension.lib.telemetry.vac_client import VacClient
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER

# Payload generator function mappings for CSE operations
# Each command has its own payload generator
OPERATION_TO_PAYLOAD_GENERATOR = {
    # CSE server CLI commands
    CseOperation.CLUSTER_CONVERT: payload_generator.get_payload_for_cluster_convert,  # noqa: E501

    CseOperation.CONFIG_CHECK: payload_generator.get_payload_for_config_check,

    CseOperation.SERVICE_INSTALL: payload_generator.get_payload_for_install_server,   # noqa: E501
    CseOperation.SERVICE_UPGRADE: payload_generator.get_payload_for_upgrade_server,  # noqa: E501
    CseOperation.SERVICE_RUN: payload_generator.get_payload_for_run_server,

    CseOperation.TEMPLATE_INSTALL: payload_generator.get_payload_for_install_template,  # noqa: E501
    CseOperation.TEMPLATE_LIST: payload_generator.get_payload_for_template_list,  # noqa: E501

    # vcd-cli CSE client commands
    CseOperation.CLUSTER_CONFIG: payload_generator.get_payload_for_cluster_config,  # noqa: E501
    CseOperation.CLUSTER_CREATE: payload_generator.get_payload_for_create_cluster,  # noqa: E501
    CseOperation.CLUSTER_DELETE: payload_generator.get_payload_for_cluster_delete,  # noqa: E501
    CseOperation.CLUSTER_INFO: payload_generator.get_payload_for_cluster_info,
    CseOperation.CLUSTER_LIST: payload_generator.get_payload_for_list_clusters,
    CseOperation.CLUSTER_RESIZE: payload_generator.get_payload_for_cluster_resize,  # noqa: E501
    CseOperation.CLUSTER_UPGRADE: payload_generator.get_payload_for_cluster_upgrade,  # noqa: E501
    CseOperation.CLUSTER_UPGRADE_PLAN: payload_generator.get_payload_for_cluster_upgrade_plan,  # noqa: E501

    CseOperation.NODE_CREATE: payload_generator.get_payload_for_node_create,
    CseOperation.NODE_DELETE: payload_generator.get_payload_for_node_delete,
    CseOperation.NODE_INFO: payload_generator.get_payload_for_node_info,

    CseOperation.OVDC_DISABLE: payload_generator.get_payload_for_ovdc_disable,
    CseOperation.OVDC_ENABLE: payload_generator.get_payload_for_ovdc_enable,
    CseOperation.OVDC_INFO: payload_generator.get_payload_for_ovdc_info,
    CseOperation.OVDC_LIST: payload_generator.get_payload_for_ovdc_list,

    CseOperation.V35_CLUSTER_INFO: payload_generator.get_payload_for_v35_cluster_info,  # noqa: E501
    CseOperation.V35_CLUSTER_LIST: payload_generator.get_payload_for_v35_cluster_list,  # noqa: E501
    CseOperation.V35_CLUSTER_CONFIG: payload_generator.get_payload_for_v35_cluster_config,  # noqa: E501
    CseOperation.V35_CLUSTER_APPLY: payload_generator.get_payload_for_v35_cluster_apply,  # noqa: E501
    CseOperation.V35_CLUSTER_DELETE: payload_generator.get_payload_for_v35_cluster_delete,  # noqa: E501
    CseOperation.V35_CLUSTER_UPGRADE_PLAN: payload_generator.get_payload_for_v35_cluster_upgrade_plan,  # noqa: E501
    CseOperation.V35_CLUSTER_UPGRADE: payload_generator.get_payload_for_v35_cluster_upgrade,  # noqa: E501
    CseOperation.V35_CLUSTER_ACL_LIST: payload_generator.get_payload_for_v35_cluster_acl_list,  # noqa: E501
    CseOperation.V35_CLUSTER_ACL_UPDATE: payload_generator.get_payload_for_v35_cluster_acl_update,  # noqa: E501
    CseOperation.V35_NODE_DELETE: payload_generator.get_payload_for_v35_node_delete,  # noqa: E501

    CseOperation.V36_CLUSTER_INFO: payload_generator.get_payload_for_v36_cluster_info,  # noqa: E501
    CseOperation.V36_CLUSTER_LIST: payload_generator.get_payload_for_v36_cluster_list,  # noqa: E501
    CseOperation.V36_CLUSTER_CONFIG: payload_generator.get_payload_for_v36_cluster_config,  # noqa: E501
    CseOperation.V36_CLUSTER_APPLY: payload_generator.get_payload_for_v36_cluster_apply,  # noqa: E501
    CseOperation.V36_CLUSTER_DELETE: payload_generator.get_payload_for_v36_cluster_delete,  # noqa: E501
    CseOperation.V36_CLUSTER_UPGRADE_PLAN: payload_generator.get_payload_for_v36_cluster_upgrade_plan,  # noqa: E501
    CseOperation.V36_CLUSTER_UPGRADE: payload_generator.get_payload_for_v36_cluster_upgrade,  # noqa: E501
    CseOperation.V36_CLUSTER_ACL_LIST: payload_generator.get_payload_for_v36_cluster_acl_list,  # noqa: E501
    CseOperation.V36_CLUSTER_ACL_UPDATE: payload_generator.get_payload_for_v36_cluster_acl_update,  # noqa: E501
    CseOperation.V36_NODE_DELETE: payload_generator.get_payload_for_v36_node_delete,  # noqa: E501

    CseOperation.PKS_CLUSTER_LIST: payload_generator.get_payload_for_pks_list_clusters,  # noqa: E501
    CseOperation.PKS_CLUSTER_INFO: payload_generator.get_payload_for_pks_cluster_info,  # noqa: E501
    CseOperation.PKS_CLUSTER_CONFIG: payload_generator.get_payload_for_pks_cluster_config,  # noqa: E501
    CseOperation.PKS_CLUSTER_CREATE: payload_generator.get_payload_for_pks_cluster_create,  # noqa: E501
    CseOperation.PKS_CLUSTER_DELETE: payload_generator.get_payload_for_pks_cluster_delete,  # noqa: E501
    CseOperation.PKS_CLUSTER_RESIZE: payload_generator.get_payload_for_pks_cluster_resize  # noqa: E501
}


def record_user_action_telemetry(cse_operation):
    """Decorate to make access to cse_operation to decorated function.

    This decorator is applicable only for CSE user commands.
    :param CseOperation cse_operation: CSE operation

    :return: reference to the wrapper function that decorates the
    actual CSE operation.
    """
    def decorator_logger(func):
        """Decorate to log cse operation and status to telemetry server.

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
                                   status=OperationStatus.FAILED)
                raise err
        return wrapper
    return decorator_logger


def record_user_action(cse_operation, status=OperationStatus.SUCCESS,
                       message=None, telemetry_settings=None):
    """Record CSE user action information in telemetry server.

    No exceptions should be leaked. Catch all exceptions and log them.

    :param CseOperation cse_operation:
    :param OperationStatus status: SUCCESS/FAILURE of the user action
    :param str message: any information about failure or custom message
    :param dict telemetry_settings: telemetry section CSE config->service
    """
    try:
        if not telemetry_settings:
            server_config = get_server_runtime_config()
            telemetry_settings = None if not server_config else \
                server_config.get('service', {}).get('telemetry')

        if telemetry_settings:
            if telemetry_settings.get('enable'):
                payload = get_payload_for_user_action(cse_operation, status, message)  # noqa: E501
                _send_data_to_telemetry_server(payload, telemetry_settings)
        else:
            LOGGER.debug('No telemetry settings found.')
    except Exception as err:
        LOGGER.warning(f"Error in recording user action information:{str(err)}")  # noqa: E501


def record_user_action_details(cse_operation, cse_params,
                               telemetry_settings=None):
    """Record CSE user operation details in telemetry server.

    No exception should be leaked. Catch all exceptions and log them.

    :param CseOperation cse_operation: CSE operation information
    :param dict cse_params: CSE operation parameters
    :param dict telemetry_settings: telemetry section of config->service
    """
    try:
        if not telemetry_settings:
            telemetry_settings = get_server_runtime_config()['service']['telemetry']  # noqa: E501

        if telemetry_settings['enable']:
            payload = OPERATION_TO_PAYLOAD_GENERATOR[cse_operation](cse_params)
            _send_data_to_telemetry_server(payload, telemetry_settings)
    except Exception as err:
        LOGGER.warning(f"Error in recording CSE operation details :{str(err)}")  # noqa: E501


@run_async
def _send_data_to_telemetry_server(payload, telemetry_settings):
    """Send the given payload to telemetry server.

    :param dict payload: json metadata about CSE operation
    :param dict telemetry_settings: telemetry section of config->service
    """
    vac_client = VacClient(base_url=telemetry_settings['vac_url'],
                           collector_id=telemetry_settings['collector_id'],
                           instance_id=telemetry_settings['instance_id'],
                           vcd_ceip_id=telemetry_settings['vcd_ceip_id'],
                           logger_debug=LOGGER)
    vac_client.send_data(payload)
