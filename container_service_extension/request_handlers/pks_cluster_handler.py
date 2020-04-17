# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksClusterNotFoundError
from container_service_extension.exceptions import PksDuplicateClusterError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.ovdc_utils as ovdc_utils
from container_service_extension.pksbroker import PksBroker
import container_service_extension.pksbroker_manager as pks_broker_manager
from container_service_extension.pksbroker_manager import create_pks_context_for_all_accounts_in_org  # noqa: E501
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.server_constants import PKS_PLANS_KEY
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_telemetry
import container_service_extension.utils as utils


@record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_LIST)
def cluster_list(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for cluster list operation.

    All brokers in the org do 'list cluster' operation.
    Post-process the result returned by the broker.
    Aggregate all the results into a list.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: List
    """
    _raise_error_if_pks_not_enabled()

    pks_clusters_info = pks_broker_manager.list_clusters(request_data,
                                                         tenant_auth_token,
                                                         is_jwt_token)
    common_cluster_properties = [
        'name',
        'vdc',
        'status',
        'org_name',
        'k8s_version',
        K8S_PROVIDER_KEY
    ]

    result = []
    for cluster_info in pks_clusters_info:
        filtered_cluster_info = \
            {k: cluster_info.get(k) for k in common_cluster_properties}
        result.append(filtered_cluster_info)

    return result


@record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_INFO)
def cluster_info(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    cluster, _ = _get_cluster_info(request_data, tenant_auth_token, is_jwt_token)  # noqa: E501
    return cluster


@record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_CONFIG)
def cluster_config(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    _, broker = _get_cluster_info(request_data, tenant_auth_token, is_jwt_token, telemetry=False)  # noqa: E501
    return broker.get_cluster_config(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_CREATE)
def cluster_create(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for cluster create operation.

    Required data: org_name, ovdc_name, cluster_name

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    required = [
        RequestKey.CLUSTER_NAME
    ]
    req_utils.validate_payload(request_data, required)

    cluster_name = request_data[RequestKey.CLUSTER_NAME]
    request_data['is_org_admin_search'] = True

    try:
        _get_cluster_and_broker(request_data, tenant_auth_token, is_jwt_token, telemetry=False)  # noqa: E501
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
    broker = _get_broker_from_k8s_metadata(k8s_metadata, tenant_auth_token, is_jwt_token)  # noqa: E501
    request_data[RequestKey.PKS_PLAN_NAME] = k8s_metadata[PKS_PLANS_KEY][0]
    request_data[RequestKey.PKS_EXT_HOST] = \
        f"{cluster_name}.{k8s_metadata[PKS_CLUSTER_DOMAIN_KEY]}"
    return broker.create_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_DELETE)
def cluster_delete(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    _, broker = _get_cluster_info(request_data, tenant_auth_token, is_jwt_token, telemetry=False)  # noqa: E501
    return broker.delete_cluster(data=request_data)


@record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_RESIZE)
def cluster_resize(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    _, broker = _get_cluster_info(request_data, tenant_auth_token, is_jwt_token, telemetry=False)  # noqa: E501
    return broker.resize_cluster(data=request_data)


def _get_cluster_info(request_data, tenant_auth_token, is_jwt_token, **kwargs):
    """Get cluster details directly from cloud provider.

    Logic of the method is as follows.

    If 'ovdc' is present in the cluster spec,
        choose the right PKS broker to do get_cluster operation.
    else
        Invoke set of all PKS brokers in the org to find the cluster

    :return: a tuple of cluster information as dictionary and the broker
        instance used to find the cluster information.

    :rtype: tuple
    """
    required = [
        RequestKey.CLUSTER_NAME
    ]
    req_utils.validate_payload(request_data, required)

    org_name = request_data.get(RequestKey.ORG_NAME)
    ovdc_name = request_data.get(RequestKey.OVDC_NAME)

    if ovdc_name is not None and org_name is not None:
        k8s_metadata = \
            ovdc_utils.get_ovdc_k8s_provider_metadata(org_name=org_name,
                                                      ovdc_name=ovdc_name,
                                                      include_credentials=True,
                                                      include_nsxt_info=True)
        broker = _get_broker_from_k8s_metadata(
            k8s_metadata, tenant_auth_token, is_jwt_token)
        return broker.get_cluster_info(data=request_data, **kwargs), broker

    return _get_cluster_and_broker(
        request_data, tenant_auth_token, is_jwt_token, **kwargs)


def _get_cluster_and_broker(request_data, tenant_auth_token,
                            is_jwt_token, **kwargs):
    cluster_name = request_data[RequestKey.CLUSTER_NAME]

    pks_ctx_list = create_pks_context_for_all_accounts_in_org(
        tenant_auth_token, is_jwt_token)
    for pks_ctx in pks_ctx_list:
        debug_msg = f"Get cluster info for cluster '{cluster_name}' " \
            f"failed on host '{pks_ctx['host']}' with error: "
        pks_broker = PksBroker(pks_ctx, tenant_auth_token, is_jwt_token)
        try:
            return pks_broker.get_cluster_info(data=request_data, **kwargs), pks_broker  # noqa: E501
        except (PksClusterNotFoundError, PksServerError) as err:
            # continue searching using other PksBrokers
            LOGGER.debug(f"{debug_msg}{err}")
        except PksDuplicateClusterError as err:
            # fail because multiple clusters with same name exist
            LOGGER.debug(f"{debug_msg}{err}")
            raise
        except Exception as err:
            LOGGER.error(f"Unknown error: {err}", exc_info=True)
            raise

    # raised if cluster was not found in PksBrokers
    raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")


def _get_broker_from_k8s_metadata(k8s_metadata,
                                  tenant_auth_token,
                                  is_jwt_token):
    """Get broker from ovdc k8s metadata.

    If PKS is not enabled, raise CseServerError
    If PKS is enabled
        if no ovdc metadata exists or k8s provider is None, raise server error
        else return the broker according to ovdc k8s provider
    """
    _raise_error_if_pks_not_enabled()
    if not k8s_metadata or k8s_metadata.get(K8S_PROVIDER_KEY) != K8sProvider.PKS:  # noqa: E501
        raise CseServerError("Org VDC is not enabled for Kubernetes "
                             "cluster deployment")
    return PksBroker(k8s_metadata, tenant_auth_token, is_jwt_token)


def _raise_error_if_pks_not_enabled():
    if not utils.is_pks_enabled():
        raise CseServerError('CSE is not configured to work with PKS.')
