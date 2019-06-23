# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

from pyvcloud.vcd.org import Org
import requests

from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksServerError
from container_service_extension.exceptions import UnauthorizedActionError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pyvcloud_utils import get_sys_admin_client
from container_service_extension.pyvcloud_utils import get_vdc_by_id
from container_service_extension.server_constants import CseOperation
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProviders
from container_service_extension.utils import get_pks_cache


class OvdcManager(object):
    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec
        self.ovdc_cache = OvdcCache()
        self.pks_cache = get_pks_cache()

    def invoke(self, op):
        """Handle ovdc related operations.

        :param CseOperation op: Operation to be performed on the ovdc.

        :return result: result of the operation.

        :rtype: dict
        """
        result = {}
        result['body'] = []
        self.is_ovdc_present_in_request = self.req_spec.get('vdc')

        if op == CseOperation.OVDC_ENABLE_DISABLE:
            pks_ctx, ovdc = self._get_ovdc_params()
            if self.req_spec[K8S_PROVIDER_KEY] == K8sProviders.PKS:
                self._create_pks_compute_profile(pks_ctx)
            task = self.ovdc_cache. \
                set_ovdc_container_provider_metadata(
                    ovdc,
                    container_prov_data=pks_ctx,
                    container_provider=self.req_spec[K8S_PROVIDER_KEY])
            # TODO() Constructing response should be moved out of this layer
            result['body'] = {'task_href': task.get('href')}
        elif op == CseOperation.OVDC_INFO:
            ovdc_id = self.req_spec.get('ovdc_id')
            # TODO() Constructing response should be moved out of this layer
            result['body'] = self.ovdc_cache. \
                get_ovdc_container_provider_metadata(ovdc_id=ovdc_id)
        elif op == CseOperation.OVDC_LIST:
            list_pks_plans = self.req_spec.get('list_pks_plans', False)
            result['body'] = self._list_ovdcs(list_pks_plans=list_pks_plans)

        return result

    def _get_ovdc_params(self):
        ovdc_id = self.req_spec.get('ovdc_id')
        org_name = self.req_spec.get('org_name')
        pks_plans = self.req_spec['pks_plans']
        pks_cluster_domain = self.req_spec['pks_cluster_domain']
        ovdc = self.ovdc_cache.get_ovdc(ovdc_id=ovdc_id)
        pvdc_id = self.ovdc_cache.get_pvdc_id(ovdc)

        pks_context = None
        if self.req_spec[K8S_PROVIDER_KEY] == K8sProviders.PKS:
            if not self.pks_cache:
                raise CseServerError('PKS config file does not exist')
            pvdc_info = self.pks_cache.get_pvdc_info(pvdc_id)
            if not pvdc_info:
                LOGGER.debug(f"pvdc '{pvdc_id}' is not backed "
                             f"by PKS-managed-vSphere resources")
                raise CseServerError(f"'{ovdc.resource.get('name')}' is not "
                                     f"eligible to provide resources for "
                                     f"PKS clusters. Refer debug logs for more"
                                     f" details.")
            pks_account_info = self.pks_cache.get_pks_account_info(
                org_name, pvdc_info.vc)
            nsxt_info = self.pks_cache.get_nsxt_info(pvdc_info.vc)

            pks_compute_profile_name = \
                self._create_pks_compute_profile_name_from_vdc_id(ovdc_id)
            pks_context = OvdcCache.construct_pks_context(
                pks_account_info=pks_account_info,
                pvdc_info=pvdc_info,
                nsxt_info=nsxt_info,
                pks_compute_profile_name=pks_compute_profile_name,
                pks_plans=pks_plans,
                pks_cluster_domain=pks_cluster_domain,
                credentials_required=True)

        return pks_context, ovdc

    def _create_pks_compute_profile(self, pks_ctx):
        ovdc_id = self.req_spec.get('ovdc_id')
        org_name = self.req_spec.get('org_name')
        ovdc_name = self.req_spec.get('ovdc_name')
        # Compute profile creation
        pks_compute_profile_name = \
            self._create_pks_compute_profile_name_from_vdc_id(ovdc_id)
        pks_compute_profile_description = f"{org_name}--{ovdc_name}" \
            f"--{ovdc_id}"
        pks_az_name = f"az-{ovdc_name}"
        ovdc_rp_name = f"{ovdc_name} ({ovdc_id})"

        compute_profile_params = PksComputeProfileParams(
            pks_compute_profile_name, pks_az_name,
            pks_compute_profile_description,
            pks_ctx.get('cpi'),
            pks_ctx.get('datacenter'),
            pks_ctx.get('cluster'),
            ovdc_rp_name).to_dict()

        LOGGER.debug(f"Creating PKS Compute Profile with name:"
                     f"{pks_compute_profile_name}")

        pksbroker = PKSBroker(self.tenant_auth_token, self.req_spec, pks_ctx)
        try:
            pksbroker.create_compute_profile(**compute_profile_params)
        except PksServerError as ex:
            if ex.status == requests.codes.conflict:
                LOGGER.debug(f"Compute profile name {pks_compute_profile_name}"
                             f" already exists\n{str(ex)}")
            else:
                raise ex

    def _create_pks_compute_profile_name_from_vdc_id(self, vdc_id):
        """Construct pks compute profile name.

        :param str vdc_id: UUID of the vdc in vcd

        :return: pks compute profile name

        :rtype: str
        """
        client = get_sys_admin_client()
        vdc = get_vdc_by_id(client, vdc_id)
        return f"cp--{vdc_id}--{vdc.name}"

    def _list_ovdcs(self, list_pks_plans=False):
        """Get list of ovdcs.

        If client is sysadmin,
            Gets all ovdcs of all organizations.
        Else
            Gets all ovdcs of the organization in context.
        """
        if self.vcd_client.is_sysadmin():
            org_resource_list = self.vcd_client.get_org_list()
        else:
            org_resource_list = list(self.vcd_client.get_org())

        ovdc_list = []
        vc_to_pks_plans_map = {}
        if list_pks_plans:
            if self.vcd_client.is_sysadmin():
                vc_to_pks_plans_map = self._construct_vc_to_pks_map()
            else:
                raise UnauthorizedActionError(
                    'Operation Denied. Plans available only for '
                    'System Administrator.')
        for org_resource in org_resource_list:
            org = Org(self.vcd_client, resource=org_resource)
            vdc_list = org.list_vdcs()
            for vdc in vdc_list:
                ctr_prov_ctx = \
                    self.ovdc_cache.get_ovdc_container_provider_metadata(
                        ovdc_name=vdc['name'], org_name=org.get_name(),
                        credentials_required=False)
                if list_pks_plans:
                    pks_plans, pks_server = self.\
                        _get_pks_plans_and_server_for_vdc(vdc,
                                                          org_resource,
                                                          vc_to_pks_plans_map)
                    vdc_dict = {
                        'org': org.get_name(),
                        'name': vdc['name'],
                        'pks_api_server': pks_server,
                        'available pks plans': pks_plans
                    }
                else:
                    vdc_dict = {
                        'name': vdc['name'],
                        'org': org.get_name(),
                        K8S_PROVIDER_KEY: ctr_prov_ctx[K8S_PROVIDER_KEY]
                    }
                ovdc_list.append(vdc_dict)
        return ovdc_list


class PksComputeProfileParams(namedtuple("PksComputeProfileParams",
                                         'cp_name, az_name, description,'
                                         'cpi,datacenter_name, '
                                         'cluster_name, ovdc_rp_name')):
    """Construct PKS ComputeProfile Parameters ."""

    def __str__(self):
        return f"class:{PksComputeProfileParams.__name__}," \
            f" cp_name:{self.cp_name}, az_name:{self.az_name}, " \
            f" description:{self.description}, cpi:{self.cpi}, " \
            f" datacenter_name:{self.datacenter_name}, " \
            f" cluster_name:{self.cluster_name}, " \
            f" ovdc_rp_name:{self.ovdc_rp_name}"

    def to_dict(self):
        return dict(self._asdict())
