# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseServerError
import container_service_extension.ovdc_utils as ovdc_utils
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pksbroker_manager import PksBrokerManager
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.server_constants import PKS_PLANS_KEY
from container_service_extension.shared_constants import RequestKey
from container_service_extension.utils import get_pks_cache
from container_service_extension.utils import is_pks_enabled
from container_service_extension.vcdbroker import VcdBroker
from container_service_extension.vcdbroker_manager import VcdBrokerManager


# TODO(Constants)
#  As part of refactoring, avoid accessing HTTP request body directly
#  from VcdBroker and PksBroker. We should try to limit processing request to
#  request_processor.py and broker_manager.py.


class BrokerManager:
    """Manage calls to vCD and PKS brokers.

    Handles:
    Pre-processing of requests to brokers
    Post-processing of results from brokers.
    """

    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec
        self.pks_cache = get_pks_cache()
        self.vcdbroker_manager = VcdBrokerManager(tenant_auth_token, request_spec) # noqa: E501
        self.pksbroker_manager = PksBrokerManager(tenant_auth_token, request_spec) # noqa: E501
        self.is_ovdc_present_in_request = bool(request_spec.get(RequestKey.OVDC_NAME)) # noqa: E501

    def _get_cluster_config(self):
        _, broker = self._get_cluster_info()
        return broker.get_cluster_config()

    def _create_cluster(self):
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]
        # 'is_org_admin_search' is used here to prevent cluster creation with
        # same cluster-name by users within org, which might span over to PKS.
        # If it is true, cluster list is filtered by the org name of the
        # logged-in user to check for duplicates.
        cluster, _ = self._find_cluster_in_org(is_org_admin_search=True)
        if cluster:
            raise ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                            f"already exists.")

        ctr_prov_ctx = ovdc_utils.get_ovdc_k8s_provider_metadata(org_name=self.req_spec[RequestKey.ORG_NAME], ovdc_name=self.req_spec[RequestKey.OVDC_NAME], include_credentials=True, include_nsxt_info=True) # noqa: E501
        if ctr_prov_ctx.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
            self.req_spec[RequestKey.PKS_PLAN_NAME] = ctr_prov_ctx[PKS_PLANS_KEY][0] # noqa: E501
            self.req_spec['pks_ext_host'] = f"{cluster_name}.{ctr_prov_ctx[PKS_CLUSTER_DOMAIN_KEY]}" # noqa: E501
        broker = self._get_broker_based_on_ctr_prov_ctx(ctr_prov_ctx)
        return broker.create_cluster()

    def _delete_cluster(self):
        _, broker = self._get_cluster_info()
        return broker.delete_cluster()

    def _get_cluster_info(self):
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
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]
        if self.is_ovdc_present_in_request:
            broker = self._get_broker_based_on_vdc()
            return broker.get_cluster_info(), broker
        else:
            cluster, broker = self._find_cluster_in_org()
            if cluster:
                return cluster, broker

        raise ClusterNotFoundError(f"Cluster {cluster_name} not found "
                                   f"either in vCD or PKS")

    def _list_clusters(self):
        """Logic of the method is as follows.

        If 'ovdc' is present in the body,
            choose the right broker (by identifying the k8s provider
            (vcd|pks) defined for that ovdc) to do list_clusters operation.
        Else
            Invoke set of all (vCD/PKS)brokers in the org to do list_clusters.
            Post-process the result returned by each broker.
            Aggregate all the results into one.
        """
        vcd_clusters_info = \
            self.vcdbroker_manager.list_clusters()
        pks_clusters_info = []
        if is_pks_enabled():
            pks_clusters_info = \
                self.pksbroker_manager.list_clusters()
        all_cluster_infos = vcd_clusters_info + pks_clusters_info

        common_cluster_properties = \
            ('name', 'vdc', 'status', 'org_name', K8S_PROVIDER_KEY)
        result = []
        for cluster_info in all_cluster_infos:
            filtered_cluster_info = {
                k: cluster_info.get(k) for k in common_cluster_properties}
            result.append(filtered_cluster_info)

        return result

    def _resize_cluster(self):
        cluster, broker = self._get_cluster_info()
        return broker.resize_cluster(curr_cluster_info=cluster)

    def _find_cluster_in_org(self, is_org_admin_search=False):
        cluster, broker = self.vcdbroker_manager.find_cluster_in_org()

        if not cluster and is_pks_enabled():
            cluster, broker = self.pksbroker_manager.find_cluster_in_org(is_org_admin_search=is_org_admin_search) # noqa: E501

        return cluster, broker

    def _get_broker_based_on_ctr_prov_ctx(self, ctr_prov_ctx):
        # If system is equipped with PKS, use the metadata on ovdc to determine
        # the correct broker, otherwise fallback to vCD for cluster deployment.
        # However if the system is enabled for PKS and has no metadata on odvc
        # or isn't enabled for container deployment raise appropriate
        # exception.
        if is_pks_enabled():
            if ctr_prov_ctx:
                if ctr_prov_ctx.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
                    return PKSBroker(self.tenant_auth_token, self.req_spec,
                                     pks_ctx=ctr_prov_ctx)
                elif ctr_prov_ctx.get(K8S_PROVIDER_KEY) == K8sProvider.NATIVE:
                    return VcdBroker(self.tenant_auth_token, self.req_spec)

        else:
            return VcdBroker(self.tenant_auth_token, self.req_spec)

        raise CseServerError("Org VDC is not enabled for Kubernetes cluster "
                             "deployment")

    def _get_broker_based_on_vdc(self):
        """Get the broker based on org VDC.

        :return: broker

        :rtype: container_service_extension.abstract_broker.AbstractBroker
        """
        ovdc_name = self.req_spec.get(RequestKey.OVDC_NAME)
        org_name = self.req_spec.get(RequestKey.ORG_NAME)

        ctr_prov_ctx = ovdc_utils.get_ovdc_k8s_provider_metadata(org_name=org_name, ovdc_name=ovdc_name, include_credentials=True, include_nsxt_info=True) # noqa: E501

        return self._get_broker_based_on_ctr_prov_ctx(ctr_prov_ctx)
