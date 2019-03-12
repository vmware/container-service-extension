# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.vcdbroker import VcdBroker
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import CONTAINER_PROVIDER
from container_service_extension.ovdc_cache import CtrProvType
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.utils import connect_vcd_user_via_token
from container_service_extension.utils import exception_handler
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import get_vcd_sys_admin_client
from container_service_extension.utils import OK
from container_service_extension.utils import ACCEPTED

from enum import Enum, unique

from pyvcloud.vcd.org import Org

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
@unique
class Operation(Enum):
    CREATE_CLUSTER = 'create cluster'
    DELETE_CLUSTER = 'delete cluster'
    GET_CLUSTER = 'get cluster info'
    LIST_CLUSTERS = 'list clusters'
    RESIZE_CLUSTER = 'resize cluster'


class BrokerManager(object):
    def __init__(self, headers, params, body):
        self.headers = headers
        self.params = params
        self.body = body
        config = get_server_runtime_config()
        from container_service_extension.service import Service
        self.pks_cache = Service().get_pks_cache()
        self.ovdc_cache = OvdcCache(get_vcd_sys_admin_client())
        self.vcd_client, self.session = connect_vcd_user_via_token(
            vcd_uri=config['vcd']['host'],
            headers=self.headers,
            verify_ssl_certs=config['vcd']['verify'])


    @exception_handler
    def invoke(self, op, on_the_fly_request_body=None):
        """Invoke right broker(s) to perform the operation requested and do
        further (pre/post)processing on the request/result(s) if required.

        Depending on the operation requested, this method may do one or more
        of below mentioned points.
        1. Extract and construct the relevant params for the operation.
        2. Choose right broker to perform the operation/method requested.
        3. Scan through available brokers to aggregate (or) filter results.
        4. Construct and return the HTTP response

        :param Operation op: Operation to be performed by one of the brokers.
        :param dict on_the_fly_request_body: body constructed by processor.

        :return result: HTTP response

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK

        if on_the_fly_request_body:
            self.body.update(on_the_fly_request_body)

        if op == Operation.GET_CLUSTER:
            result['body'] = \
                self._get_cluster_info(self.body['cluster_name'])[0]
        elif op == Operation.LIST_CLUSTERS:
            result['body'] = self._list_clusters()
        elif op == Operation.DELETE_CLUSTER:
            self._delete_cluster(self.body['cluster_name'])
            result['status_code'] = ACCEPTED
        elif op == Operation.RESIZE_CLUSTER:
            self._resize_cluster(self.body['cluster_name'],
                                 self.body['node_count'])
            result['status_code'] = ACCEPTED
        elif op == Operation.CREATE_CLUSTER:
            # TODO(ClusterParams) Create an inner class "ClusterParams"
            #  in abstract_broker.py and have subclasses define and use it
            #  as instance variable.
            #  Method 'Create_cluster' in VcdBroker and PksBroker should take
            #  ClusterParams either as a param (or)
            #  read from instance variable (if needed only).
            cluster_params = {'cluster_name': self.body.get('name', None),
                              'vdc_name': self.body.get('vdc', None),
                              'node_count': self.body.get('node_count', None),
                              'storage_profile': self.body.get(
                                  'storage_profile', None),
                              'network_name': self.body.get('network', None),
                              'template': self.body.get('template', None),
                              'pks_plan': self.body.get('pks_plan', None),
                              'pks_ext_host': self.body.get('pks_ext_host',
                                                            None)
                              }
            result['body'] = self._create_cluster(**cluster_params)
            result['status_code'] = ACCEPTED

        return result

    def _get_cluster_info(self, cluster_name):
        """Logic of the method is as follows.

        If 'ovdc' is present in the body,
            choose the right broker (by identifying the container_provider
            (vcd|pks) defined for that ovdc) to do get_cluster operation.
        Else
            Invoke set of all (vCD/PKS)brokers in the org to find the cluster

        Returns a tuple of (cluster and the broker instance used to find the
        cluster)
        """
        vdc = self.params.get('vdc', None)
        print(f'vdc: {vdc}')
        is_ovdc_present_in_request = self.body.get('vdc', None) or self.params.get('vdc', None)
        if is_ovdc_present_in_request:
            print('inside ovdc blcok')
            broker = self.get_broker_based_on_vdc()
            return broker.get_cluster_info(cluster_name), broker
        else:
            cluster, broker = self._find_cluster_in_org(cluster_name)
            if cluster is not None:
                return cluster, broker

        raise ClusterNotFoundError(f'cluster {cluster_name} not found '
                                   f'either in vCD or PKS')

    def _list_clusters(self):
        """Logic of the method is as follows,

        If 'ovdc' is present in the body,
            choose the right broker (by identifying the container_provider
            (vcd|pks) defined for that ovdc) to do list_clusters op.
        Else
            Invoke set of all (vCD/PKS)brokers in the org to do list_clusters.
            Post-process the result returned by each broker.
            Aggregate all the results into one.
        """
        is_ovdc_present_in_request = self.body.get('vdc', None) or self.params.get('vdc', None)
        if is_ovdc_present_in_request:
            broker = self.get_broker_based_on_vdc()
            return broker.list_clusters()
        else:
            common_cluster_properties = ('name', 'vdc', 'status')
            vcd_broker = VcdBroker(self.headers, self.body)
            vcd_clusters = []
            for cluster in vcd_broker.list_clusters():
                vcd_cluster = {k: cluster.get(k, None) for k in
                               common_cluster_properties}
                vcd_cluster[CONTAINER_PROVIDER] = CtrProvType.VCD.value
                vcd_clusters.append(vcd_cluster)

            pks_clusters = []
            pks_ctx_list = self._get_all_pks_accounts_in_org()
            for pks_ctx in pks_ctx_list:
                pks_broker = PKSBroker(self.headers, self.body, pks_ctx)
                for cluster in pks_broker.list_clusters():
                    pks_cluster = {k: cluster.get(k, None) for k in
                                   common_cluster_properties}
                    pks_cluster[CONTAINER_PROVIDER] = CtrProvType.PKS.value
                    pks_clusters.append(pks_cluster)
            return vcd_clusters + pks_clusters

    def _resize_cluster(self, cluster_name, node_count):
        broker = self._get_cluster_info(cluster_name)[1]
        return broker.resize_cluster(name=cluster_name,
                                     num_worker_nodes=node_count)

    def _delete_cluster(self, cluster_name):
        broker = self._get_cluster_info(cluster_name)[1]
        return broker.delete_cluster(cluster_name)

    def _create_cluster(self, **kwargs):
        cluster_name = kwargs['cluster_name']
        cluster = self._find_cluster_in_org(cluster_name)[0]
        if cluster is None:
            broker = self.get_broker_based_on_vdc()
            return broker.create_cluster(**kwargs)
        else:
            raise CseServerError(f'Cluster with name: {cluster_name} '
                                 f'already found')

    def _find_cluster_in_org(self, cluster_name):
        """Invoke set of all (vCD/PKS)brokers in the org to find the cluster.

        If cluster found:
            Return a tuple of (cluster and the broker instance used to find
            the cluster)
        Else:
            (None, None) if cluster not found.
        """
        vcd_broker = VcdBroker(self.headers, self.body)
        try:
            return vcd_broker.get_cluster_info(cluster_name), vcd_broker
        except Exception as err:
            LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                         f"on vCD with error: {err}")
            pass

        pks_ctx_list = self._get_all_pks_accounts_in_org()
        for pks_ctx in pks_ctx_list:
            pksbroker = PKSBroker(self.headers, self.body, pks_ctx)
            try:
                return pksbroker.get_cluster_info(cluster_name), pksbroker
            except Exception as err:
                LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                             f"on {pks_ctx['host']} with error: {err}")
                pass

        return None, None

    def _get_all_pks_accounts_in_org(self):
        """Get a set of PKS accounts in a given Org or System.

        If user is Sysadmin
            Gets all PKS accounts defined in the entire System.
        Else
            Gets either PKS accounts 'per org per vc' (or) 'per vc' based on
            the admin configuration specified in pks.yaml

        :return:
        """
        if self.vcd_client.is_sysadmin():
            pks_acc_list = self.pks_cache.get_all_pks_accounts_in_system()
            pks_ctx_list = [OvdcCache.construct_pks_context(
                pks_account, credentials_required=True)
                for pks_account in pks_acc_list]
            return pks_ctx_list

        if self.pks_cache.are_svc_accounts_per_org_per_vc():
            pks_acc_list = \
                self.pks_cache.get_all_pks_accounts_per_org_per_vc_in_org\
                    (self.session.get('org'))
            pks_ctx_list = [OvdcCache.construct_pks_context
                            (pks_account, credentials_required=True)
                            for pks_account in pks_acc_list]
        else:
            pks_ctx_list = self._get_all_pks_accounts_per_vc_in_org()

        return pks_ctx_list

    def _get_all_pks_accounts_per_vc_in_org(self):
        """Get a set of PKS accounts in a given Org
        based on 'vc' as a key.
        """

        org_resource = self.vcd_client.get_org()
        org = Org(self.vcd_client, resource=org_resource)
        vdc_list = org.list_vdcs()

        # Constructing dict instead of list to avoid duplicates
        # TODO figure out a way to add dicts to sets directly
        pks_ctx_dict = {}
        for vdc in vdc_list:
            ctr_prov_ctx = \
                self.ovdc_cache.get_ovdc_container_provider_metadata(
                    ovdc_name=vdc['name'], org_name=org.get_name(),
                    credentials_required=True)
            if ctr_prov_ctx[CONTAINER_PROVIDER] == CtrProvType.PKS.value:
                pks_ctx_dict[ctr_prov_ctx['vc']]=ctr_prov_ctx

        return pks_ctx_dict.values()

    def get_broker_based_on_vdc(self, on_the_fly_request_body=None):
        """Gets the broker based on ovdc.

        :param on_the_fly_request_body: New or modified HTTP request body by
        CSE {container_service_extension.processor.ServiceProcessor}
        :return: broker

        :rtype: container_service_extension.abstract_broker.AbstractBroker
        """

        if on_the_fly_request_body:
            self.body.update(on_the_fly_request_body)

        ovdc_name = self.body.get('vdc', None) or self.params.get('vdc', None)
        org_name = self.session.get('org')
        LOGGER.debug(f"org_name={org_name};vdc_name=\'{ovdc_name}\'")

        """
        Get the ovdc metadata from the logged-in org and ovdc.
        Create the right broker based on value of 'container_provider'.
        Fall back to DefaultBroker for missing ovdc or org.
        """
        if ovdc_name and org_name:
            ctr_prov_ctx = \
                self.ovdc_cache.get_ovdc_container_provider_metadata(
                ovdc_name=ovdc_name, org_name=org_name,
                credentials_required=True)
            LOGGER.debug(
                f"ovdc metadata for {ovdc_name}-{org_name}=>{ctr_prov_ctx}")
            if ctr_prov_ctx.get('container_provider') == CtrProvType.PKS.value:
                return PKSBroker(self.headers, self.body,
                                 pks_ctx=ctr_prov_ctx)
            else:
                return VcdBroker(self.headers, self.body)
        else:
            # TODO() - This call should be based on a boolean flag
            # Specify flag in config file whether to have default
            # handling is required for missing ovdc or org.
            return VcdBroker(self.headers, self.body)
