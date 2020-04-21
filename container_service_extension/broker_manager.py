# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.exceptions as e
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pksbroker as pksbroker
import container_service_extension.pksbroker_manager as pksbroker_manager
import container_service_extension.request_context as ctx
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils
import container_service_extension.vcdbroker as vcdbroker

"""Handles retrieving the correct broker/cluster to use during an operation."""


def get_cluster_info(request_data, request_context: ctx.RequestContext):
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
        k8s_metadata = ovdc_utils.get_ovdc_k8s_provider_metadata(
            request_context.sysadmin_client,
            org_name=org_name,
            ovdc_name=ovdc_name,
            include_credentials=True,
            include_nsxt_info=True)
        broker = get_broker_from_k8s_metadata(k8s_metadata, request_context)
        return broker.get_cluster_info(request_data), broker

    return get_cluster_and_broker(request_data, request_context)


def get_cluster_and_broker(request_data, request_context: ctx.RequestContext):
    """.

    :param request_data:
    :param request_context:
    :return:

    :raises CseDuplicateClusterError: if multiple clusters share the same name
        across orgs and sys admin tries to do a cluster operation.
    :raises PksDuplicateClusterError: if multiple pks clusters share the
        same name.
    """
    cluster_name = request_data[RequestKey.CLUSTER_NAME]
    vcd_broker = vcdbroker.VcdBroker(request_context)
    try:
        return vcd_broker.get_cluster_info(request_data), vcd_broker
    except e.ClusterNotFoundError:
        # continue searching using PksBrokers
        pass
    except e.CseDuplicateClusterError as err:
        # fail because multiple clusters with same name exist
        # only case is when multiple same-name clusters exist across orgs
        # and sys admin tries to do a cluster operation
        LOGGER.debug(f"Error: Found multiple native clusters named "
                     f"'{cluster_name}' ({err})")
        raise
    except Exception as err:
        LOGGER.error(f"Unknown error occured getting info for native cluster "
                     f"'{cluster_name}' ({err})", exc_info=True)
        raise

    pks_contexts = pksbroker_manager.create_pks_context_for_all_accounts_in_org(request_context) # noqa: E501
    for pks_context in pks_contexts:
        pks_broker = pksbroker.PksBroker(pks_context, request_context)
        try:
            return pks_broker.get_cluster_info(request_data), pks_broker
        except (e.PksClusterNotFoundError, e.PksServerError):
            # continue searching using other PksBrokers
            pass
        except e.PksDuplicateClusterError as err:
            # fail because multiple clusters with same name exist
            LOGGER.debug(f"Error: Found multiple PKS clusters named "
                         f"'{cluster_name}' ({err})")
            raise
        except Exception as err:
            LOGGER.error(f"Unknown error occured getting info for PKS cluster "
                         f"'{cluster_name}' ({err})", exc_info=True)
            raise

    raise e.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")


def get_broker_from_k8s_metadata(k8s_metadata,
                                 request_context: ctx.RequestContext):
    """Get broker from ovdc k8s metadata.

    If PKS is not enabled, always return VcdBroker
    If PKS is enabled
        if no ovdc metadata exists or k8s provider is None, raise server error
        else return the broker according to ovdc k8s provider
    """
    if utils.is_pks_enabled():
        if not k8s_metadata or k8s_metadata.get(K8S_PROVIDER_KEY) == K8sProvider.NONE: # noqa: E501
            raise e.CseServerError("Org VDC is not enabled for Kubernetes "
                                   "cluster deployment")

        if k8s_metadata.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
            return pksbroker.PksBroker(k8s_metadata, request_context)

    return vcdbroker.VcdBroker(request_context)
