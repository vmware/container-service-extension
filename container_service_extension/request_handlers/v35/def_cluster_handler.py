# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import container_service_extension.def_.cluster_svc as cluster_svc
import container_service_extension.def_.models as def_models
import container_service_extension.request_context as ctx
import container_service_extension.server_constants as const
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_telemetry


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_CREATE)
def cluster_create(req_ctx: ctx.RequestContext):
    """Request handler for cluster create operation.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_entity_spec = def_models.ClusterEntity(**req_ctx.body)  # noqa: E501
    return svc.create_cluster(cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_RESIZE)
def cluster_resize(req_ctx: ctx.RequestContext):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None
    Conditional data and default values:
            network_name, rollback=True

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_id = req_ctx.url_data['id']
    cluster_entity_spec = def_models.ClusterEntity(**req_ctx.body)  # noqa: E501
    return svc.resize_cluster(cluster_id, cluster_entity_spec)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_DELETE)
def cluster_delete(req_ctx: ctx.RequestContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_id = req_ctx.url_data['id']
    return svc.delete_cluster(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_INFO)
def cluster_info(req_ctx: ctx.RequestContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_id = req_ctx.url_data['id']
    return svc.get_cluster_info(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_CONFIG)
def cluster_config(req_ctx: ctx.RequestContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    cluster_id = req_ctx.url_data['id']
    return svc.get_cluster_config(cluster_id)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_UPGRADE_PLAN)  # noqa: E501
def cluster_upgrade_plan(request_data, req_ctx: ctx.RequestContext):
    """Request handler for cluster upgrade-plan operation.

    data validation handled in broker

    :return: List[Tuple(str, str)]
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    return svc.get_cluster_upgrade_plan(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_UPGRADE)
def cluster_upgrade(request_data, req_ctx: ctx.RequestContext):
    """Request handler for cluster upgrade operation.

    data validation handled in broker

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    return svc.upgrade_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.CLUSTER_LIST)
def cluster_list(request_data, req_ctx: ctx.RequestContext):
    """Request handler for cluster list operation.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: List
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    vcd_clusters_info = svc.list_clusters(data=request_data)
    from container_service_extension.server_constants import K8S_PROVIDER_KEY
    common_cluster_properties = [
        'name',
        'vdc',
        'status',
        'org_name',
        'k8s_version',
        K8S_PROVIDER_KEY
    ]

    result = []
    for cluster_info in vcd_clusters_info:
        filtered_cluster_info = \
            {k: cluster_info.get(k) for k in common_cluster_properties}
        result.append(filtered_cluster_info)

    return result


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_CREATE)
def node_create(request_data, req_ctx: ctx.RequestContext):
    """Request handler for node create operation.

    Required data: cluster_name, network_name
    Optional data and default values: org_name=None, ovdc_name=None,
        num_nodes=1, num_cpu=None, mb_memory=None, storage_profile_name=None,
        template_name=default, template_revision=default,
        ssh_key=None, rollback=True, enable_nfs=False,

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    return svc.create_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_DELETE)
def node_delete(request_data, req_ctx: ctx.RequestContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
    return svc.delete_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=const.CseOperation.NODE_INFO)
def node_info(request_data, req_ctx: ctx.RequestContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    pass
    svc = cluster_svc.ClusterService(req_ctx)
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
