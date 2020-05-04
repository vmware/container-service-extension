# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.broker_manager as broker_manager
import container_service_extension.exceptions as e
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pksbroker_manager as pksbroker_manager
import container_service_extension.request_context as ctx
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.server_constants import PKS_PLANS_KEY
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry # noqa: E501
import container_service_extension.utils as utils
import container_service_extension.vcdbroker as vcdbroker


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_CREATE)
def cluster_create(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster create operation.

    Required data: org_name, ovdc_name, cluster_name
    Conditional data and default values:
        if k8s_provider is 'native':
            network_name, num_nodes=2, num_cpu=None, mb_memory=None,
            storage_profile_name=None, template_name=default,
            template_revision=default, ssh_key=None, enable_nfs=False,
            rollback=True

    (data validation handled in brokers)

    :return: Dict
    """
    required = [
        RequestKey.CLUSTER_NAME
    ]
    req_utils.validate_payload(request_data, required)

    cluster_name = request_data[RequestKey.CLUSTER_NAME]
    # TODO HACK 'is_org_admin_search' is used here to prevent users from
    # creating clusters with the same name, including clusters in PKS
    # True means that the cluster list is filtered by the org name of
    # the logged-in user to check that there are no duplicate clusters
    request_data['is_org_admin_search'] = True

    try:
        broker_manager.get_cluster_and_broker(request_data, request_context)
        raise e.ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                          f"already exists.")
    except e.ClusterNotFoundError:
        pass

    k8s_metadata = ovdc_utils.get_ovdc_k8s_provider_metadata(
        request_context.sysadmin_client,
        org_name=request_data[RequestKey.ORG_NAME],
        ovdc_name=request_data[RequestKey.OVDC_NAME],
        include_credentials=True,
        include_nsxt_info=True)
    if k8s_metadata.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
        request_data[RequestKey.PKS_PLAN_NAME] = k8s_metadata[PKS_PLANS_KEY][0]
        request_data[RequestKey.PKS_EXT_HOST] = \
            f"{cluster_name}.{k8s_metadata[PKS_CLUSTER_DOMAIN_KEY]}"
    broker = broker_manager.get_broker_from_k8s_metadata(k8s_metadata,
                                                         request_context)
    return broker.create_cluster(request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_RESIZE)
def cluster_resize(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None
    Conditional data and default values:
        if k8s_provider is 'native':
            network_name, rollback=True

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    return broker.resize_cluster(request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_DELETE)
def cluster_delete(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    return broker.delete_cluster(request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_INFO)
def cluster_info(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    cluster, _ = broker_manager.get_cluster_info(request_data, request_context)
    return cluster


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_CONFIG)
def cluster_config(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    return broker.get_cluster_config(request_data)


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_UPGRADE_PLAN)
def cluster_upgrade_plan(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster upgrade-plan operation.

    data validation handled in broker

    :return: List[Tuple(str, str)]
    """
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    if isinstance(broker, vcdbroker.VcdBroker):
        return broker.get_cluster_upgrade_plan(request_data)

    raise e.BadRequestError(
        error_message="'cluster upgrade-plan' operation is not supported by "
                      "non native clusters.")


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_UPGRADE)
def cluster_upgrade(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster upgrade operation.

    data validation handled in broker

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    if isinstance(broker, vcdbroker.VcdBroker):
        return broker.upgrade_cluster(request_data)

    raise e.BadRequestError(
        error_message="'cluster upgrade' operation is not supported by non "
                      "native clusters.")


@record_user_action_telemetry(cse_operation=CseOperation.CLUSTER_LIST)
def cluster_list(request_data, request_context: ctx.RequestContext):
    """Request handler for cluster list operation.

    All (vCD/PKS) brokers in the org do 'list cluster' operation.
    Post-process the result returned by pks broker.
    Aggregate all the results into a list.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: List
    """
    vcd_broker = vcdbroker.VcdBroker(request_context)
    vcd_clusters_info = vcd_broker.list_clusters(request_data)

    pks_clusters_info = []
    if utils.is_pks_enabled():
        pks_clusters_info = pksbroker_manager.list_clusters(request_data,
                                                            request_context)
    all_clusters = vcd_clusters_info + pks_clusters_info

    common_cluster_properties = [
        'name',
        'vdc',
        'status',
        'org_name',
        'k8s_type',
        'k8s_version',
        K8S_PROVIDER_KEY,
    ]

    clusters = []
    for cluster in all_clusters:
        clusters.append({k: cluster.get(k) for k in common_cluster_properties})

    return clusters


@record_user_action_telemetry(cse_operation=CseOperation.NODE_CREATE)
def node_create(request_data, request_context: ctx.RequestContext):
    """Request handler for node create operation.

    Required data: cluster_name, network_name
    Optional data and default values: org_name=None, ovdc_name=None,
        num_nodes=1, num_cpu=None, mb_memory=None, storage_profile_name=None,
        template_name=default, template_revision=default,
        ssh_key=None, rollback=True, enable_nfs=False,

    (data validation handled in brokers)

    :return: Dict
    """
    # Currently node create is a vCD only operation.
    # Different from resize because this can create nfs nodes
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    if isinstance(broker, vcdbroker.VcdBroker):
        return broker.create_nodes(request_data)

    raise e.BadRequestError(
        error_message="'node create' operation is not supported by non native "
                      "clusters.")


@record_user_action_telemetry(cse_operation=CseOperation.NODE_DELETE)
def node_delete(request_data, request_context: ctx.RequestContext):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    if isinstance(broker, vcdbroker.VcdBroker):
        return broker.delete_nodes(request_data)

    raise e.BadRequestError(
        error_message="'node delete' operation is not supported by non native "
                      "clusters.")


@record_user_action_telemetry(cse_operation=CseOperation.NODE_INFO)
def node_info(request_data, request_context: ctx.RequestContext):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    # Currently node info is a vCD only operation.
    _, broker = broker_manager.get_cluster_info(request_data, request_context)
    if isinstance(broker, vcdbroker.VcdBroker):
        return broker.get_node_info(request_data)

    raise e.BadRequestError(
        error_message="'node info' operation is not supported by non native "
                      "clusters.")
