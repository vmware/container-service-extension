# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Support CSE 3.1 cluster requests.

Starting CSE 3.1, this module handles all the cluster requests coming in at
any RDE version (>= 2.0) and at any request api_version (>=36).

Responsibility of the functions in this file:
1. Validate the Input payload based on the (Operation, payload_version).
   Get the validator based on the payload_version.
2. Convert the input entity to runtime rde format.
3. Based on the runtime rde, call the appropriate backend method.
4. Convert the response to be compatible with the request payload
   version (If request = X.Y, the response must be X.Z where Z>=Y)
5. Return the response.
"""

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
from container_service_extension.common.constants.shared_constants import ClusterAclKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.common.constants.shared_constants import PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as pyvcloud_utils  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.lib.telemetry.constants as telemetry_constants  # noqa: E501
import container_service_extension.lib.telemetry.telemetry_handler as telemetry_handler  # noqa: E501
import container_service_extension.rde.backend.cluster_service_factory as cluster_service_factory  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import DELETE_NFS_NODE_BEHAVIOR_ID  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import KUBE_CONFIG_BEHAVIOR_INTERFACE_ID  # noqa: E501
from container_service_extension.rde.behaviors.behavior_service import BehaviorService  # noqa: E501
import container_service_extension.rde.common.entity_service as entity_service
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.utils as rde_utils
import container_service_extension.rde.validators.validator_factory as rde_validator_factory  # noqa: E501
import container_service_extension.security.context.behavior_request_context as behavior_ctx  # noqa: E501
import container_service_extension.security.context.operation_context as ctx
import container_service_extension.server.request_handlers.request_utils as request_utils  # noqa: E501

# TODO: Needs to evaluate if we want to handle RDE 1.0 requests coming
#  in at 36.0 in this handler.


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_APPLY)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_create(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster create operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    input_entity: dict = data[RequestKey.INPUT_SPEC]
    payload_version = input_entity.get(rde_constants.PayloadKey.PAYLOAD_VERSION)  # noqa: E501
    rde_utils.raise_error_if_unsupported_payload_version(payload_version)

    # Validate the Input payload based on the (Operation, payload_version).
    # Get the validator based on the payload_version
    # ToDo : Don't use default cloudapi_client. Use the specific versioned one
    rde_validator_factory.get_validator(
        rde_version=rde_constants.MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION[
            payload_version]).validate(cloudapi_client=op_ctx.cloudapi_client,
                                       entity=input_entity)

    def_entity_service = entity_service.DefEntityService(op_ctx.cloudapi_client)  # noqa: E501
    entity_type = server_utils.get_registered_def_entity_type()
    converted_entity: AbstractNativeEntity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    def_entity = common_models.DefEntity(entity=converted_entity, entityType=entity_type.id)  # noqa: E501

    # No need to set org context for non sysadmin users
    org_context = None
    if op_ctx.client.is_sysadmin():
        org_resource = pyvcloud_utils.get_org(op_ctx.client, org_name=converted_entity.metadata.org_name)  # noqa: E501
        org_context = org_resource.href.split('/')[-1]

    _, task_href = def_entity_service.create_entity(
        entity_type_id=entity_type.id,
        entity=def_entity,
        tenant_org_context=org_context,
        is_request_async=True)

    task_resource = op_ctx.sysadmin_client.get_resource(task_href)
    entity_id = task_resource.Owner.get('id')
    def_entity = def_entity_service.get_entity(entity_id)
    def_entity.entity.status.task_href = task_href
    return def_entity.to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_LIST)  # noqa: E501
@request_utils.cluster_api_exception_handler
def native_cluster_list(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    :return: List
    """
    svc = cluster_service_factory.ClusterServiceFactory(_get_request_context(op_ctx)).get_cluster_service()  # noqa: E501
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


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_LIST)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_list(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    :return: List
    """
    svc = cluster_service_factory.ClusterServiceFactory(_get_request_context(op_ctx)).get_cluster_service()  # noqa: E501
    # response should not be paginated
    return [def_entity.to_dict() for def_entity in
            svc.list_clusters(data.get(RequestKey.QUERY_PARAMS, {}))]


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_INFO)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_info(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    svc = cluster_service_factory.ClusterServiceFactory(_get_request_context(op_ctx)).get_cluster_service()  # noqa: E501
    cluster_id = data[RequestKey.CLUSTER_ID]
    return svc.get_cluster_info(cluster_id).to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_CONFIG)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_config(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster config operation.

    Required data: cluster_id

    :return: Dict
    """
    cluster_id = data[RequestKey.CLUSTER_ID]
    behavior_svc = BehaviorService(cloudapi_client=op_ctx.cloudapi_client)
    config_task_href = behavior_svc.invoke_behavior(
        entity_id=cluster_id,
        behavior_interface_id=KUBE_CONFIG_BEHAVIOR_INTERFACE_ID)
    config_task = op_ctx.client.get_resource(config_task_href)
    op_ctx.client.get_task_monitor().wait_for_success(config_task)
    config_task = op_ctx.client.get_resource(config_task_href)
    return config_task.Result.ResultContent.text


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_APPLY)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_update(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    cluster_id = data[RequestKey.CLUSTER_ID]
    input_entity: dict = data[RequestKey.INPUT_SPEC]
    payload_version = input_entity.get(rde_constants.PayloadKey.PAYLOAD_VERSION)  # noqa: E501
    rde_utils.raise_error_if_unsupported_payload_version(payload_version)

    # Validate the Input payload based on the (Operation, payload_version).
    # Get the validator based on the payload_version
    # ToDo : Don't use default cloudapi_client. Use the specific versioned one
    rde_validator_factory.get_validator(
        rde_version=rde_constants.MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION[
            payload_version]). \
        validate(cloudapi_client=op_ctx.cloudapi_client, entity_id=cluster_id,
                 entity=input_entity,
                 operation=BehaviorOperation.UPDATE_CLUSTER)

    # Convert the input entity to runtime rde format.
    # Based on the runtime rde, call the appropriate backend method.
    def_entity_service = entity_service.DefEntityService(op_ctx.cloudapi_client)  # noqa: E501
    converted_native_entity: AbstractNativeEntity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    cluster_def_entity: common_models.DefEntity = def_entity_service.get_entity(cluster_id)  # noqa: E501
    cluster_def_entity.entity.spec = converted_native_entity.spec
    updated_def_entity, task_href = def_entity_service.update_entity(
        entity_id=cluster_id, entity=cluster_def_entity,
        invoke_hooks=True, is_request_async=True)
    updated_def_entity.entity.status.task_href = task_href
    # TODO: Response RDE must be compatible with the request RDE.
    #  Conversions may be needed especially if there is a major version
    #  difference in the input RDE and runtime RDE.
    return updated_def_entity.to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_UPGRADE_PLAN)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_upgrade_plan(data, op_ctx: ctx.OperationContext):
    """Request handler for cluster upgrade-plan operation.

    :return: List[Tuple(str, str)]
    """
    svc = cluster_service_factory.ClusterServiceFactory(_get_request_context(op_ctx)).get_cluster_service()  # noqa: E501
    return svc.get_cluster_upgrade_plan(data[RequestKey.CLUSTER_ID])


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_DELETE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_delete(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_id = data[RequestKey.CLUSTER_ID]
    def_entity_service = entity_service.DefEntityService(op_ctx.cloudapi_client)  # noqa: E501
    def_entity: common_models.DefEntity = def_entity_service.get_entity(cluster_id)  # noqa: E501
    _, task_href = def_entity_service.delete_entity(cluster_id, invoke_hooks=True, is_request_async=True)  # noqa: E501
    def_entity.entity.status.task_href = task_href
    return def_entity.to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_NODE_DELETE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def nfs_node_delete(data, op_ctx: ctx.OperationContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_id = data[RequestKey.CLUSTER_ID]
    node_name = data[RequestKey.NODE_NAME]
    behavior_svc = BehaviorService(cloudapi_client=op_ctx.cloudapi_client)
    telemetry_handler.record_user_action_details(
        cse_operation=telemetry_constants.CseOperation.V36_NODE_DELETE,
        cse_params={
            telemetry_constants.PayloadKey.CLUSTER_ID: cluster_id,
            telemetry_constants.PayloadKey.NODE_NAME: node_name,
            telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(server_constants.ThreadLocalData.USER_AGENT)   # noqa: E501
        }
    )
    delete_nfs_node_task = behavior_svc.invoke_behavior(
        entity_id=cluster_id,
        behavior_interface_id=DELETE_NFS_NODE_BEHAVIOR_ID,
        arguments={
            RequestKey.NODE_NAME.value: node_name
        })
    def_entity_service = entity_service.DefEntityService(op_ctx.cloudapi_client)  # noqa: E501
    cluster_def_entity: common_models.DefEntity = def_entity_service.get_entity(cluster_id)  # noqa: E501
    cluster_def_entity.entity.status.task_href = delete_nfs_node_task

    return cluster_def_entity.to_dict()


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_ACL_LIST)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_acl_info(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster acl list operation."""
    svc = cluster_service_factory.ClusterServiceFactory(_get_request_context(op_ctx)).get_cluster_service()  # noqa: E501
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


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_ACL_UPDATE)  # noqa: E501
@request_utils.cluster_api_exception_handler
def cluster_acl_update(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster acl update operation."""
    svc = cluster_service_factory.ClusterServiceFactory(_get_request_context(op_ctx)).get_cluster_service()  # noqa: E501
    cluster_id = data[RequestKey.CLUSTER_ID]
    update_acl_entries = data.get(RequestKey.INPUT_SPEC, {}).get(ClusterAclKey.ACCESS_SETTING)  # noqa: E501
    svc.update_cluster_acl(cluster_id, update_acl_entries)


def _get_request_context(op_ctx: ctx.OperationContext):
    """Get the request context from operation context.

    :param op_ctx: operation context
    :return: RequestContext
    :rtype: behavior_ctx.RequestContext
    """
    return behavior_ctx.RequestContext(op_ctx=op_ctx, mqtt_publisher=op_ctx.mqtt_publisher)  # noqa: E501
