# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Utilities to manage CSE metadata on Ovdcs."""

from collections import namedtuple

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.utils as pyvcd_utils
from pyvcloud.vcd.vdc import VDC
import requests

from container_service_extension.common.constants.server_constants import K8S_PROVIDER_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import K8sProvider  # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_CLUSTER_DOMAIN_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_COMPUTE_PROFILE_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_PLANS_KEY  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey   # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.exception.exceptions as e
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.security.context.operation_context as ctx
from container_service_extension.server.pks.pks_cache import PksCache
from container_service_extension.server.pks.pksbroker import PksBroker


def get_ovdc_k8s_provider_metadata(sysadmin_client: vcd_client.Client,
                                   org_name=None, ovdc_name=None, ovdc_id=None,
                                   include_credentials=False,
                                   include_nsxt_info=False):
    """Get k8s provider metadata for an org VDC.

    :param sysadmin_client:
    :param org_name:
    :param ovdc_name:
    :param ovdc_id:
    :param include_credentials:
    :param include_nsxt_info:
    :return:  Dictionary with k8s provider metadata
    """
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    ovdc = vcd_utils.get_vdc(client=sysadmin_client, vdc_name=ovdc_name,
                             vdc_id=ovdc_id, org_name=org_name,
                             is_admin_operation=True)

    all_metadata = pyvcd_utils.metadata_to_dict(ovdc.get_all_metadata())
    k8s_provider = all_metadata.get(K8S_PROVIDER_KEY, K8sProvider.NONE)

    result = {
        K8S_PROVIDER_KEY: k8s_provider
    }

    if k8s_provider == K8sProvider.PKS:
        result.update({k: all_metadata[k] for k in PksCache.get_pks_keys()})  # noqa: E501
        result[PKS_PLANS_KEY] = result[PKS_PLANS_KEY].split(',')

        # Get the credentials from PksCache
        if include_credentials or include_nsxt_info:
            pks_cache = server_utils.get_pks_cache()
            pvdc_info = pks_cache.get_pvdc_info(
                vcd_utils.get_pvdc_id(ovdc))
            if include_credentials:
                # noqa: E501 TODO in case only ovdc_id is provided, we need a way to get org_name
                pks_info = pks_cache.get_pks_account_info(org_name,
                                                          pvdc_info.vc)
                result.update(pks_info.credentials._asdict())
            if include_nsxt_info:
                nsxt_info = pks_cache.get_nsxt_info(pvdc_info.vc)
                result['nsxt'] = nsxt_info

    return result


def get_all_ovdc_with_metadata():
    client = None
    try:
        client = vcd_utils.get_sys_admin_client(api_version=None)
        q = client.get_typed_query(
            vcd_client.ResourceType.ADMIN_ORG_VDC.value,
            query_result_format=vcd_client.QueryResultFormat.RECORDS,
            fields='metadata@SYSTEM:k8s_provider')
        ovdc_records = q.execute()
        return ovdc_records
    finally:
        if client is not None:
            client.logout()


def update_ovdc_k8s_provider_metadata(sysadmin_client: vcd_client.Client,
                                      ovdc_id,
                                      k8s_provider_data=None,
                                      k8s_provider=None):
    """Set the k8s provider metadata for given ovdc.

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param str ovdc_id:
    :param dict k8s_provider_data:  k8s provider context details
    :param K8sProvider k8s_provider:
    :return:
    """
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    ovdc = vcd_utils.get_vdc(sysadmin_client, vdc_id=ovdc_id)
    ovdc_name = ovdc.get_resource().get('name')
    metadata = {
        K8S_PROVIDER_KEY: k8s_provider or K8sProvider.NONE
    }

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
    return ovdc.set_multiple_metadata(metadata,
                                      vcd_client.MetadataDomain.SYSTEM,
                                      vcd_client.MetadataVisibility.PRIVATE)


def construct_pks_context(pks_account_info, pvdc_info=None, nsxt_info=None,
                          pks_compute_profile_name=None, pks_plans='',
                          pks_cluster_domain='',
                          credentials_required=False):
    """Construct PKS context dictionary.

    :param container_service_extension.server.pks.pks_cache.PksAccountInfo pks_account_info: pks connection details  # noqa: E501
    :param container_service_extension.server.pks.pks_cache.PvdcInfo pvdc_info:
        pvdc details including datacenter and cluster.
    :param dict nsxt_info:
    :param str pks_compute_profile_name: name of the compute profile
    :param str pks_plans: comma separated values for pks plans
    :param str pks_cluster_domain:
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


def construct_k8s_metadata_from_pks_cache(sysadmin_client: vcd_client.Client,
                                          ovdc_id, org_name, pks_plans,
                                          pks_cluster_domain,
                                          k8s_provider):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    ctr_prov_context = {
        K8S_PROVIDER_KEY: k8s_provider,
    }
    if k8s_provider == K8sProvider.PKS:
        if not server_utils.is_pks_enabled():
            raise e.CseServerError('CSE is not configured to work with PKS.')

        ovdc = vcd_utils.get_vdc(client=sysadmin_client, vdc_id=ovdc_id,
                                 is_admin_operation=True)
        pks_cache = server_utils.get_pks_cache()
        pvdc_id = vcd_utils.get_pvdc_id(ovdc)
        pvdc_info = pks_cache.get_pvdc_info(pvdc_id)
        if not pvdc_info:
            LOGGER.debug(f"pvdc '{pvdc_id}' is not backed "
                         f"by PKS-managed-vSphere resources")
            raise e.CseServerError(f"VDC '{ovdc.get_resource().get('name')}'"
                                   " is not eligible to provide resources"
                                   " for PKS clusters.")
        pks_account_info = pks_cache.get_pks_account_info(
            org_name, pvdc_info.vc)
        nsxt_info = pks_cache.get_nsxt_info(pvdc_info.vc)

        pks_compute_profile_name = _construct_pks_compute_profile_name(
            sysadmin_client, ovdc_id)
        ctr_prov_context = construct_pks_context(
            pks_account_info=pks_account_info,
            pvdc_info=pvdc_info,
            nsxt_info=nsxt_info,
            pks_compute_profile_name=pks_compute_profile_name,
            pks_plans=pks_plans,
            pks_cluster_domain=pks_cluster_domain,
            credentials_required=True)
    return ctr_prov_context


def _construct_pks_compute_profile_name(sysadmin_client: vcd_client.Client,
                                        vdc_id):
    """Construct pks compute profile name.

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param str vdc_id: UUID of the vdc in vcd

    :return: pks compute profile name

    :rtype: str
    """
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    vdc = vcd_utils.get_vdc(client=sysadmin_client, vdc_id=vdc_id)
    return f"cp--{vdc_id}--{vdc.name}"


def create_pks_compute_profile(request_data,
                               op_ctx: ctx.OperationContext,
                               pks_context):
    ovdc_id = request_data.get(RequestKey.OVDC_ID)
    org_name = request_data.get(RequestKey.ORG_NAME)
    ovdc_name = request_data.get(RequestKey.OVDC_NAME)
    # Compute profile creation
    pks_compute_profile_name = _construct_pks_compute_profile_name(
        op_ctx.sysadmin_client, ovdc_id)
    pks_compute_profile_description = f"{org_name}--{ovdc_name}--{ovdc_id}"
    pks_az_name = f"az-{ovdc_name}"
    ovdc_rp_name = f"{ovdc_name} ({ovdc_id})"

    compute_profile_params = PksComputeProfileParams(
        pks_compute_profile_name, pks_az_name,
        pks_compute_profile_description,
        pks_context.get('cpi'),
        pks_context.get('datacenter'),
        pks_context.get('cluster'),
        ovdc_rp_name).to_dict()

    LOGGER.debug(f"Creating PKS Compute Profile with name:"
                 f"{pks_compute_profile_name}")

    pksbroker = PksBroker(pks_context, op_ctx)
    try:
        pksbroker.create_compute_profile(**compute_profile_params)
    except e.PksServerError as err:
        if err.status == requests.codes.conflict:
            LOGGER.debug(f"Compute profile name {pks_compute_profile_name}"
                         f" already exists\n{str(err)}")
        else:
            raise


def _remove_metadata_from_ovdc(ovdc: VDC, keys=None):
    if keys is None:
        keys = []
    metadata = pyvcd_utils.metadata_to_dict(ovdc.get_all_metadata())
    for k in keys:
        if k in metadata:
            ovdc.remove_metadata(k, domain=vcd_client.MetadataDomain.SYSTEM)


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
