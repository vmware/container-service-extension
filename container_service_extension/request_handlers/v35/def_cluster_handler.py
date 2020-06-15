# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict

import container_service_extension.def_.cluster_service as cluster_svc
import container_service_extension.def_.models as def_models
import container_service_extension.exceptions as cse_exception
from container_service_extension.request_context import RequestContext
import container_service_extension.security_context as ctx
import container_service_extension.server_constants as const
from container_service_extension.shared_constants import OperationType
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RequestMethod
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_telemetry

_OPERATION_KEY = 'operation'


def _get_url_data(method: str, url: str):
    tokens = url.split('/')
    num_tokens = len(tokens)

    if num_tokens < 5:
        raise cse_exception.NotFoundRequestError()

    operation_type = tokens[4].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == OperationType.CLUSTER:
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: const.CseOperation.CLUSTER_LIST}
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: const.CseOperation.CLUSTER_CREATE}
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 6:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: const.CseOperation.CLUSTER_INFO,
                    RequestKey.CLUSTER_ID: tokens[5]
                }
            if method == RequestMethod.PUT:
                return {
                    _OPERATION_KEY: const.CseOperation.CLUSTER_RESIZE,
                    RequestKey.CLUSTER_ID: tokens[5]
                }
            if method == RequestMethod.DELETE:
                return {
                    _OPERATION_KEY: const.CseOperation.CLUSTER_DELETE,
                    RequestKey.CLUSTER_ID: tokens[5]
                }
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 7:
            if method == RequestMethod.GET:
                if tokens[6] == 'config':
                    return {
                        _OPERATION_KEY: const.CseOperation.CLUSTER_CONFIG,
                        RequestKey.CLUSTER_ID: tokens[5]
                    }
                if tokens[6] == 'upgrade-plan':
                    return {
                        _OPERATION_KEY: const.CseOperation.CLUSTER_UPGRADE_PLAN,  # noqa: E501
                        RequestKey.CLUSTER_ID: tokens[5]
                    }
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 8:
            if method == RequestMethod.POST:
                if tokens[6] == 'action' and tokens[7] == 'upgrade':
                    return {
                        _OPERATION_KEY: const.CseOperation.CLUSTER_UPGRADE,
                        RequestKey.CLUSTER_ID: tokens[5]
                    }
            raise cse_exception.MethodNotAllowedRequestError()


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_CREATE)
def cluster_create(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    """Request handler for cluster create operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(security_ctx)
    cluster_entity_spec = def_models.ClusterEntity(**req_ctx.body)
    return svc.create_cluster(cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_RESIZE)
def cluster_resize(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None
    Conditional data and default values:
            network_name, rollback=True

    (data validation handled in broker)

    :return: Dict
    """
    svc = cluster_svc.ClusterService(security_ctx)
    cluster_id = req_ctx.url_data[RequestKey.CLUSTER_ID]
    cluster_entity_spec = def_models.ClusterEntity(**req_ctx.body)
    return svc.resize_cluster(cluster_id, cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_DELETE)
def cluster_delete(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_id = req_ctx.url_data[RequestKey.CLUSTER_ID]
    return svc.delete_cluster(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_INFO)
def cluster_info(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    svc = cluster_svc.ClusterService(security_ctx)
    cluster_id = req_ctx.url_data[RequestKey.CLUSTER_ID]
    return asdict(svc.get_cluster_info(cluster_id))


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_CONFIG)
def cluster_config(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_id = req_ctx.url_data[RequestKey.CLUSTER_ID]
    return svc.get_cluster_config(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_UPGRADE_PLAN)  # noqa: E501
def cluster_upgrade_plan(request_data, req_ctx: RequestContext,
                         security_ctx: ctx.SecurityContext):
    """Request handler for cluster upgrade-plan operation.

    data validation handled in broker

    :return: List[Tuple(str, str)]
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(req_ctx)
    return svc.get_cluster_upgrade_plan(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_UPGRADE)
def cluster_upgrade(request_data, req_ctx: RequestContext,
                    security_ctx: ctx.SecurityContext):
    """Request handler for cluster upgrade operation.

    data validation handled in broker

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(req_ctx)
    return svc.upgrade_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_LIST)
def cluster_list(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    """Request handler for cluster list operation.

    :return: List
    """
    svc = cluster_svc.ClusterService(security_ctx)
    return [asdict(def_entity) for def_entity in
            svc.list_clusters(req_ctx.query_params)]


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_CREATE)
def node_create(request_data, security_ctx: ctx.SecurityContext):
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
    svc = cluster_svc.ClusterService(security_ctx)
    return svc.create_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_DELETE)
def node_delete(request_data, security_ctx: ctx.SecurityContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(security_ctx)
    return svc.delete_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_INFO)
def node_info(request_data, security_ctx: ctx.SecurityContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    raise NotImplementedError
    svc = cluster_svc.ClusterService(security_ctx)
    return svc.get_node_info(data=request_data)


OPERATION_TO_METHOD = {
    const.CseOperation.CLUSTER_CONFIG: cluster_config,
    const.CseOperation.CLUSTER_CREATE: cluster_create,
    const.CseOperation.CLUSTER_DELETE: cluster_delete,
    const.CseOperation.CLUSTER_INFO: cluster_info,
    const.CseOperation.CLUSTER_LIST: cluster_list,
    const.CseOperation.CLUSTER_RESIZE: cluster_resize,
    const.CseOperation.CLUSTER_UPGRADE_PLAN: cluster_upgrade_plan,
    const.CseOperation.CLUSTER_UPGRADE: cluster_upgrade,
    const.CseOperation.NODE_CREATE: node_create,
    const.CseOperation.NODE_DELETE: node_delete,
    const.CseOperation.NODE_INFO: node_info,
}


def invoke(req_ctx: RequestContext, security_ctx: ctx.SecurityContext):
    req_ctx.url_data = _get_url_data(req_ctx.verb, req_ctx.url)
    operation = req_ctx.url_data[_OPERATION_KEY]
    return OPERATION_TO_METHOD[operation](req_ctx, security_ctx), operation
