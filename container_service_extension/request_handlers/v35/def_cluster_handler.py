# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict

import container_service_extension.def_.cluster_service as cluster_svc
import container_service_extension.def_.models as def_models
import container_service_extension.operation_context as ctx
import container_service_extension.request_handlers.request_utils as request_utils  # noqa: E501
from container_service_extension.shared_constants import FlattenedClusterSpecKey  # noqa: E501
from container_service_extension.shared_constants import RequestKey
import container_service_extension.telemetry.constants as telemetry_constants
import container_service_extension.telemetry.telemetry_handler as telemetry_handler  # noqa: E501


_OPERATION_KEY = 'operation'


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_APPLY)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_create(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster create operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_entity_spec = def_models.ClusterEntity(**data[RequestKey.V35_SPEC])
    return asdict(svc.create_cluster(cluster_entity_spec))


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_APPLY)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_resize(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    Validate data before actual resize is delegated to cluster service.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    cluster_entity_spec = def_models.ClusterEntity(**data[RequestKey.V35_SPEC])
    curr_entity = svc.entity_svc.get_entity(cluster_id)
    request_utils.validate_request_payload(
        asdict(cluster_entity_spec.spec), asdict(curr_entity.entity.spec),
        exclude_fields=[FlattenedClusterSpecKey.WORKERS_COUNT.value,
                        FlattenedClusterSpecKey.NFS_COUNT.value])
    return asdict(svc.resize_cluster(cluster_id, cluster_entity_spec))


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_DELETE)  # noqa: E501
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
    return asdict(svc.delete_cluster(cluster_id))


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_INFO)  # noqa: E501
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


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_CONFIG)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_config(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster config operation.

    Required data: cluster_id

    :return: Dict
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.get_cluster_config(cluster_id)


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE_PLAN)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_upgrade_plan(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade-plan operation.

    :return: List[Tuple(str, str)]
    """
    svc = cluster_svc.ClusterService(op_ctx)
    return svc.get_cluster_upgrade_plan(data[RequestKey.CLUSTER_ID])


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_upgrade(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade operation.

    Validate data before actual upgrade is delegated to cluster service.

    :return: Dict
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_entity_spec = def_models.ClusterEntity(**data[RequestKey.V35_SPEC])
    cluster_id = data[RequestKey.CLUSTER_ID]
    curr_entity = svc.entity_svc.get_entity(cluster_id)
    request_utils.validate_request_payload(
        asdict(cluster_entity_spec.spec), asdict(curr_entity.entity.spec),
        exclude_fields=[FlattenedClusterSpecKey.TEMPLATE_NAME.value,
                        FlattenedClusterSpecKey.TEMPLATE_REVISION.value])
    return asdict(svc.upgrade_cluster(cluster_id, cluster_entity_spec))


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_LIST)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_list(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    :return: List
    """
    svc = cluster_svc.ClusterService(op_ctx)
    return [asdict(def_entity) for def_entity in
            svc.list_clusters(data.get(RequestKey.V35_QUERY, {}))]


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


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_NODE_DELETE)  # noqa: E501
@request_utils.v35_api_exception_handler
def nfs_node_delete(data, op_ctx: ctx.OperationContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    node_name = data[RequestKey.NODE_NAME]

    telemetry_handler.record_user_action_details(
        cse_operation=telemetry_constants.CseOperation.V35_NODE_DELETE,
        cse_params={
            telemetry_constants.PayloadKey.CLUSTER_ID: cluster_id,
            telemetry_constants.PayloadKey.NODE_NAME: node_name
        }
    )

    return asdict(svc.delete_nodes(cluster_id, [node_name]))


@request_utils.v35_api_exception_handler
def node_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
