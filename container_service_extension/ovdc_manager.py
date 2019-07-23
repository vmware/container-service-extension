# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.utils import metadata_to_dict
import requests

from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pks_cache import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.pks_cache import PKS_COMPUTE_PROFILE_KEY
from container_service_extension.pks_cache import PKS_PLANS_KEY
from container_service_extension.pks_cache import PksCache
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pyvcloud_utils import get_pvdc_id
from container_service_extension.pyvcloud_utils import get_sys_admin_client
from container_service_extension.pyvcloud_utils import get_vdc
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import RequestKey
from container_service_extension.utils import get_pks_cache
from container_service_extension.utils import is_pks_enabled


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


def construct_ctr_prov_ctx_from_ovdc_metadata(ovdc_name, org_name):
    ctr_prov_ctx = OvdcManager().get_ovdc_container_provider_metadata(
        ovdc_name=ovdc_name, org_name=org_name,
        credentials_required=True, nsxt_info_required=True)
    return ctr_prov_ctx


def construct_ctr_prov_ctx_from_pks_cache(ovdc_id, org_name, pks_plans,
                                          pks_cluster_domain,
                                          container_provider):
    client = None
    try:
        ctr_prov_context = {}
        ctr_prov_context[K8S_PROVIDER_KEY] = container_provider
        if container_provider == K8sProvider.PKS:
            if not is_pks_enabled():
                raise CseServerError('CSE is not configured to work with PKS.')

            client = get_sys_admin_client()
            ovdc = get_vdc(client=client, vdc_id=ovdc_id,
                           is_admin_operation=True)
            pks_cache = get_pks_cache()
            pvdc_id = get_pvdc_id(ovdc)
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
        client = get_sys_admin_client()
        vdc = get_vdc(client=client, vdc_id=vdc_id)
        return f"cp--{vdc_id}--{vdc.name}"
    finally:
        if client:
            client.logout()


def create_pks_compute_profile(pks_ctx, tenant_auth_token, req_spec):
    ovdc_id = req_spec.get(RequestKey.OVDC_ID)
    org_name = req_spec.get(RequestKey.ORG_NAME)
    ovdc_name = req_spec.get(RequestKey.OVDC_NAME)
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

    pksbroker = PKSBroker(tenant_auth_token, req_spec, pks_ctx)
    try:
        pksbroker.create_compute_profile(**compute_profile_params)
    except PksServerError as ex:
        if ex.status == requests.codes.conflict:
            LOGGER.debug(f"Compute profile name {pks_compute_profile_name}"
                         f" already exists\n{str(ex)}")
        else:
            raise


class OvdcManager(object):
    def get_ovdc_container_provider_metadata(self, ovdc_name=None,
                                             ovdc_id=None, org_name=None,
                                             credentials_required=False,
                                             nsxt_info_required=False):
        """Get metadata of given ovdc, pertaining to the container provider.

        :param str ovdc_name: name of the ovdc
        :param str ovdc_id: UUID of ovdc
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @client.
        :param bool credentials_required: Decides if output metadata
        should include credentials or not.

        :return: metadata of the ovdc

        :rtype: dict

        :raises EntityNotFoundException: if the ovdc could not be found.
        """
        # Get pvdc and pks information from oVdc metadata
        client = None
        try:
            client = get_sys_admin_client()
            ovdc = get_vdc(client=client, vdc_name=ovdc_name,
                           vdc_id=ovdc_id, org_name=org_name,
                           is_admin_operation=True)

            all_metadata = metadata_to_dict(ovdc.get_all_metadata())

            if K8S_PROVIDER_KEY not in all_metadata:
                container_provider = K8sProvider.NONE
            else:
                container_provider = all_metadata[K8S_PROVIDER_KEY]

            ctr_prov_details = {}
            if container_provider == K8sProvider.PKS:
                # Filter out container provider metadata into a dict
                ctr_prov_details = {
                    metadata_key:
                        all_metadata[metadata_key]
                        for metadata_key in PksCache.get_pks_keys()
                }

                # Get the credentials from PksCache
                pvdc_id = get_pvdc_id(ovdc)
                pks_cache = get_pks_cache()
                pvdc_info = pks_cache.get_pvdc_info(pvdc_id)
                ctr_prov_details[PKS_PLANS_KEY] = \
                    ctr_prov_details[PKS_PLANS_KEY].split(',')
                if credentials_required:
                    pks_info = pks_cache.get_pks_account_info(
                        org_name, pvdc_info.vc)
                    ctr_prov_details.update(pks_info.credentials._asdict())
                if nsxt_info_required:
                    nsxt_info = pks_cache.get_nsxt_info(pvdc_info.vc)
                    ctr_prov_details['nsxt'] = nsxt_info

            ctr_prov_details[K8S_PROVIDER_KEY] = container_provider

            return ctr_prov_details
        finally:
            if client:
                client.logout()

    def set_ovdc_container_provider_metadata(self,
                                             ovdc_id,
                                             container_prov_data=None,
                                             container_provider=None):
        """Set the container provider metadata of given ovdc.

        :param resource ovdc: vdc resource
        :param dict container_prov_data: container provider context details
        :param str container_provider: name of container provider for which
            the ovdc is being enabled to deploy k8 clusters on.
        """
        client = None
        try:
            client = get_sys_admin_client()
            ovdc = get_vdc(client, vdc_id=ovdc_id)
            ovdc_name = ovdc.get_resource().get('name')

            metadata = {}
            metadata[K8S_PROVIDER_KEY] = container_provider or \
                K8sProvider.NONE

            if container_provider != K8sProvider.PKS:
                LOGGER.debug(f"Remove existing metadata for ovdc:{ovdc_name}")
                self._remove_metadata_from_ovdc(ovdc, PksCache.get_pks_keys())

                LOGGER.debug(f"Updated metadata for {container_provider}:"
                             f"{metadata}")
            else:
                container_prov_data.pop('username')
                container_prov_data.pop('secret')
                container_prov_data.pop('nsxt')
                metadata.update(container_prov_data)

            # set ovdc metadata into Vcd
            LOGGER.debug(f"On ovdc:{ovdc_name}, setting metadata:{metadata}")
            return ovdc.set_multiple_metadata(metadata, MetadataDomain.SYSTEM,
                                              MetadataVisibility.PRIVATE)
        finally:
            if client:
                client.logout()

    def _remove_metadata_from_ovdc(self, ovdc, keys=[]):
        metadata = metadata_to_dict(ovdc.get_all_metadata())
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
