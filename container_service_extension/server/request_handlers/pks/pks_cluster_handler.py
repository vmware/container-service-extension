# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy

import pyvcloud.vcd.client as vcd_client

from container_service_extension.common.constants.server_constants import K8S_PROVIDER_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import K8sProvider  # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_CLUSTER_DOMAIN_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_PLANS_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import ThreadLocalData  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501
import container_service_extension.common.utils.ovdc_utils as ovdc_utils
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.exception.exceptions import ClusterAlreadyExistsError  # noqa: E501
from container_service_extension.exception.exceptions import ClusterNotFoundError  # noqa: E501
from container_service_extension.exception.exceptions import CseServerError
from container_service_extension.exception.exceptions import PksClusterNotFoundError  # noqa: E501
from container_service_extension.exception.exceptions import PksDuplicateClusterError  # noqa: E501
from container_service_extension.exception.exceptions import PksServerError
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import PayloadKey
import container_service_extension.lib.telemetry.telemetry_handler as telemetry_handler  # noqa: E501
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.security.context.operation_context as ctx
from container_service_extension.server.pks.pksbroker import PksBroker
import container_service_extension.server.pks.pksbroker_manager as pks_broker_manager  # noqa: E501
from container_service_extension.server.pks.pksbroker_manager import create_pks_context_for_all_accounts_in_org  # noqa: E501
import container_service_extension.server.request_handlers.request_utils as req_utils  # noqa: E501

DEFAULT_API_VERSION = vcd_client.ApiVersion.VERSION_33.value


@telemetry_handler.record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_LIST)  # noqa: E501
def cluster_list(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster list operation.

    All brokers in the org do 'list cluster' operation.
    Post-process the result returned by the broker.
    Aggregate all the results into a list.

    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: List
    """
    _raise_error_if_pks_not_enabled()

    data = req_utils.flatten_request_data(
        request_data, [RequestKey.QUERY_PARAMS])

    cse_params = copy.deepcopy(data)
    cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
    telemetry_handler.record_user_action_details(
        cse_operation=CseOperation.PKS_CLUSTER_LIST,
        cse_params=cse_params)

    pks_clusters_info = pks_broker_manager.list_clusters(data, op_ctx)
    common_cluster_properties = [
        'name',
        'vdc',
        'status',
        'org_name',
        'k8s_version',
        K8S_PROVIDER_KEY
    ]

    result = []
    for info in pks_clusters_info:
        filtered_cluster_info = \
            {k: info.get(k) for k in common_cluster_properties}
        result.append(filtered_cluster_info)

    return result


@telemetry_handler.record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_INFO)  # noqa: E501
def cluster_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster info operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()

    data = req_utils.flatten_request_data(
        request_data, [RequestKey.QUERY_PARAMS])

    cluster, _ = _get_cluster_info(data, op_ctx)  # noqa: E501
    telemetry_handler.record_user_action_details(
        cse_operation=CseOperation.PKS_CLUSTER_INFO,
        cse_params=_get_telemetry_data(data, cluster))
    return cluster


@telemetry_handler.record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_CONFIG)  # noqa: E501
def cluster_config(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster config operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    cluster, broker = _get_cluster_info(request_data, op_ctx, telemetry=False)  # noqa: E501
    telemetry_handler.record_user_action_details(
        cse_operation=CseOperation.PKS_CLUSTER_CONFIG,
        cse_params=_get_telemetry_data(request_data, cluster))
    return broker.get_cluster_config(data=request_data)


@telemetry_handler.record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_CREATE)  # noqa: E501
def cluster_create(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster create operation.

    Required data: org_name, ovdc_name, cluster_name

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()

    data = req_utils.flatten_request_data(
        request_data, [RequestKey.INPUT_SPEC])

    required = [
        RequestKey.CLUSTER_NAME
    ]
    req_utils.validate_payload(data, required)

    cluster_name = data[RequestKey.CLUSTER_NAME]
    data['is_org_admin_search'] = True

    try:
        _get_cluster_and_broker(data, op_ctx, telemetry=False)
        raise ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                        f"already exists.")
    except ClusterNotFoundError:
        pass

    sysadmin_client_v33 = op_ctx.get_sysadmin_client(
        api_version=DEFAULT_API_VERSION)
    k8s_metadata = \
        ovdc_utils.get_ovdc_k8s_provider_metadata(
            sysadmin_client_v33,
            org_name=data[RequestKey.ORG_NAME],
            ovdc_name=data[RequestKey.OVDC_NAME],
            include_credentials=True,
            include_nsxt_info=True)
    broker = _get_broker_from_k8s_metadata(k8s_metadata, op_ctx)
    data[RequestKey.PKS_PLAN_NAME] = k8s_metadata[PKS_PLANS_KEY][0]
    data[RequestKey.PKS_EXT_HOST] = \
        f"{cluster_name}.{k8s_metadata[PKS_CLUSTER_DOMAIN_KEY]}"
    cluster = broker.create_cluster(data=data)
    # Record telemetry data
    telemetry_handler.record_user_action_details(
        cse_operation=CseOperation.PKS_CLUSTER_CREATE,
        cse_params=_get_telemetry_data(data, cluster))
    return cluster


@telemetry_handler.record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_DELETE)  # noqa: E501
def cluster_delete(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster delete operation.

    Required data: cluster_name
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()
    cluster, broker = _get_cluster_info(request_data, op_ctx, telemetry=False)  # noqa: E501
    # Record telemetry data
    telemetry_handler.record_user_action_details(
        cse_operation=CseOperation.PKS_CLUSTER_DELETE,
        cse_params=_get_telemetry_data(request_data, cluster))
    return broker.delete_cluster(data=request_data)


@telemetry_handler.record_user_action_telemetry(cse_operation=CseOperation.PKS_CLUSTER_RESIZE)  # noqa: E501
def cluster_resize(request_data, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    Required data: cluster_name, num_nodes
    Optional data and default values: org_name=None, ovdc_name=None

    (data validation handled in broker)

    :return: Dict
    """
    _raise_error_if_pks_not_enabled()

    data = req_utils.flatten_request_data(
        request_data, [RequestKey.INPUT_SPEC])

    cluster, broker = _get_cluster_info(data, op_ctx, telemetry=False)  # noqa: E501
    # Record telemetry data
    telemetry_handler.record_user_action_details(
        cse_operation=CseOperation.PKS_CLUSTER_RESIZE,
        cse_params=_get_telemetry_data(data, cluster))
    return broker.resize_cluster(data=data)


def _get_cluster_info(request_data, op_ctx, **kwargs):
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
        sysadmin_client_v33 = op_ctx.get_sysadmin_client(
            api_version=DEFAULT_API_VERSION)
        k8s_metadata = \
            ovdc_utils.get_ovdc_k8s_provider_metadata(
                sysadmin_client_v33,
                org_name=org_name,
                ovdc_name=ovdc_name,
                include_credentials=True,
                include_nsxt_info=True)
        broker = _get_broker_from_k8s_metadata(
            k8s_metadata, op_ctx)
        return broker.get_cluster_info(data=request_data, **kwargs), broker

    return _get_cluster_and_broker(request_data, op_ctx, **kwargs)


def _get_cluster_and_broker(request_data, op_ctx, **kwargs):
    cluster_name = request_data[RequestKey.CLUSTER_NAME]

    pks_ctx_list = create_pks_context_for_all_accounts_in_org(op_ctx)
    for pks_ctx in pks_ctx_list:
        debug_msg = f"Get cluster info for cluster '{cluster_name}' " \
            f"failed on host '{pks_ctx['host']}' with error: "
        pks_broker = PksBroker(pks_ctx, op_ctx)
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
                                  op_ctx: ctx.OperationContext):
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
    return PksBroker(k8s_metadata, op_ctx)


def _raise_error_if_pks_not_enabled():
    if not server_utils.is_pks_enabled():
        raise CseServerError('CSE is not configured to work with PKS.')


def _get_telemetry_data(request_data, cluster_data):
    """Construct telemetry data.

    :param dict request_data: data from user
    :param dict cluster_data: cluster information
    :return: telemetry data
    :rtype: dict
    """
    cse_params = copy.deepcopy(request_data)
    cse_params[PayloadKey.K8S_VERSION] = cluster_data.get(PayloadKey.K8S_VERSION)  # noqa: E501
    cse_params[PayloadKey.PKS_CLUSTER_ID] = cluster_data.get(PayloadKey.PKS_CLUSTER_ID)  # noqa: E501
    cse_params[PayloadKey.PKS_VERSION] = cluster_data.get(PayloadKey.PKS_VERSION)  # noqa: E501
    cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
    return cse_params
