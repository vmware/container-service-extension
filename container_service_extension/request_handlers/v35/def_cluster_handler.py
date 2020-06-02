# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.def_modules.models import ClusterEntity
from container_service_extension.request_context import RequestContext
from container_service_extension.server_constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_telemetry
from container_service_extension.def_modules.cluster_svc import DefClusterService


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_CREATE)
def cluster_create(request_data, request_context: RequestContext):
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
    cluster_svc = DefClusterService(request_context)
    cluster_entity_spec = ClusterEntity(**request_context.request_body)
    return cluster_svc.create_cluster(cluster_entity_spec)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_RESIZE)
def cluster_resize(request_data, request_context: RequestContext):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None
    Conditional data and default values:
            network_name, rollback=True

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.resize_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_DELETE)
def cluster_delete(request_data, request_context: RequestContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.delete_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_INFO)
def cluster_info(request_data, request_context: RequestContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.get_cluster_info(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_CONFIG)
def cluster_config(request_data, request_context: RequestContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.get_cluster_config(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_UPGRADE_PLAN)
def cluster_upgrade_plan(request_data, request_context: RequestContext):
    """Request handler for cluster upgrade-plan operation.

    data validation handled in broker

    :return: List[Tuple(str, str)]
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.get_cluster_upgrade_plan(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_UPGRADE)
def cluster_upgrade(request_data, request_context: RequestContext):
    """Request handler for cluster upgrade operation.

    data validation handled in broker

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.upgrade_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_LIST)
def cluster_list(request_data, request_context: RequestContext):
    """Request handler for cluster list operation.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: List
    """
    cluster_svc = DefClusterService(request_context)
    vcd_clusters_info = cluster_svc.list_clusters(data=request_data)
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

@record_user_action_telemetry(cse_operation=CseOperation.NODE_CREATE)
def node_create(request_data, request_context: RequestContext):
    """Request handler for node create operation.

    Required data: cluster_name, network_name
    Optional data and default values: org_name=None, ovdc_name=None,
        num_nodes=1, num_cpu=None, mb_memory=None, storage_profile_name=None,
        template_name=default, template_revision=default,
        ssh_key=None, rollback=True, enable_nfs=False,

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.create_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.NODE_DELETE)
def node_delete(request_data, request_context: RequestContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.delete_nodes(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.NODE_INFO)
def node_info(request_data, request_context: RequestContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    cluster_svc = DefClusterService(request_context)
    return cluster_svc.get_node_info(data=request_data)


OPERATION_TO_METHOD = {
    CseOperation.CLUSTER_CONFIG: cluster_config,
    CseOperation.CLUSTER_CREATE: cluster_create,
    CseOperation.CLUSTER_DELETE: cluster_delete,
    CseOperation.CLUSTER_INFO: cluster_info,
    CseOperation.CLUSTER_LIST: cluster_list,
    CseOperation.CLUSTER_RESIZE: cluster_resize,
    CseOperation.CLUSTER_UPGRADE_PLAN: cluster_upgrade_plan,  # noqa: E501
    CseOperation.CLUSTER_UPGRADE: cluster_upgrade,
    CseOperation.NODE_CREATE: node_create,
    CseOperation.NODE_DELETE: node_delete,
    CseOperation.NODE_INFO: node_info,
}
    
    
    

