# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.utils import connect_vcd_user_via_token
from container_service_extension.utils import exception_handler
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import get_vcd_sys_admin_client
from container_service_extension.utils import get_vdc
from container_service_extension.utils import OK
from container_service_extension.broker import VcdBroker
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pksbroker import PKSBroker

from enum import Enum, unique

from pyvcloud.vcd.org import Org


@unique
class Operation(Enum):
    CREATE_CLUSTER = 'create cluster'
    DELETE_CLUSTER = 'delete clsuter'
    GET_CLUSTER = 'get cluster info'
    LIST_CLUSTERS = 'list clusters'
    RESIZE_CLUSTER = 'resize cluster'


class Broker_manager(object):
    def __init__(self, headers, body):
        self.headers = headers
        self.body = body
        from container_service_extension.service import Service
        config = get_server_runtime_config()
        self.pks_cache = Service().get_pks_cache()
        self.client, self.session = connect_vcd_user_via_token(
            vcd_uri=config['vcd']['host'],
            headers=self.headers,
            verify_ssl_certs=config['vcd']['verify'])


    @exception_handler
    def invoke(self, op, on_the_fly_request_body=None):
        result = {}
        result['body'] = []
        result['status_code'] = OK
        if on_the_fly_request_body:
            self.body = on_the_fly_request_body

        if op == Operation.GET_CLUSTER:
            result['body'] = self._get_cluster_info(self.body['cluster_name'])

        if op == Operation.LIST_CLUSTERS:
            result['body'] = self._list_clusters()

        return result

    def _get_cluster_info(self, cluster_name):
        is_ovdc_present_in_body = self.body.get('vdc') if self.body else None
        if is_ovdc_present_in_body:
            broker = self.get_new_broker(self.body)
            return broker.get_cluster_info(cluster_name)
        else:
            vcd_broker = VcdBroker(self.headers, self.body)
            try:
                return vcd_broker.get_cluster_info(cluster_name)
            except Exception as err:
                LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                             f"on vCD with error {err}")
                pass

            pks_ctx_list = self._get_all_pks_accounts_in_org()
            for pks_ctx in pks_ctx_list:
                pks_broker = PKSBroker(self.headers, self.body, pks_ctx)
                try:
                    return pks_broker.get_cluster_info(cluster_name)
                except Exception as err:
                    LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                                 f"on {pks_ctx['host']} with error {err}")
                    pass
        raise ClusterNotFoundError(f'cluster {cluster_name} not found '
                                   f'either in vCD or PKS')

    def _list_clusters(self):
        is_ovdc_present_in_body = self.body.get('vdc') if self.body else None
        if is_ovdc_present_in_body:
            broker = self.get_new_broker(self.body)
            return broker.list_clusters()
        else:
            vcd_broker = VcdBroker(self.headers, self.body)
            vcd_clusters = []
            for cluster in vcd_broker.list_clusters():
                vcd_cluster = {k: cluster.get(k, None) for k in
                               ('name', 'vdc_name', 'status')}
                vcd_cluster[OvdcCache.CONTAINER_PROVIDER] = 'vcd'
                vcd_clusters.append(vcd_cluster)

            pks_clusters = []
            pks_ctx_list = self._get_all_pks_accounts_in_org()
            for pks_ctx in pks_ctx_list:
                pks_broker = PKSBroker(self.headers, self.body, pks_ctx)
                try:
                    for cluster in pks_broker.list_clusters():
                        pks_cluster = {k: cluster.get(k, None) for k in
                                       ('name', 'vdc_name', 'status')}
                        pks_cluster[OvdcCache.CONTAINER_PROVIDER] = 'pks'
                        pks_clusters.append(pks_cluster)
                except Exception as err:
                    LOGGER.debug(f"List clusters failed on {pks_ctx['host']}"
                                 f" with error {err}")
                    pass
            return vcd_clusters + pks_clusters

    def _get_all_pks_accounts_in_org(self):

        if self.client.is_sysadmin():
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

        ovdc_cache = OvdcCache(get_vcd_sys_admin_client())
        org_resource = self.client.get_org()
        org = Org(self.client, resource=org_resource)
        vdc_list = org.list_vdcs()

        # Constructing dict with key='vc' ensures no duplicates in the result
        pks_ctx_dict = {}
        for vdc in vdc_list:
            ctr_prov_ctx = ovdc_cache.get_ovdc_container_provider_metadata(
                ovdc_name=vdc['name'], org_name=org.get_name(),
                credentials_required=True)
            if ctr_prov_ctx[OvdcCache.CONTAINER_PROVIDER] == 'pks':
                pks_ctx_dict[ctr_prov_ctx['vc']]=ctr_prov_ctx

        return pks_ctx_dict.values()

    def get_new_broker(self, on_the_fly_request_body=None):

        request_body = self.body
        if on_the_fly_request_body:
            request_body = on_the_fly_request_body

        config = get_server_runtime_config()
        tenant_client, session = connect_vcd_user_via_token(
            vcd_uri=config['vcd']['host'],
            headers=self.headers,
            verify_ssl_certs=config['vcd']['verify'])
        ovdc_name = request_body.get('vdc') if request_body else None
        org_name = session.get('org')
        LOGGER.debug(f"org_name={org_name};vdc_name=\'{ovdc_name}\'")

        """
        Get the ovdc metadata from the logged-in org and ovdc.
        Create the right broker based on value of 'container_provider'.
        Fall back to DefaultBroker for missing ovdc or org.
        """
        if ovdc_name and org_name:
            admin_client = get_vcd_sys_admin_client()
            ovdc_cache = OvdcCache(admin_client)
            ctr_prov_ctx = ovdc_cache.get_ovdc_container_provider_metadata(
                ovdc_name=ovdc_name, org_name=org_name,
                credentials_required=True)
            LOGGER.debug(
                f"ovdc metadata for {ovdc_name}-{org_name}=>{ctr_prov_ctx}")
            if ctr_prov_ctx.get('container_provider') == 'pks':
                return PKSBroker(self.headers, request_body,
                                 pks_ctx=ctr_prov_ctx)
            else:
                return VcdBroker(self.headers, request_body)
        else:
            # TODO() - This call should be based on a boolean flag
            # Specify flag in config file whether to have default
            # handling is required for missing ovdc or org.
            return VcdBroker(self.headers, request_body)

# b = Broker_manager(None, None)
# b.invoke(Operation.GET_CLUSTER)
