# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.org import Org
import requests

from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseDuplicateClusterError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksDuplicateClusterError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pks_cache import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.pks_cache import PKS_PLANS_KEY
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.server_constants import CseOperation
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProviders
from container_service_extension.utils import connect_vcd_user_via_token
from container_service_extension.utils import exception_handler
from container_service_extension.utils import get_pks_cache
from container_service_extension.vcdbroker import VcdBroker


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
        self.ovdc_cache = OvdcCache()
        self.is_ovdc_present_in_request = False
        self.vcd_client, self.session = connect_vcd_user_via_token(
            tenant_auth_token=tenant_auth_token)

    @exception_handler
    def invoke(self, op):
        """Invoke right broker(s) to perform the operation requested.

        Might result in further (pre/post)processing on the request/result(s).


        Depending on the operation requested, this method may do one or more
        of below mentioned points.
        1. Extract and construct the relevant params for the operation.
        2. Choose right broker to perform the operation/method requested.
        3. Scan through available brokers to aggregate (or) filter results.
        4. Construct and return the HTTP response

        :param CseOperation op: Operation to be performed by one of the
            brokers.

        :return result: result of the operation.

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = requests.codes.ok
        self.is_ovdc_present_in_request = self.req_spec.get('vdc')

        if op == CseOperation.CLUSTER_CONFIG:
            cluster_spec = \
                {'cluster_name': self.req_spec.get('cluster_name', None)}
            result['body'] = \
                self._get_cluster_config(**cluster_spec)
        elif op == CseOperation.CLUSTER_CREATE:
            # TODO(ClusterSpec) Create an inner class "ClusterSpec"
            #  in abstract_broker.py and have subclasses define and use it
            #  as instance variable.
            #  Method 'Create_cluster' in VcdBroker and PksBroker should take
            #  ClusterSpec either as a param (or)
            #  read from instance variable (if needed only).
            cluster_spec = {
                'cluster_name': self.req_spec.get('cluster_name', None),
                'vdc_name': self.req_spec.get('vdc', None),
                'node_count': self.req_spec.get('node_count', None),
                'storage_profile': self.req_spec.get('storage_profile', None),
                'network_name': self.req_spec.get('network', None),
                'template': self.req_spec.get('template', None),
            }
            result['body'] = self._create_cluster(**cluster_spec)
            result['status_code'] = requests.codes.accepted
        elif op == CseOperation.CLUSTER_DELETE:
            cluster_spec = \
                {'cluster_name': self.req_spec.get('cluster_name', None)}
            result['body'] = self._delete_cluster(**cluster_spec)
            result['status_code'] = requests.codes.accepted
        elif op == CseOperation.CLUSTER_INFO:
            cluster_spec = \
                {'cluster_name': self.req_spec.get('cluster_name', None)}
            result['body'] = self._get_cluster_info(**cluster_spec)[0]
        elif op == CseOperation.CLUSTER_LIST:
            result['body'] = self._list_clusters()
        elif op == CseOperation.CLUSTER_RESIZE:
            # TODO(resize_cluster) Once VcdBroker.create_nodes() is hooked to
            #  broker_manager, ensure broker.resize_cluster returns only
            #  response body. Construct the remainder of the response here.
            #  This cannot be done at the moment as @exception_handler cannot
            #  be removed on create_nodes() as of today (Mar 15, 2019).
            cluster_spec = \
                {'cluster_name': self.req_spec.get('cluster_name', None),
                 'node_count': self.req_spec.get('node_count', None)
                 }
            result['body'] = self._resize_cluster(**cluster_spec)
            result['status_code'] = requests.codes.accepted
        elif op == CseOperation.NODE_CREATE:
            # Currently node create is a vCD only operation.
            broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            result['body'] = broker.create_nodes()
            result['status_code'] = requests.codes.accepted
        elif op == CseOperation.NODE_DELETE:
            # Currently node delete is a vCD only operation.
            broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            result['body'] = broker.delete_nodes()
            result['status_code'] = requests.codes.accepted
        elif op == CseOperation.NODE_INFO:
            node_spec = \
                {'cluster_name': self.req_spec.get('cluster_name'),
                 'node_name': self.req_spec.get('node_name')}
            result['body'] = self._get_node_info(**node_spec)[0]

        return result

    def _get_cluster_config(self, **cluster_spec):
        """Get the cluster configuration.

        :param str cluster_name: Name of cluster.

        :return: Cluster config.

        :rtype: str
        """
        cluster_name = cluster_spec['cluster_name']
        if self.is_ovdc_present_in_request:
            broker = self.get_broker_based_on_vdc()
            return broker.get_cluster_config(cluster_name=cluster_name)
        else:
            cluster, broker = self._find_cluster_in_org(cluster_name)
            if cluster:
                return broker.get_cluster_config(cluster_name=cluster['name'])

        raise ClusterNotFoundError(f"Cluster {cluster_name} not found "
                                   f"either in vCD or PKS")

    def _create_cluster(self, **cluster_spec):
        cluster_name = cluster_spec['cluster_name']
        # 'is_org_admin_search' is used here to prevent cluster creation with
        # same cluster-name by users within org.
        # If it is true, cluster list is filtered by the org name of the
        # logged-in user to check for duplicates.
        cluster, _ = self._find_cluster_in_org(cluster_name,
                                               is_org_admin_search=True)
        if not cluster:
            ctr_prov_ctx = self._get_ctr_prov_ctx_from_ovdc_metadata()
            if ctr_prov_ctx.get(
                    K8S_PROVIDER_KEY) == K8sProviders.PKS:
                cluster_spec['pks_plan'] = ctr_prov_ctx[PKS_PLANS_KEY][0]
                cluster_spec['pks_ext_host'] = f"{cluster_name}." \
                    f"{ctr_prov_ctx[PKS_CLUSTER_DOMAIN_KEY]}"
            broker = self._get_broker_based_on_ctr_prov_ctx(ctr_prov_ctx)
            return broker.create_cluster(**cluster_spec)
        else:
            raise ClusterAlreadyExistsError(
                f"Cluster {cluster_name} already exists.")

    def _delete_cluster(self, **cluster_spec):
        cluster_name = cluster_spec['cluster_name']
        _, broker = self._get_cluster_info(**cluster_spec)
        return broker.delete_cluster(cluster_name=cluster_name)

    def _get_cluster_info(self, **cluster_spec):
        """Get cluster details directly from cloud provider.

        Logic of the method is as follows.

        If 'ovdc' is present in the cluster spec,
            choose the right broker (by identifying the container_provider
            (vcd|pks) defined for that ovdc) to do get_cluster operation.
        else
            Invoke set of all (vCD/PKS) brokers in the org to find the cluster

        :return: a tuple of cluster information as dictionary and the broker
            instance used to find the cluster information.

        :rtype: tuple
        """
        cluster_name = cluster_spec['cluster_name']
        if self.is_ovdc_present_in_request:
            broker = self.get_broker_based_on_vdc()
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
            choose the right broker (by identifying the container_provider
            (vcd|pks) defined for that ovdc) to do list_clusters operation.
        Else
            Invoke set of all (vCD/PKS)brokers in the org to do list_clusters.
            Post-process the result returned by each broker.
            Aggregate all the results into one.
        """
        if self.is_ovdc_present_in_request:
            broker = self.get_broker_based_on_vdc()
            return broker.list_clusters()
        else:
            common_cluster_properties = ('name', 'vdc', 'status', 'org_name')
            vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            vcd_clusters = []
            for cluster in vcd_broker.list_clusters():
                vcd_cluster = {k: cluster.get(k, None) for k in
                               common_cluster_properties}
                vcd_cluster[K8S_PROVIDER_KEY] = K8sProviders.NATIVE
                vcd_clusters.append(vcd_cluster)

            pks_clusters = []
            pks_ctx_list = self._create_pks_context_for_all_accounts_in_org()
            for pks_ctx in pks_ctx_list:
                pks_broker = PKSBroker(self.tenant_auth_token, self.req_spec,
                                       pks_ctx)
                # Get all cluster information to get vdc name from
                # compute-profile-name
                for cluster in pks_broker.list_clusters(is_admin_request=True):
                    pks_cluster = \
                        PKSBroker.generate_cluster_subset_with_given_keys(
                            cluster, common_cluster_properties)
                    pks_cluster[K8S_PROVIDER_KEY] = K8sProviders.PKS
                    pks_clusters.append(pks_cluster)
            return vcd_clusters + pks_clusters

    def _resize_cluster(self, **cluster_spec):
        cluster, broker = self._get_cluster_info(**cluster_spec)
        return broker.resize_cluster(curr_cluster_info=cluster, **cluster_spec)

    def _get_node_info(self, **node_spec):
        """Get node details directly from cloud provider.

        Logic of the method is as follows.

        If 'ovdc' is present in the cluster spec,
            choose the right broker (by identifying the container_provider
            (vcd|pks) defined for that ovdc) to do get_node operation.
        else
            Invoke set of all (vCD/PKS) brokers in the org to find the cluster
            and then do get_node operation

        :return: a tuple of node information as dictionary and the broker
            instance used to find the cluster information.

        :rtype: tuple
        """
        cluster_name = node_spec['cluster_name']
        node_name = node_spec['node_name']
        if self.is_ovdc_present_in_request:
            broker = self.get_broker_based_on_vdc()
            return broker.get_node_info(cluster_name, node_name), broker
        else:
            vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
            cluster = vcd_broker.get_cluster_info(cluster_name)
            if cluster:
                return vcd_broker.get_node_info(
                    cluster_name, node_name), vcd_broker

        raise ClusterNotFoundError(f"Cluster {cluster_name} with "
                                   f"Node {node_name} not found "
                                   f"either in vCD or PKS")

    def _find_cluster_in_org(self, cluster_name, is_org_admin_search=False):
        """Invoke set of all (vCD/PKS)brokers in the org to find the cluster.

        'is_org_admin_search' is used here to prevent cluster creation with
        same cluster-name by users within org. If it is true,
        cluster list is filtered by the org name of the logged-in user.

        If cluster found:
            Return a tuple of (cluster and the broker instance used to find
            the cluster)
        Else:
            (None, None) if cluster not found.
        """
        vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
        try:
            return vcd_broker.get_cluster_info(cluster_name), vcd_broker
        except CseDuplicateClusterError as err:
            LOGGER.debug(f"Get cluster info on {cluster_name}"
                         f"on vCD failed with error: {err}")
            raise err
        except Exception as err:
            LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                         f"on vCD with error: {err}")

        pks_ctx_list = self._create_pks_context_for_all_accounts_in_org()
        for pks_ctx in pks_ctx_list:
            pksbroker = PKSBroker(self.tenant_auth_token, self.req_spec,
                                  pks_ctx)
            try:
                return pksbroker.get_cluster_info(
                    cluster_name=cluster_name,
                    is_org_admin_search=is_org_admin_search), pksbroker
            except PksDuplicateClusterError as err:
                LOGGER.debug(f"Get cluster info on {cluster_name}"
                             f"on PKS failed with error: {err}")
                raise err
            except PksServerError as err:
                LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                             f"on {pks_ctx['host']} with error: {err}")
        return None, None

    def _create_pks_context_for_all_accounts_in_org(self):
        """Create PKS context for accounts in a given Org.

        If user is Sysadmin
            Creates PKS contexts for all PKS accounts defined in the entire
            system.
        else
            Creates PKS contexts for all PKS accounts assigned to the org.
            However if separate service accounts for each org hasn't been
            configued by admin via pks.yaml, then PKS accounts of the PKS
            server corresponding to the vCenters powering the individual
            orgVDC of the org will be picked up for creating the PKS contexts.

        :return: list of dict, where each dictionary is a PKS context

        :rtype: list
        """
        if not self.pks_cache:
            return []

        if self.vcd_client.is_sysadmin():
            all_pks_account_info = \
                self.pks_cache.get_all_pks_account_info_in_system()
            pks_ctx_list = [OvdcCache.construct_pks_context(
                pks_account_info, credentials_required=True)
                for pks_account_info in all_pks_account_info]
            return pks_ctx_list

        org_name = self.session.get('org')
        if self.pks_cache.do_orgs_have_exclusive_pks_account():
            pks_account_infos = \
                self.pks_cache.get_exclusive_pks_accounts_info_for_org(
                    org_name)
            pks_ctx_list = [OvdcCache.construct_pks_context
                            (pks_account_info, credentials_required=True)
                            for pks_account_info in pks_account_infos]
        else:
            org_resource = self.vcd_client.get_org()
            org = Org(self.vcd_client, resource=org_resource)
            vdc_names = [vdc['name'] for vdc in org.list_vdcs()]
            # Constructing dict instead of list to avoid duplicates
            # TODO() figure out a way to add pks contexts to a set directly
            pks_ctx_dict = {}
            for vdc_name in vdc_names:
                # this is a full blown pks_account_info + pvdc_info +
                # compute_profile_name dictionary
                ctr_prov_ctx = \
                    self.ovdc_cache.get_ovdc_container_provider_metadata(
                        ovdc_name=vdc_name, org_name=org_name,
                        credentials_required=True)
                if ctr_prov_ctx[K8S_PROVIDER_KEY] == K8sProviders.PKS:
                    pks_ctx_dict[ctr_prov_ctx['vc']] = ctr_prov_ctx

            pks_ctx_list = list(pks_ctx_dict.values())

        return pks_ctx_list

    def _get_ctr_prov_ctx_from_ovdc_metadata(self, ovdc_name=None,
                                             org_name=None):
        ovdc_name = \
            ovdc_name or self.req_spec.get('vdc')
        org_name = \
            org_name or self.req_spec.get('org') or self.session.get('org')

        if ovdc_name and org_name:
            ctr_prov_ctx = \
                self.ovdc_cache.get_ovdc_container_provider_metadata(
                    ovdc_name=ovdc_name, org_name=org_name,
                    credentials_required=True, nsxt_info_required=True)
            return ctr_prov_ctx

    def _get_broker_based_on_ctr_prov_ctx(self, ctr_prov_ctx):
        # If system is equipped with PKS, use the metadata on ovdc to determine
        # the correct broker, otherwise fallback to vCD for cluster deployment.
        # However if the system is enabled for PKS and has no metadata on odvc
        # or isn't enabled for container deployment raise appropriate
        # exception.
        if self.pks_cache:
            if ctr_prov_ctx:
                if ctr_prov_ctx.get(K8S_PROVIDER_KEY) == K8sProviders.PKS:
                    return PKSBroker(self.tenant_auth_token, self.req_spec,
                                     pks_ctx=ctr_prov_ctx)
                elif ctr_prov_ctx.get(K8S_PROVIDER_KEY) == K8sProviders.NATIVE:
                    return VcdBroker(self.tenant_auth_token, self.req_spec)

        else:
            return VcdBroker(self.tenant_auth_token, self.req_spec)

        raise CseServerError("Org VDC is not enabled for Kubernetes cluster "
                             "deployment")

    def get_broker_based_on_vdc(self):
        """Get the broker based on ovdc.

        :return: broker

        :rtype: container_service_extension.abstract_broker.AbstractBroker
        """
        ovdc_name = self.req_spec.get('vdc')
        org_name = self.req_spec.get('org') or self.session.get('org')

        ctr_prov_ctx = self._get_ctr_prov_ctx_from_ovdc_metadata(
            ovdc_name=ovdc_name, org_name=org_name)

        return self._get_broker_based_on_ctr_prov_ctx(ctr_prov_ctx)

    def _get_pks_plans_and_server_for_vdc(self,
                                          vdc,
                                          org_resource,
                                          vc_to_pks_plans_map):
        pks_server = ''
        pks_plans = []
        vc_backing_vdc = self.ovdc_cache.get_ovdc(
            ovdc_name=vdc['name'],
            org_name=org_resource.get('name')).resource.ComputeProviderScope

        pks_plan_and_server_info = vc_to_pks_plans_map.get(vc_backing_vdc, [])
        if len(pks_plan_and_server_info) > 0:
            pks_plans = pks_plan_and_server_info[0]
            pks_server = pks_plan_and_server_info[1]
        return pks_plans, pks_server

    def _construct_vc_to_pks_map(self):
        pks_vc_plans_map = {}
        pks_ctx_list = self._create_pks_context_for_all_accounts_in_org()

        for pks_ctx in pks_ctx_list:
            if pks_ctx['vc'] in pks_vc_plans_map:
                continue
            pks_broker = PKSBroker(self.tenant_auth_token, self.req_spec,
                                   pks_ctx)
            plans = pks_broker.list_plans()
            plan_names = [plan.get('name') for plan in plans]
            pks_vc_plans_map[pks_ctx['vc']] = [plan_names, pks_ctx['host']]
        return pks_vc_plans_map
