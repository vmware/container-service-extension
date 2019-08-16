import container_service_extension.broker_manager as broker_manager
from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterNotFoundError
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
    """Request handler for cluster create operation.

    Required data: org_name, ovdc_name, cluster_name
    Conditional data and default values:
        if k8s_provider is 'native':
            network_name, num_nodes=2, num_cpu=None, mb_memory=None,
            storage_profile_name=None, template_name=default,
            template_revision=default, ssh_key_filepath=None, enable_nfs=False,
            rollback=True

    (data validation handled in brokers)

    :return: Dict
    """
    required = [
        RequestKey.CLUSTER_NAME
    ]
    utils.ensure_keys_in_dict(required, request_data, dict_name='data')
    cluster_name = request_data[RequestKey.CLUSTER_NAME]
    # TODO HACK 'is_org_admin_search' is used here to prevent users from
    # creating clusters with the same name, including clusters in PKS
    # True means that the cluster list is filtered by the org name of
    # the logged-in user to check that there are no duplicate clusters
    request_data['is_org_admin_search'] = True

    try:
        broker_manager.get_cluster_and_broker(request_data, tenant_auth_token)
        raise ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                        f"already exists.")
    except ClusterNotFoundError:
        pass

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
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None
    Conditional data and default values:
        if k8s_provider is 'native':
            network_name, rollback=True

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data,
                                                tenant_auth_token)
    return broker.resize_cluster(request_data)


def cluster_delete(request_data, tenant_auth_token):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data,
                                                tenant_auth_token)
    return broker.delete_cluster(request_data)


def cluster_info(request_data, tenant_auth_token):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    cluster, _ = broker_manager.get_cluster_info(request_data,
                                                 tenant_auth_token)
    return cluster


def cluster_config(request_data, tenant_auth_token):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    _, broker = broker_manager.get_cluster_info(request_data,
                                                tenant_auth_token)
    return broker.get_cluster_config(request_data)


def cluster_list(request_data, tenant_auth_token):
    """Request handler for cluster list operation.

    All (vCD/PKS) brokers in the org do 'list cluster' operation.
    Post-process the result returned by pks broker.
    Aggregate all the results into a list.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

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
    """Request handler for node create operation.

    Required data: cluster_name, network_name
    Optional data and default values: org_name=None, ovdc_name=None,
        num_nodes=1, num_cpu=None, mb_memory=None, storage_profile_name=None,
        template_name=default, template_revision=default,
        ssh_key_filepath=None, rollback=True, enable_nfs=False,

    (data validation handled in brokers)

    :return: Dict
    """
    # Currently node create is a vCD only operation.
    # Different from resize because this can create nfs nodes
    return VcdBroker(tenant_auth_token).create_nodes(request_data)


def node_delete(request_data, tenant_auth_token):
    """Request handler for node delete operation.

    Required data: cluster_name, node_names_list
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    # Currently node delete is a vCD only operation.
    # TODO remove once resize is able to scale down native clusters
    return VcdBroker(tenant_auth_token).delete_nodes(request_data)


def node_info(request_data, tenant_auth_token):
    """Request handler for node info operation.

    Required data: cluster_name, node_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in brokers)

    :return: Dict
    """
    # Currently node info is a vCD only operation.
    return VcdBroker(tenant_auth_token).get_node_info(request_data)
