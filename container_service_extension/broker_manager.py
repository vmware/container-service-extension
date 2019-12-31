# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseDuplicateClusterError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksClusterNotFoundError
from container_service_extension.exceptions import PksDuplicateClusterError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.ovdc_utils as ovdc_utils
from container_service_extension.pksbroker import PksBroker
from container_service_extension.pksbroker_manager import create_pks_context_for_all_accounts_in_org # noqa: E501
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils
from container_service_extension.vcdbroker import VcdBroker


"""Handles retrieving the correct broker/cluster to use during an operation."""


def get_cluster_info(request_data, tenant_auth_token, is_jwt_token):
    """Get cluster details directly from cloud provider.

    Logic of the method is as follows.

    If 'ovdc' is present in the cluster spec,
        choose the right broker (by identifying the k8s provider
        (vcd|pks) defined for that ovdc) to do get_cluster operation.
    else
        Invoke set of all (vCD/PKS) brokers in the org to find the cluster

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
        broker = get_broker_from_k8s_metadata(
            k8s_metadata, tenant_auth_token, is_jwt_token)
        return broker.get_cluster_info(request_data), broker

    return get_cluster_and_broker(
        request_data, tenant_auth_token, is_jwt_token)


def get_cluster_and_broker(request_data, tenant_auth_token, is_jwt_token):
    cluster_name = request_data[RequestKey.CLUSTER_NAME]
    vcd_broker = VcdBroker(tenant_auth_token, is_jwt_token)
    try:
        return vcd_broker.get_cluster_info(request_data), vcd_broker
    except ClusterNotFoundError as err:
        # continue searching using PksBrokers
        LOGGER.debug(f"{err}")
    except CseDuplicateClusterError as err:
        # fail because multiple clusters with same name exist
        # only case is when multiple same-name clusters exist across orgs
        # and sys admin tries to do a cluster operation
        LOGGER.debug(f"{err}")
        raise
    except Exception as err:
        LOGGER.error(f"Unknown error: {err}", exc_info=True)
        raise

    pks_ctx_list = create_pks_context_for_all_accounts_in_org(
        tenant_auth_token, is_jwt_token)
    for pks_ctx in pks_ctx_list:
        debug_msg = f"Get cluster info for cluster '{cluster_name}' " \
                    f"failed on host '{pks_ctx['host']}' with error: "
        pks_broker = PksBroker(pks_ctx, tenant_auth_token, is_jwt_token)
        try:
            return pks_broker.get_cluster_info(request_data), pks_broker
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

    # only raised if cluster was not found in VcdBroker or PksBrokers
    raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")


def get_broker_from_k8s_metadata(k8s_metadata,
                                 tenant_auth_token,
                                 is_jwt_token):
    """Get broker from ovdc k8s metadata.

    If PKS is not enabled, always return VcdBroker
    If PKS is enabled
        if no ovdc metadata exists or k8s provider is None, raise server error
        else return the broker according to ovdc k8s provider
    """
    if utils.is_pks_enabled():
        if not k8s_metadata or k8s_metadata.get(K8S_PROVIDER_KEY) == K8sProvider.NONE: # noqa: E501
            raise CseServerError("Org VDC is not enabled for Kubernetes "
                                 "cluster deployment")

        if k8s_metadata.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
            return PksBroker(k8s_metadata, tenant_auth_token, is_jwt_token)

    return VcdBroker(tenant_auth_token, is_jwt_token)
