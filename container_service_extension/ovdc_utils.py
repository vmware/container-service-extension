# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import ResourceType
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.org import Org
import pyvcloud.vcd.utils as pyvcd_utils
from pyvcloud.vcd.utils import to_dict
import requests

from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksServerError
from container_service_extension.exceptions import UnauthorizedRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pks_cache import PksCache
from container_service_extension.pksbroker import PksBroker
import container_service_extension.pksbroker_manager as pks_broker_manager
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.server_constants import PKS_COMPUTE_PROFILE_KEY # noqa: E501
from container_service_extension.server_constants import PKS_PLANS_KEY
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils


def get_ovdc_k8s_provider_metadata(org_name=None, ovdc_name=None, ovdc_id=None,
                                   include_credentials=False,
                                   include_nsxt_info=False):
    """Get k8s provider metadata for an org VDC.

    :param str org_name:
    :param str ovdc_name:
    :param str ovdc_id:
    :param bool include_credentials:
    :param bool include_nsxt_info:

    :return: Dictionary with k8s provider metadata

    :rtype: Dict
    """
    client = None
    try:
        client = vcd_utils.get_sys_admin_client()
        ovdc = vcd_utils.get_vdc(client=client, vdc_name=ovdc_name,
                                 vdc_id=ovdc_id, org_name=org_name,
                                 is_admin_operation=True)
        all_metadata = pyvcd_utils.metadata_to_dict(ovdc.get_all_metadata())
        k8s_provider = all_metadata.get(K8S_PROVIDER_KEY, K8sProvider.NONE)

        result = {
            K8S_PROVIDER_KEY: k8s_provider
        }

        if k8s_provider == K8sProvider.PKS:
            result.update({k: all_metadata[k] for k in PksCache.get_pks_keys()}) # noqa: E501
            result[PKS_PLANS_KEY] = result[PKS_PLANS_KEY].split(',')

            # Get the credentials from PksCache
            if include_credentials or include_nsxt_info:
                pks_cache = utils.get_pks_cache()
                pvdc_info = \
                    pks_cache.get_pvdc_info(vcd_utils.get_pvdc_id(ovdc))
            if include_credentials:
                # noqa: E501 TODO in case only ovdc_id is provided, we need a way to get org_name
                pks_info = \
                    pks_cache.get_pks_account_info(org_name, pvdc_info.vc)
                result.update(pks_info.credentials._asdict())
            if include_nsxt_info:
                nsxt_info = pks_cache.get_nsxt_info(pvdc_info.vc)
                result['nsxt'] = nsxt_info

        return result
    finally:
        if client is not None:
            client.logout()


def get_ovdc_list(client,
                  list_pks_plans=False,
                  tenant_auth_token=None,
                  is_jwt_token=False):
    """Get details for all client-visible org VDCs.

    :param pyvcloud.vcd.client.Client client:
    :param bool list_pks_plans:
    :param str tenant_auth_token:
    :param bool is_jwt_token:

    :return: List of dict with str keys: ['name', 'org', 'k8s provider'].
        If @list_pks_plans is True, then dict will also have
        str keys: ['pks api server', 'available pks plans']

    :rtype: List[Dict]

    :raises UnauthorizedRequestError: if trying to @list_pks_plans
        as non-sysadmin.
    :raises ValueError: if @list_pks_plans is True and @tenant_auth_token
        is None.
    """
    if list_pks_plans and not client.is_sysadmin():
        raise UnauthorizedRequestError('Operation Denied. Plans available '
                                       'only for System Administrator.')
    if list_pks_plans and not tenant_auth_token:
        raise ValueError("Missing required parameters for listing pks plans.")

    if client.is_sysadmin():
        org_resource_list = client.get_org_list()
    else:
        org_resource_list = list(client.get_org())

    ovdc_list = []
    for org_resource in org_resource_list:
        org = Org(client, resource=org_resource)
        vdc_list = org.list_vdcs()
        for vdc_sparse in vdc_list:
            ovdc_name = vdc_sparse['name']
            org_name = org.get_name()

            k8s_metadata = get_ovdc_k8s_provider_metadata(ovdc_name=ovdc_name,
                                                          org_name=org_name)
            k8s_provider = k8s_metadata[K8S_PROVIDER_KEY]
            ovdc_info = {
                'name': ovdc_name,
                'org': org_name,
                'k8s provider': k8s_provider
            }

            if list_pks_plans:
                # client is sys admin if we're here
                pks_plans = ''
                pks_server = ''
                if k8s_provider == K8sProvider.PKS:
                    # vc name for vdc can only be found using typed query
                    q = \
                        client.get_typed_query(
                            ResourceType.ADMIN_ORG_VDC.value,
                            query_result_format=QueryResultFormat.RECORDS,
                            qfilter=f"name=={ovdc_name};orgName=={org_name}")
                    ovdc_records = list(q.execute())
                    if len(ovdc_records) == 0:
                        raise EntityNotFoundException(f"Org VDC {ovdc_name} not found in org {org_name}") # noqa: E501
                    ovdc_record = None
                    # there should only ever be one element in the generator
                    for record in ovdc_records:
                        ovdc_record = to_dict(record, resource_type=ResourceType.ADMIN_ORG_VDC.value) # noqa: E501
                        break
                    vc_name = ovdc_record['vcName']

                    vc_to_pks_plans_map = _get_vc_to_pks_plans_map(
                        tenant_auth_token, is_jwt_token)
                    pks_plan_and_server_info = \
                        vc_to_pks_plans_map.get(vc_name, [])
                    if len(pks_plan_and_server_info) > 0:
                        pks_plans = pks_plan_and_server_info[0]
                        pks_server = pks_plan_and_server_info[1]

                ovdc_info['pks api server'] = pks_server
                ovdc_info['available pks plans'] = pks_plans

            ovdc_list.append(ovdc_info)

    return ovdc_list


def update_ovdc_k8s_provider_metadata(ovdc_id,
                                      k8s_provider_data=None,
                                      k8s_provider=None):
    """Set the k8s provider metadata of given ovdc.

    :param str ovdc_id:
    :param dict k8s_provider_data: k8s provider context details
    :param K8sProvider k8s_provider: name of k8s provider for which
        the ovdc is being enabled to deploy k8 clusters on.
    """
    client = None
    try:
        client = vcd_utils.get_sys_admin_client()
        ovdc = vcd_utils.get_vdc(client, vdc_id=ovdc_id)
        ovdc_name = ovdc.get_resource().get('name')

        metadata = {}
        metadata[K8S_PROVIDER_KEY] = k8s_provider or \
            K8sProvider.NONE

        if k8s_provider != K8sProvider.PKS:
            LOGGER.debug(f"Remove existing metadata for ovdc:{ovdc_name}")
            _remove_metadata_from_ovdc(ovdc, PksCache.get_pks_keys())

            LOGGER.debug(f"Updated metadata for {k8s_provider}:"
                         f"{metadata}")
        else:
            k8s_provider_data.pop('username')
            k8s_provider_data.pop('secret')
            k8s_provider_data.pop('nsxt')
            metadata.update(k8s_provider_data)

        # set ovdc metadata into Vcd
        LOGGER.debug(f"On ovdc:{ovdc_name}, setting metadata:{metadata}")
        return ovdc.set_multiple_metadata(metadata, MetadataDomain.SYSTEM,
                                          MetadataVisibility.PRIVATE)
    finally:
        if client:
            client.logout()


def _get_vc_to_pks_plans_map(tenant_auth_token, is_jwt_token):
    pks_vc_plans_map = {}
    pks_ctx_list = pks_broker_manager.create_pks_context_for_all_accounts_in_org(tenant_auth_token, is_jwt_token) # noqa: E501

    for pks_ctx in pks_ctx_list:
        if pks_ctx['vc'] in pks_vc_plans_map:
            continue
        pks_broker = PksBroker(pks_ctx, tenant_auth_token, is_jwt_token)
        plans = pks_broker.list_plans()
        plan_names = [plan.get('name') for plan in plans]
        pks_vc_plans_map[pks_ctx['vc']] = [plan_names, pks_ctx['host']]
    return pks_vc_plans_map


def construct_pks_context(pks_account_info, pvdc_info=None, nsxt_info=None,
                          pks_compute_profile_name=None, pks_plans='',
                          pks_cluster_domain='',
                          credentials_required=False):
    """Construct PKS context dictionary.

    :param container_service_extension.pks_cache.PksAccountInfo
        pks_account_info: pks connection details
    :param container_service_extension.pks_cache.PvdcInfo pvdc_info:
        pvdc details including datacenter and cluster.
    :param str pks_compute_profile_name: name of the compute profile
    :param str pks_plans: comma separated values for pks plans
    :param bool credentials_required: determines if credentials have to
        be part of the resultant dictionary

    :return: pks context details

    :rtype: dict
    """
    pks_ctx = pks_account_info._asdict()
    credentials = pks_ctx.pop('credentials')
    if credentials_required:
        pks_ctx.update(credentials._asdict())
    if pvdc_info:
        pks_ctx.update(pvdc_info._asdict())
    pks_ctx[PKS_COMPUTE_PROFILE_KEY] = '' if not pks_compute_profile_name \
        else pks_compute_profile_name
    pks_ctx[PKS_PLANS_KEY] = '' if not pks_plans else pks_plans
    pks_ctx[PKS_CLUSTER_DOMAIN_KEY] = '' if not pks_cluster_domain \
        else pks_cluster_domain
    pks_ctx['nsxt'] = nsxt_info
    return pks_ctx


def construct_k8s_metadata_from_pks_cache(ovdc_id, org_name, pks_plans,
                                          pks_cluster_domain,
                                          k8s_provider):
    client = None
    try:
        ctr_prov_context = {}
        ctr_prov_context[K8S_PROVIDER_KEY] = k8s_provider
        if k8s_provider == K8sProvider.PKS:
            if not utils.is_pks_enabled():
                raise CseServerError('CSE is not configured to work with PKS.')

            client = vcd_utils.get_sys_admin_client()
            ovdc = vcd_utils.get_vdc(client=client, vdc_id=ovdc_id,
                                     is_admin_operation=True)
            pks_cache = utils.get_pks_cache()
            pvdc_id = vcd_utils.get_pvdc_id(ovdc)
            pvdc_info = pks_cache.get_pvdc_info(pvdc_id)
            if not pvdc_info:
                LOGGER.debug(f"pvdc '{pvdc_id}' is not backed "
                             f"by PKS-managed-vSphere resources")
                raise CseServerError(f"VDC '{ovdc.get_resource().get('name')}'"
                                     " is not eligible to provide resources"
                                     " for PKS clusters.")
            pks_account_info = pks_cache.get_pks_account_info(
                org_name, pvdc_info.vc)
            nsxt_info = pks_cache.get_nsxt_info(pvdc_info.vc)

            pks_compute_profile_name = \
                _construct_pks_compute_profile_name(ovdc_id)
            ctr_prov_context = construct_pks_context(
                pks_account_info=pks_account_info,
                pvdc_info=pvdc_info,
                nsxt_info=nsxt_info,
                pks_compute_profile_name=pks_compute_profile_name,
                pks_plans=pks_plans,
                pks_cluster_domain=pks_cluster_domain,
                credentials_required=True)
        return ctr_prov_context
    finally:
        if client:
            client.logout()


def _construct_pks_compute_profile_name(vdc_id):
    """Construct pks compute profile name.

    :param str vdc_id: UUID of the vdc in vcd

    :return: pks compute profile name

    :rtype: str
    """
    client = None
    try:
        client = vcd_utils.get_sys_admin_client()
        vdc = vcd_utils.get_vdc(client=client, vdc_id=vdc_id)
        return f"cp--{vdc_id}--{vdc.name}"
    finally:
        if client:
            client.logout()


def create_pks_compute_profile(pks_ctx,
                               tenant_auth_token,
                               is_jwt_token,
                               request_data):
    ovdc_id = request_data.get(RequestKey.OVDC_ID)
    org_name = request_data.get(RequestKey.ORG_NAME)
    ovdc_name = request_data.get(RequestKey.OVDC_NAME)
    # Compute profile creation
    pks_compute_profile_name = \
        _construct_pks_compute_profile_name(ovdc_id)
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

    pksbroker = PksBroker(pks_ctx, tenant_auth_token, is_jwt_token)
    try:
        pksbroker.create_compute_profile(**compute_profile_params)
    except PksServerError as ex:
        if ex.status == requests.codes.conflict:
            LOGGER.debug(f"Compute profile name {pks_compute_profile_name}"
                         f" already exists\n{str(ex)}")
        else:
            raise


def _remove_metadata_from_ovdc(ovdc, keys=[]):
    metadata = pyvcd_utils.metadata_to_dict(ovdc.get_all_metadata())
    for k in keys:
        if k in metadata:
            ovdc.remove_metadata(k, domain=MetadataDomain.SYSTEM)


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
