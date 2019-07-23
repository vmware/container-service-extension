# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseServerError
import container_service_extension.ovdc_utils as ovdc_utils
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pksbroker_manager import PksBrokerManager
from container_service_extension.server_constants import CseOperation
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
#  1. Scan and classify all broker-related constants in server code into
#  either common, vcd_broker_specific, pks_broker_specific constants.
#  Design and refactor them into one or more relevant files.
#  2. Scan through both CSE client and server to identify HTTP request/response
#  body params and define all of them as constants into a file
#  from where both client and server can access them.
#  3. Refactor both client and server code accordingly
#  4. As part of refactoring, avoid accessing HTTP request body directly
#  from VcdBroker and PksBroker. We should try to limit processing request to
#  processor.py and broker_manager.py.


class BrokerManager(object):
    """Manage calls to vCD and PKS brokers.

    Handles:
    Pre-processing of requests to brokers
    Post-processing of results from brokers.
    """

    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec
        self.pks_cache = get_pks_cache()
        self.vcdbroker_manager = VcdBrokerManager(
            tenant_auth_token, request_spec)
        self.pksbroker_manager = PksBrokerManager(
            tenant_auth_token, request_spec)
        self.is_ovdc_present_in_request = False

    def invoke(self, op):
        """Invoke right broker(s) to perform the operation requested.

        Might result in further (pre/post)processing on the request/result(s).


        Depending on the operation requested, this method may do one or more
        of below mentioned points.
        1. Extract and construct the relevant params for the operation.
        2. Choose right broker to perform the operation/method requested.
        3. Scan through available brokers to aggregate (or) filter results.

        :param CseOperation op: Operation to be performed by one of the
            brokers.

        :return result: result of the operation.

        :rtype: dict
        """
        result = {}
        self.is_ovdc_present_in_request = bool(self.req_spec.get(RequestKey.OVDC_NAME)) # noqa: E501

        if op == CseOperation.CLUSTER_CONFIG:
            cluster_spec = \
                {'cluster_name': self.req_spec.get(RequestKey.CLUSTER_NAME)}
            result = self._get_cluster_config(**cluster_spec)
        elif op == CseOperation.CLUSTER_CREATE:
            # TODO(ClusterSpec) Create an inner class "ClusterSpec"
            #  in abstract_broker.py and have subclasses define and use it
            #  as instance variable.
            #  Method 'Create_cluster' in VcdBroker and PksBroker should take
            #  ClusterSpec either as a param (or)
            #  read from instance variable (if needed only).
            cluster_spec = {
                'cluster_name': self.req_spec.get(RequestKey.CLUSTER_NAME),
                'vdc_name': self.req_spec.get(RequestKey.OVDC_NAME),
                'org_name': self.req_spec.get(RequestKey.ORG_NAME),
                'node_count': self.req_spec.get(RequestKey.NUM_WORKERS),
                'storage_profile': self.req_spec.get(RequestKey.STORAGE_PROFILE_NAME), # noqa: E501
                'network_name': self.req_spec.get(RequestKey.NETWORK_NAME),
                'template': self.req_spec.get(RequestKey.TEMPLATE_NAME),
            }
            result = self._create_cluster(**cluster_spec)
        elif op == CseOperation.CLUSTER_DELETE:
            cluster_spec = \
                {'cluster_name': self.req_spec.get(RequestKey.CLUSTER_NAME)}
            result = self._delete_cluster(**cluster_spec)
        elif op == CseOperation.CLUSTER_INFO:
            cluster_spec = \
                {'cluster_name': self.req_spec.get(RequestKey.CLUSTER_NAME)}
            result = self._get_cluster_info(**cluster_spec)[0]
        elif op == CseOperation.CLUSTER_LIST:
            result = self._list_clusters()
        elif op == CseOperation.CLUSTER_RESIZE:
            cluster_spec = {
                'cluster_name': self.req_spec.get(RequestKey.CLUSTER_NAME),
                'node_count': self.req_spec.get(RequestKey.NUM_WORKERS)
            }
            result = self._resize_cluster(**cluster_spec)
        elif op == CseOperation.NODE_CREATE:
            # Currently node create is a vCD only operation.
            broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            result = broker.create_nodes()
        elif op == CseOperation.NODE_DELETE:
            # Currently node delete is a vCD only operation.
            broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            result = broker.delete_nodes()
        elif op == CseOperation.NODE_INFO:
            cluster_name = self.req_spec.get(RequestKey.CLUSTER_NAME)
            node_name = self.req_spec.get(RequestKey.NODE_NAME)
            # Currently node info is a vCD only operation.
            broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            result = broker.get_node_info(cluster_name, node_name)

        return result

    def _get_cluster_config(self, **cluster_spec):
        """Get the cluster configuration.

        :param str cluster_name: Name of cluster.

        :return: Cluster config.

        :rtype: str
        """
        cluster, broker = self._get_cluster_info(**cluster_spec)
        return broker.get_cluster_config(cluster_name=cluster['name'])

    def _create_cluster(self, **cluster_spec):
        cluster_name = cluster_spec['cluster_name']
        vdc_name = cluster_spec.get('vdc_name')
        org_name = cluster_spec.get('org_name')
        # 'is_org_admin_search' is used here to prevent cluster creation with
        # same cluster-name by users within org, which might span over to PKS.
        # If it is true, cluster list is filtered by the org name of the
        # logged-in user to check for duplicates.
        cluster, _ = self._find_cluster_in_org(cluster_name,
                                               is_org_admin_search=True)
        if cluster:
            raise ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                            f"already exists.")

        ctr_prov_ctx = ovdc_utils.get_ovdc_k8s_provider_metadata(org_name=org_name, ovdc_name=vdc_name, get_credentials=True, get_nsxt_info=True) # noqa: E501
        if ctr_prov_ctx.get(K8S_PROVIDER_KEY) == K8sProvider.PKS:
            cluster_spec['pks_plan'] = ctr_prov_ctx[PKS_PLANS_KEY][0]
            cluster_spec['pks_ext_host'] = f"{cluster_name}.{ctr_prov_ctx[PKS_CLUSTER_DOMAIN_KEY]}" # noqa: E501
        broker = self._get_broker_based_on_ctr_prov_ctx(ctr_prov_ctx)
        return broker.create_cluster(**cluster_spec)

    def _delete_cluster(self, **cluster_spec):
        cluster, broker = self._get_cluster_info(**cluster_spec)
        return broker.delete_cluster(cluster_name=cluster['name'])

    def _get_cluster_info(self, **cluster_spec):
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
        cluster_name = cluster_spec['cluster_name']
        if self.is_ovdc_present_in_request:
            broker = self._get_broker_based_on_vdc()
            return broker.get_cluster_info(cluster_name=cluster_name), broker
        else:
            cluster, broker = self._find_cluster_in_org(cluster_name)
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

    def _resize_cluster(self, **cluster_spec):
        cluster, broker = self._get_cluster_info(**cluster_spec)
        return broker.resize_cluster(curr_cluster_info=cluster, **cluster_spec)

    def _find_cluster_in_org(self, cluster_name, is_org_admin_search=False):
        cluster, broker = self.vcdbroker_manager.find_cluster_in_org(
            cluster_name, is_org_admin_search)
        if not cluster and is_pks_enabled():
            cluster, broker = self.pksbroker_manager.find_cluster_in_org(
                cluster_name, is_org_admin_search)

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

        ctr_prov_ctx = ovdc_utils.get_ovdc_k8s_provider_metadata(org_name=org_name, ovdc_name=ovdc_name, get_credentials=True, get_nsxt_info=True) # noqa: E501

        return self._get_broker_based_on_ctr_prov_ctx(ctr_prov_ctx)
