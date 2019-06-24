# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.org import Org

from container_service_extension.exceptions import UnauthorizedActionError
from container_service_extension.ovdc_manager import create_pks_compute_profile
from container_service_extension.ovdc_manager import \
    construct_ctr_prov_ctx_from_pks_cache
from container_service_extension.ovdc_manager import OvdcManager
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pksbroker_manager import PksBrokerManager
from container_service_extension.pyvcloud_utils \
    import connect_vcd_user_via_token
from container_service_extension.pyvcloud_utils import get_vdc
from container_service_extension.server_constants import CseOperation
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProviders
from container_service_extension.utils import is_pks_enabled
from container_service_extension.utils import str2bool

class OvdcRequestHandler(object):
    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec

    def invoke(self, op):
        """Handle ovdc related operations.

        :param CseOperation op: Operation to be performed on the ovdc.

        :return result: result of the operation.

        :rtype: dict
        """
        result = {}

        if op == CseOperation.OVDC_ENABLE_DISABLE:
            ovdc_id = self.req_spec.get('ovdc_id')
            org_name = self.req_spec.get('org_name')
            pks_plans = self.req_spec.get('pks_plans')
            pks_cluster_domain = self.req_spec.get('pks_cluster_domain')
            container_provider = self.req_spec[K8S_PROVIDER_KEY]

            ctr_prov_ctx = construct_ctr_prov_ctx_from_pks_cache(
                ovdc_id=ovdc_id, org_name=org_name,
                pks_plans=pks_plans, pks_cluster_domain=pks_cluster_domain,
                container_provider=container_provider)

            if container_provider == K8sProviders.PKS:
                if is_pks_enabled():
                    create_pks_compute_profile(
                        ctr_prov_ctx, self.tenant_auth_token, self.req_spec)

            task = OvdcManager().set_ovdc_container_provider_metadata(
                ovdc_id=ovdc_id,
                container_prov_data=ctr_prov_ctx,
                container_provider=container_provider)

            result = {'task_href': task.get('href')}
        elif op == CseOperation.OVDC_INFO:
            ovdc_id = self.req_spec.get('ovdc_id')
            result = OvdcManager().get_ovdc_container_provider_metadata(
                ovdc_id=ovdc_id)
        elif op == CseOperation.OVDC_LIST:
            list_pks_plans = str2bool(self.req_spec.get('list_pks_plans'))
            result = self._list_ovdcs(list_pks_plans=list_pks_plans)

        return result

    def _list_ovdcs(self, list_pks_plans):
        """Get list of ovdcs.

        If client is sysadmin,
            Gets all ovdcs of all organizations.
        Else
            Gets all ovdcs of the organization in context.
        """
        client,_ = connect_vcd_user_via_token(tenant_auth_token)
        if client.is_sysadmin():
            org_resource_list = client.get_org_list()
        else:
            org_resource_list = list(client.get_org())

        ovdc_list = []
        vc_to_pks_plans_map = {}
        if is_pks_enabled() and list_pks_plans:
            if client.is_sysadmin():
                vc_to_pks_plans_map = self._construct_vc_to_pks_map()
            else:
                raise UnauthorizedActionError(
                    'Operation Denied. Plans available only for '
                    'System Administrator.')
        for org_resource in org_resource_list:
            org = Org(client, resource=org_resource)
            vdc_list = org.list_vdcs()
            for vdc_sparse in vdc_list:
                ctr_prov_ctx = \
                    OvdcManager().get_ovdc_container_provider_metadata(
                        ovdc_name=vdc_sparse['name'], org_name=org.get_name(),
                        credentials_required=False)
                vdc_dict = {
                    'name': vdc_sparse['name'],
                    'org': org.get_name(),
                    K8S_PROVIDER_KEY: ctr_prov_ctx[K8S_PROVIDER_KEY]
                }
                if is_pks_enabled() and list_pks_plans:
                    pks_plans, pks_server = self.\
                        _get_pks_plans_and_server_for_vdc(client,
                                                          vdc_sparse,
                                                          org_resource,
                                                          vc_to_pks_plans_map)
                    vdc_dict['pks_api_server'] = pks_server
                    vdc_dict['available pks plans'] = pks_plans
                ovdc_list.append(vdc_dict)
        return ovdc_list

    def _get_pks_plans_and_server_for_vdc(self,
                                          client,
                                          vdc_sparse,
                                          org_resource,
                                          vc_to_pks_plans_map):
        pks_server = ''
        pks_plans = []
        vdc = get_vdc(client, vdc_name=vdc_sparse['name'],
                      org_name=org_resource.get('name'))
        vc_backing_vdc = vdc.get_resource().ComputeProviderScope

        pks_plan_and_server_info = vc_to_pks_plans_map.get(vc_backing_vdc, [])
        if len(pks_plan_and_server_info) > 0:
            pks_plans = pks_plan_and_server_info[0]
            pks_server = pks_plan_and_server_info[1]
        return pks_plans, pks_server

    def _construct_vc_to_pks_map(self):
        pks_vc_plans_map = {}
        pksbroker_manager = PksBrokerManager(
            self.tenant_auth_token, self.req_spec)
        pks_ctx_list = \
            pksbroker_manager.create_pks_context_for_all_accounts_in_org()

        for pks_ctx in pks_ctx_list:
            if pks_ctx['vc'] in pks_vc_plans_map:
                continue
            pks_broker = PKSBroker(self.tenant_auth_token, self.req_spec,
                                   pks_ctx)
            plans = pks_broker.list_plans()
            plan_names = [plan.get('name') for plan in plans]
            pks_vc_plans_map[pks_ctx['vc']] = [plan_names, pks_ctx['host']]
        return pks_vc_plans_map
