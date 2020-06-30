# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import container_service_extension.def_.ovdc_service as ovdc_service
import container_service_extension.operation_context as ctx
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501


def ovdc_update(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc enable, disable operations.

    Add or remove the respective cluster placement policies to enable or
    disable cluster deployment of a certain kind in the OVDC.

    Required data: k8s_runtime

    :return: Dictionary with org VDC update task href.
    """
    ovdc = ovdc_service.Ovdc(**{**data[RequestKey.V35_SPEC], "ovdc_id": data[RequestKey.OVDC_ID]}) # noqa: E501
    return ovdc_service.update_ovdc(operation_context, ovdc)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
def ovdc_info(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc info operation.

    Required data: ovdc_id

    :return: Dictionary with org VDC k8s provider metadata.
    """
    ovdc_id = data[RequestKey.OVDC_ID]
    return ovdc_service.get_ovdc(operation_context, ovdc_id)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
def ovdc_list(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s runtimes.
    """
    return ovdc_service.list_ovdc(operation_context)
