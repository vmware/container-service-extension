from container_service_extension.broker_manager import BrokerManager
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils
from container_service_extension.vcdbroker import VcdBroker


def cluster_create(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, ovdc_name, cluster_name, num_nodes.
    Conditional data: if k8s_provider is 'native', num_cpu, mb_memory,
        network_name, storage_profile_name, template_name, template_revision,
        enable_nfs, rollback are required (validation handled elsewhere).

    :return: Dict
    """
    required = [
        RequestKey.ORG_NAME,
        RequestKey.OVDC_NAME,
        RequestKey.CLUSTER_NAME,
        RequestKey.NUM_WORKERS
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    broker_manager = BrokerManager(tenant_auth_token, request_dict)
    return broker_manager._create_cluster()


def cluster_resize(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name, num_nodes.
    Conditional data: if k8s_provider is 'native', network_name,
        rollback are required (validation handled elsewhere).
    Optional data: ovdc_name.

    :return: Dict
    """
    required = [
        RequestKey.ORG_NAME,
        RequestKey.CLUSTER_NAME,
        RequestKey.NUM_WORKERS
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    broker_manager = BrokerManager(tenant_auth_token, request_dict)
    return broker_manager._resize_cluster()


def cluster_delete(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    required = [
        RequestKey.CLUSTER_NAME,
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    broker_manager = BrokerManager(tenant_auth_token, request_dict)
    return broker_manager._delete_cluster()


def cluster_info(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    required = [
        RequestKey.CLUSTER_NAME,
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    broker_manager = BrokerManager(tenant_auth_token, request_dict)
    return broker_manager._get_cluster_info()[0]


def cluster_config(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    required = [
        RequestKey.CLUSTER_NAME,
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    broker_manager = BrokerManager(tenant_auth_token, request_dict)
    return broker_manager._get_cluster_config()


def cluster_list(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    :return: List
    """
    broker_manager = BrokerManager(tenant_auth_token, request_dict)
    return broker_manager._list_clusters()


def node_create(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org name, ovdc name, cluster name, num nodes, num cpu,
        mb memory, network name, storage profile name, template name,
        template_revision, rollback, enable nfs.

    :return: Dict
    """
    required = [
        RequestKey.ORG_NAME,
        RequestKey.CLUSTER_NAME,
        RequestKey.NUM_WORKERS,
        RequestKey.NUM_CPU,
        RequestKey.MB_MEMORY,
        RequestKey.NETWORK_NAME,
        RequestKey.STORAGE_PROFILE_NAME,
        RequestKey.TEMPLATE_NAME,
        RequestKey.TEMPLATE_REVISION,
        RequestKey.ROLLBACK,
        RequestKey.ENABLE_NFS,
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    # Currently node create is a vCD only operation.
    # Different from resize because this can create nfs nodes
    broker = VcdBroker(tenant_auth_token, request_dict)
    return broker.create_nodes()


def node_delete(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name, node_names_list.
    Optional data: ssh_key_file, ovdc_name.

    :return: Dict
    """
    required = [
        RequestKey.ORG_NAME,
        RequestKey.CLUSTER_NAME,
        RequestKey.NODE_NAMES_LIST
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    # Currently node delete is a vCD only operation.
    # TODO remove once resize is able to scale down native clusters
    broker = VcdBroker(tenant_auth_token, request_dict)
    return broker.delete_nodes()


def node_info(request_dict, tenant_auth_token):
    """Request handler for cluster operation.

    Required data: org_name, cluster_name, node_name.
    Optional data: ovdc_name.

    :return: Dict
    """
    required = [
        RequestKey.ORG_NAME,
        RequestKey.CLUSTER_NAME,
        RequestKey.NODE_NAME
    ]
    utils.ensure_keys_in_dict(required, request_dict, dict_name="request")

    # Currently node info is a vCD only operation.
    broker = VcdBroker(tenant_auth_token, request_dict)
    return broker.get_node_info(request_dict.get(RequestKey.CLUSTER_NAME),
                                request_dict.get(RequestKey.NODE_NAME))
