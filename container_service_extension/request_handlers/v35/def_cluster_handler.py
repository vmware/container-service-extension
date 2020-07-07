# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict

import container_service_extension.def_.cluster_service as cluster_svc
import container_service_extension.def_.models as def_models
import container_service_extension.operation_context as ctx
import container_service_extension.request_handlers.request_utils as request_utils  # noqa: E501
import container_service_extension.server_constants as const
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_telemetry

_OPERATION_KEY = 'operation'


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_CREATE)
@request_utils.v35_api_exception_handler
def cluster_create(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster create operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_entity_spec = def_models.ClusterEntity(**data[RequestKey.V35_SPEC])
    return svc.create_cluster(cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_RESIZE)
@request_utils.v35_api_exception_handler
def cluster_resize(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    cluster_entity_spec = def_models.ClusterEntity(**data[RequestKey.V35_SPEC])
    return svc.resize_cluster(cluster_id, cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_DELETE)
@request_utils.v35_api_exception_handler
def cluster_delete(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.delete_cluster(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_INFO)
@request_utils.v35_api_exception_handler
def cluster_info(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return asdict(svc.get_cluster_info(cluster_id))


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_CONFIG)
@request_utils.v35_api_exception_handler
def cluster_config(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.get_cluster_config(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_UPGRADE_PLAN)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_upgrade_plan(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade-plan operation.

    :return: List[Tuple(str, str)]
    """
    svc = cluster_svc.ClusterService(op_ctx)
    return svc.get_cluster_upgrade_plan(data[RequestKey.CLUSTER_ID])


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_UPGRADE)
@request_utils.v35_api_exception_handler
def cluster_upgrade(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade operation.

    data validation handled in broker

    :return: Dict
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_entity_spec = def_models.ClusterEntity(**data[RequestKey.V35_SPEC])
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.upgrade_cluster(cluster_id, cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_LIST)
@request_utils.v35_api_exception_handler
def cluster_list(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    :return: List
    """
    svc = cluster_svc.ClusterService(op_ctx)
    return [asdict(def_entity) for def_entity in
            svc.list_clusters(data.get(RequestKey.V35_QUERY, None))]


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_CREATE)
@request_utils.v35_api_exception_handler
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
    raise NotImplementedError
    svc = cluster_svc.ClusterService(op_ctx)
    return svc.create_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_DELETE)
@request_utils.v35_api_exception_handler
def node_delete(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(op_ctx)
    return svc.delete_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_INFO)
@request_utils.v35_api_exception_handler
def node_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(op_ctx)
    return svc.get_node_info(data=request_data)
