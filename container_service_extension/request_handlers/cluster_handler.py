import container_service_extension.broker_manager as broker_manager
from container_service_extension.exceptions import ClusterAlreadyExistsError
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pksbroker_manager as pks_broker_manager
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.server_constants import PKS_PLANS_KEY
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils
from container_service_extension.vcdbroker import VcdBroker


def cluster_create(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, ovdc_name, cluster_name, num_nodes.
    Conditional data: if k8s_provider is 'native', num_cpu, mb_memory,
        network_name, storage_profile_name, template_name, template_revision,
        enable_nfs, rollback are required (validation handled elsewhere).

    :return: Dict
    """
    cluster_name = request_data[RequestKey.CLUSTER_NAME]
    # TODO HACK 'is_org_admin_search' is used here to prevent users from
    # creating clusters with the same name, including clusters in PKS
    # True means that the cluster list is filtered by the org name of
    # the logged-in user to check that there are no duplicate clusters
    request_data['is_org_admin_search'] = True
    cluster, _ = broker_manager.find_cluster_in_org(request_data,
                                                    tenant_auth_token)
    if cluster is not None:
        raise ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                        f"already exists.")

    k8s_metadata = \
        ovdc_utils.get_ovdc_k8s_provider_metadata(
            org_name=request_data[RequestKey.ORG_NAME],
            ovdc_name=request_data[RequestKey.OVDC_NAME],
            include_credentials=True,
            include_nsxt_info=True)
    if k8s_metadata.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
        request_data[RequestKey.PKS_PLAN_NAME] = k8s_metadata[PKS_PLANS_KEY][0]
        request_data['pks_ext_host'] = \
            f"{cluster_name}.{k8s_metadata[PKS_CLUSTER_DOMAIN_KEY]}"
    broker = broker_manager.get_broker_from_k8s_metadata(k8s_metadata,
                                                         tenant_auth_token)
    return broker.create_cluster(request_data)


def cluster_resize(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name, num_nodes.
    Conditional data: if k8s_provider is 'native', network_name,
        rollback are required (validation handled elsewhere).
    Optional data: ovdc_name.

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data,
                                                tenant_auth_token)
    return broker.resize_cluster(request_data)


def cluster_delete(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data,
                                                tenant_auth_token)
    return broker.delete_cluster(request_data)


def cluster_info(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    cluster, _ = broker_manager.get_cluster_info(request_data,
                                                 tenant_auth_token)
    return cluster


def cluster_config(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data,
                                                tenant_auth_token)
    return broker.get_cluster_config(request_data)


def cluster_list(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    All (vCD/PKS) brokers in the org do 'list cluster' operation.
    Post-process the result returned by pks broker.
    Aggregate all the results into a list.

    :return: List
    """
    vcd_clusters_info = \
        VcdBroker(tenant_auth_token).list_clusters(request_data)

    pks_clusters_info = []
    if utils.is_pks_enabled():
        pks_clusters_info = pks_broker_manager.list_clusters(request_data,
                                                             tenant_auth_token)
    all_cluster_infos = vcd_clusters_info + pks_clusters_info

    common_cluster_properties = [
        'name',
        'vdc',
        'status',
        'org_name',
        K8S_PROVIDER_KEY
    ]

    result = []
    for cluster_info in all_cluster_infos:
        filtered_cluster_info = \
            {k: cluster_info.get(k) for k in common_cluster_properties}
        result.append(filtered_cluster_info)

    return result


def node_create(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org name, ovdc name, cluster name, num nodes, num cpu,
        mb memory, network name, storage profile name, template name,
        template_revision, rollback, enable nfs.

    :return: Dict
    """
    # Currently node create is a vCD only operation.
    # Different from resize because this can create nfs nodes
    return VcdBroker(tenant_auth_token).create_nodes(request_data)


def node_delete(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name, node_names_list.
    Optional data: ssh_key_file, ovdc_name.

    :return: Dict
    """
    # Currently node delete is a vCD only operation.
    # TODO remove once resize is able to scale down native clusters
    return VcdBroker(tenant_auth_token).delete_nodes(request_data)


def node_info(request_data, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name, node_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    # Currently node info is a vCD only operation.
    return VcdBroker(tenant_auth_token).get_node_info(request_data)
