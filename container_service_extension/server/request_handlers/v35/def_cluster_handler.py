# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import semantic_version

from container_service_extension.common.constants.server_constants import FlattenedClusterSpecKey1X  # noqa: E501
from container_service_extension.common.constants.server_constants import ThreadLocalData  # noqa: E501
from container_service_extension.common.constants.shared_constants import ClusterAclKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.common.constants.shared_constants import PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.lib.telemetry.constants as telemetry_constants  # noqa: E501
import container_service_extension.lib.telemetry.telemetry_handler as telemetry_handler  # noqa: E501
import container_service_extension.rde.backend.cluster_service_factory as cluster_service_factory  # noqa: E501
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.utils as rde_utils
import container_service_extension.security.context.operation_context as ctx
import container_service_extension.server.request_handlers.cluster_handler as cluster_handler  # noqa: E501
import container_service_extension.server.request_handlers.request_utils as request_utils  # noqa: E501

_OPERATION_KEY = 'operation'


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_APPLY)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_create(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster create operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_create(data=data, op_ctx=op_ctx)

    input_entity: dict = data[RequestKey.INPUT_SPEC]
    # Convert the input entity to runtime rde format.
    # Based on the runtime rde, call the appropriate backend method.
    converted_native_entity: AbstractNativeEntity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    svc = cluster_service_factory.ClusterServiceFactory(op_ctx).get_cluster_service()  # noqa: E501
    new_rde: common_models.DefEntity = svc.create_cluster(converted_native_entity)  # noqa: E501
    # convert the created rde back to input rde version
    new_native_entity: AbstractNativeEntity = rde_utils.convert_runtime_rde_to_input_rde_version_format(  # noqa: E501
        new_rde.entity, rde_constants.RDEVersion.RDE_1_0_0)
    new_rde.entity = new_native_entity
    return new_rde.to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_APPLY)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_resize(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    Validate data before actual resize is delegated to cluster service.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_update(data=data, op_ctx=op_ctx)

    input_entity: dict = data[RequestKey.INPUT_SPEC]
    # Convert the input entity to runtime rde format.
    # Based on the runtime rde, call the appropriate backend method.
    converted_native_entity: AbstractNativeEntity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    svc = cluster_service_factory.ClusterServiceFactory(op_ctx).get_cluster_service()  # noqa: E501
    cluster_id = data[RequestKey.CLUSTER_ID]

    curr_entity = svc.entity_svc.get_entity(cluster_id)
    request_utils.validate_request_payload(
        converted_native_entity.spec.to_dict(), curr_entity.entity.spec.to_dict(),  # noqa: E501
        exclude_fields=[FlattenedClusterSpecKey1X.WORKERS_COUNT.value,
                        FlattenedClusterSpecKey1X.NFS_COUNT.value,
                        FlattenedClusterSpecKey1X.EXPOSE.value])
    new_rde: common_models.DefEntity = svc.resize_cluster(cluster_id, converted_native_entity)  # noqa: E501
    # convert the resized rde back to input rde version
    new_native_entity: AbstractNativeEntity = rde_utils.convert_runtime_rde_to_input_rde_version_format(  # noqa: E501
        new_rde.entity, rde_constants.RDEVersion.RDE_1_0_0)
    new_rde.entity = new_native_entity
    return new_rde.to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_DELETE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_delete(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_delete(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.delete_cluster(cluster_id).to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_INFO)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_info(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_info(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.get_cluster_info(cluster_id).to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_CONFIG)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_config(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster config operation.

    Required data: cluster_id

    :return: Dict
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_config(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.get_cluster_config(cluster_id)


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE_PLAN)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_upgrade_plan(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade-plan operation.

    :return: List[Tuple(str, str)]
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_upgrade_plan(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    return svc.get_cluster_upgrade_plan(data[RequestKey.CLUSTER_ID])


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_upgrade(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade operation.

    Validate data before actual upgrade is delegated to cluster service.

    :return: Dict
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_update(data=data, op_ctx=op_ctx)

    input_entity: dict = data[RequestKey.INPUT_SPEC]
    # Convert the input entity to runtime rde format.
    # Based on the runtime rde, call the appropriate backend method.
    converted_native_entity: AbstractNativeEntity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    svc = cluster_service_factory.ClusterServiceFactory(op_ctx).get_cluster_service()  # noqa: E501
    cluster_id = data[RequestKey.CLUSTER_ID]
    curr_entity = svc.entity_svc.get_entity(cluster_id)
    request_utils.validate_request_payload(
        converted_native_entity.spec.to_dict(), curr_entity.entity.spec.to_dict(),  # noqa: E501
        exclude_fields=[FlattenedClusterSpecKey1X.TEMPLATE_NAME.value,
                        FlattenedClusterSpecKey1X.TEMPLATE_REVISION.value])
    new_rde: common_models.DefEntity = svc.upgrade_cluster(cluster_id, converted_native_entity)  # noqa: E501
    # convert the upgraded rde back to input rde version
    new_native_entity: AbstractNativeEntity = rde_utils.convert_runtime_rde_to_input_rde_version_format(  # noqa: E501
        new_rde.entity, rde_constants.RDEVersion.RDE_1_0_0)
    new_rde.entity = new_native_entity
    return new_rde.to_dict()


# TODO: Record telemetry in a different telemetry handler
@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def native_cluster_list(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    :return: List
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.native_cluster_list(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    filters = data.get(RequestKey.QUERY_PARAMS, {})
    page_number = int(filters.get(PaginationKey.PAGE_NUMBER,
                                  CSE_PAGINATION_FIRST_PAGE_NUMBER))
    page_size = int(filters.get(PaginationKey.PAGE_SIZE,
                                CSE_PAGINATION_DEFAULT_PAGE_SIZE))

    # remove page number and page size from the filters as it is treated
    # differently from other filters
    if PaginationKey.PAGE_NUMBER in filters:
        del filters[PaginationKey.PAGE_NUMBER]
    if PaginationKey.PAGE_SIZE in filters:
        del filters[PaginationKey.PAGE_SIZE]

    # response needs to paginated
    result = svc.get_clusters_by_page(filters=filters)
    clusters = [def_entity.to_dict() for def_entity in result[PaginationKey.VALUES]]  # noqa: E501

    uri = data['url']
    return server_utils.create_links_and_construct_paginated_result(
        uri,
        clusters,
        result_total=result[PaginationKey.RESULT_TOTAL],
        page_number=page_number,
        page_size=page_size,
        query_params=filters)


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_ACL_LIST)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_acl_info(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster acl list operation."""
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_acl_info(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    cluster_id = data[RequestKey.CLUSTER_ID]
    query = data.get(RequestKey.QUERY_PARAMS, {})
    page = int(query.get(PaginationKey.PAGE_NUMBER, CSE_PAGINATION_FIRST_PAGE_NUMBER))  # noqa: E501
    page_size = int(query.get(PaginationKey.PAGE_SIZE, CSE_PAGINATION_DEFAULT_PAGE_SIZE))  # noqa: E501
    result: dict = svc.get_cluster_acl_info(cluster_id, page, page_size)

    uri = data['url']
    return server_utils.create_links_and_construct_paginated_result(
        base_uri=uri,
        values=result.get(PaginationKey.VALUES, []),
        result_total=result.get(PaginationKey.RESULT_TOTAL, 0),
        page_number=page,
        page_size=page_size)


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_ACL_UPDATE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_acl_update(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster acl update operation."""
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_acl_update(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    cluster_id = data[RequestKey.CLUSTER_ID]
    update_acl_entries = data.get(RequestKey.INPUT_SPEC, {}).get(ClusterAclKey.ACCESS_SETTING)  # noqa: E501
    svc.update_cluster_acl(cluster_id, update_acl_entries)


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_LIST)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_list(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    :return: List
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) >= semantic_version.Version(rde_constants.RDEVersion.RDE_2_0_0.value):  # noqa: E501
        return cluster_handler.cluster_list(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)

    # response should not be paginated
    return [def_entity.to_dict() for def_entity in
            svc.list_clusters(data.get(RequestKey.QUERY_PARAMS, {}))]


@request_utils.cluster_api_exception_handler
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
@request_utils.cluster_api_exception_handler
def nfs_node_delete(data, op_ctx: ctx.OperationContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    rde_in_use = server_utils.get_rde_version_in_use()
    if semantic_version.Version(rde_in_use) > semantic_version.Version(rde_constants.RDEVersion.RDE_1_0_0.value):  # noqa: E501
        return cluster_handler.nfs_node_delete(data=data, op_ctx=op_ctx)

    svc = cluster_service_factory.ClusterServiceFactory(op_ctx). \
        get_cluster_service(rde_in_use)
    cluster_id = data[RequestKey.CLUSTER_ID]
    node_name = data[RequestKey.NODE_NAME]

    telemetry_handler.record_user_action_details(
        cse_operation=telemetry_constants.CseOperation.V35_NODE_DELETE,
        cse_params={
            telemetry_constants.PayloadKey.CLUSTER_ID: cluster_id,
            telemetry_constants.PayloadKey.NODE_NAME: node_name,
            telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)   # noqa: E501
        }
    )

    return svc.delete_nodes(cluster_id, [node_name]).to_dict()


@request_utils.cluster_api_exception_handler
def node_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
