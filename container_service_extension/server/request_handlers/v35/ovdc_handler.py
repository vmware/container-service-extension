# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.common.constants.shared_constants import PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.ovdc_service as ovdc_service
import container_service_extension.security.context.operation_context as ctx
import container_service_extension.server.request_handlers.request_utils as request_utils  # noqa: E501


@request_utils.cluster_api_exception_handler
def ovdc_update(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc enable, disable operations.

    Add or remove the respective cluster placement policies to enable or
    disable cluster deployment of a certain kind in the OVDC.

    Required data: k8s_runtime

    :return: Dictionary with org VDC update task href.
    """
    ovdc_spec = common_models.Ovdc(**data[RequestKey.INPUT_SPEC])
    return ovdc_service.update_ovdc(operation_context,
                                    ovdc_id=data[RequestKey.OVDC_ID],
                                    ovdc_spec=ovdc_spec)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
@request_utils.cluster_api_exception_handler
def ovdc_info(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc info operation.

    Required data: ovdc_id

    :return: Dictionary with org VDC k8s provider metadata.
    """
    ovdc_id = data[RequestKey.OVDC_ID]
    return ovdc_service.get_ovdc(operation_context, ovdc_id)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
@request_utils.cluster_api_exception_handler
def ovdc_list(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s runtimes.
    """
    return ovdc_service.list_ovdc(operation_context)


# TODO: Record telemetry in a different telemetry handler
@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
@request_utils.cluster_api_exception_handler
def org_vdc_list(data, operation_context: ctx.OperationContext):
    """Request handler for org vdc list operation.

    This handler returns a paginated response.
    :return: Dictionary containing paginated response with Org VDC runtime info
    :rtype: dict
    """
    query_params = data.get(RequestKey.QUERY_PARAMS, {})
    page_number = int(query_params.get(PaginationKey.PAGE_NUMBER,
                                       CSE_PAGINATION_FIRST_PAGE_NUMBER))
    page_size = int(query_params.get(PaginationKey.PAGE_SIZE,
                                     CSE_PAGINATION_DEFAULT_PAGE_SIZE))
    result = ovdc_service.list_org_vdcs(operation_context,
                                        page_number=page_number,
                                        page_size=page_size)
    base_uri = data['url']
    return server_utils.create_links_and_construct_paginated_result(
        base_uri,
        result[PaginationKey.VALUES],
        result[PaginationKey.RESULT_TOTAL],
        page_number=page_number,
        page_size=page_size)
