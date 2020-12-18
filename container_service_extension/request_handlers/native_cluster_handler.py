# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.operation_context as ctx
from container_service_extension.server_constants import CseOperation as CseOperationInfo  # noqa: E501
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import PaginationKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_telemetry
import container_service_extension.utils as utils
from container_service_extension.vcdbroker import VcdBroker


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_CREATE)
def cluster_create(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster create operation.

    Required data: org_name, ovdc_name, cluster_name
    Conditional data and default values:
            network_name, num_nodes=2, num_cpu=None, mb_memory=None,
            storage_profile_name=None, template_name=default,
            template_revision=default, ssh_key=None, enable_nfs=False,
            rollback=True

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.create_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_RESIZE)
def cluster_resize(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None
    Conditional data and default values:
            network_name, rollback=True

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.resize_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_DELETE)
def cluster_delete(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.delete_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_INFO)
def cluster_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.get_cluster_info(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_CONFIG)
def cluster_config(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.get_cluster_config(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_UPGRADE_PLAN)
def cluster_upgrade_plan(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade-plan operation.

    data validation handled in broker

    :return: List[Tuple(str, str)]
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.get_cluster_upgrade_plan(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_UPGRADE)
def cluster_upgrade(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade operation.

    data validation handled in broker

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.upgrade_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_LIST)
def cluster_list(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: List
    """
    vcd_broker = VcdBroker(op_ctx)
    page_number = int(request_data.get(PaginationKey.PAGE_NUMBER, CSE_PAGINATION_FIRST_PAGE_NUMBER))  # noqa: E501
    page_size = int(request_data.get(PaginationKey.PAGE_SIZE, CSE_PAGINATION_DEFAULT_PAGE_SIZE))  # noqa: E501
    # remove page number and page size from the filters as it is treated
    # differently from other filters
    if PaginationKey.PAGE_NUMBER in request_data:
        del request_data[PaginationKey.PAGE_NUMBER]
    if PaginationKey.PAGE_SIZE in request_data:
        del request_data[PaginationKey.PAGE_SIZE]

    vcd_clusters_info = vcd_broker.list_clusters(data=request_data,
                                                 page_number=page_number,
                                                 page_size=page_size)

    common_cluster_properties = [
        'name',
        'vdc',
        'status',
        'org_name',
        'k8s_version',
        K8S_PROVIDER_KEY
    ]

    result = []
    for cluster_info in vcd_clusters_info[PaginationKey.VALUES]:
        filtered_cluster_info = \
            {k: cluster_info.get(k) for k in common_cluster_properties}
        result.append(filtered_cluster_info)

    base_url = f"{op_ctx.client.get_api_uri().strip('/')}{CseOperationInfo.CLUSTER_LIST._api_path_format}"  # noqa: E501
    return utils.create_links_and_construct_paginated_result(base_url, result,
                                                             page_number=page_number,  # noqa: E501
                                                             page_size=page_size,  # noqa: E501
                                                             query_params=request_data)  # noqa: E501


@record_user_action_telemetry(cse_operation=CseOperation.NODE_CREATE)
def node_create(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node create operation.

    Required data: cluster_name, network_name
    Optional data and default values: org_name=None, ovdc_name=None,
        num_nodes=1, num_cpu=None, mb_memory=None, storage_profile_name=None,
        template_name=default, template_revision=default,
        ssh_key=None, rollback=True, enable_nfs=False,

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.create_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.NODE_DELETE)
def node_delete(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.delete_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.NODE_INFO)
def node_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    vcd_broker = VcdBroker(op_ctx)
    return vcd_broker.get_node_info(data=request_data)
