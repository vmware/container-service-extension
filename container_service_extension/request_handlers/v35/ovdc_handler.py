# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import container_service_extension.def_.models as def_models
import container_service_extension.def_.ovdc_service as ovdc_service
import container_service_extension.operation_context as ctx
import container_service_extension.request_handlers.request_utils as request_utils  # noqa: E501
from container_service_extension.server_constants import CseOperation as CseServerOperationInfo  # noqa: E501
import container_service_extension.server_utils as server_utils
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import PaginationKey
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501


@request_utils.v35_api_exception_handler
def ovdc_update(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc enable, disable operations.

    Add or remove the respective cluster placement policies to enable or
    disable cluster deployment of a certain kind in the OVDC.

    Required data: k8s_runtime

    :return: Dictionary with org VDC update task href.
    """
    ovdc_spec = def_models.Ovdc(**data[RequestKey.INPUT_SPEC])
    return ovdc_service.update_ovdc(operation_context,
                                    ovdc_id=data[RequestKey.OVDC_ID],
                                    ovdc_spec=ovdc_spec)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
@request_utils.v35_api_exception_handler
def ovdc_info(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc info operation.

    Required data: ovdc_id

    :return: Dictionary with org VDC k8s provider metadata.
    """
    ovdc_id = data[RequestKey.OVDC_ID]
    return ovdc_service.get_ovdc(operation_context, ovdc_id)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
@request_utils.v35_api_exception_handler
def ovdc_list(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s runtimes.
    """
    page_number = int(data.get(RequestKey.V35_QUERY, {}).get(PaginationKey.PAGE_NUMBER,  # noqa: E501
                                                             CSE_PAGINATION_FIRST_PAGE_NUMBER))  # noqa: E501
    page_size = int(data.get(RequestKey.V35_QUERY, {}).get(PaginationKey.PAGE_SIZE,  # noqa: E501
                                                           CSE_PAGINATION_DEFAULT_PAGE_SIZE))  # noqa: E501
    result = ovdc_service.list_ovdc(operation_context,
                                    page_number=page_number,
                                    page_size=page_size)
    api_path = CseServerOperationInfo.V35_OVDC_LIST.api_path_format
    base_uri = f"{operation_context.client.get_api_uri().strip('/')}{api_path}"
    return server_utils.create_links_and_construct_paginated_result(
        base_uri,
        result[PaginationKey.VALUES],
        result[PaginationKey.RESULT_TOTAL],
        page_number=page_number,
        page_size=page_size)
