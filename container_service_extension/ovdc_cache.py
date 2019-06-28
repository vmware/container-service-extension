# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils
from pyvcloud.vcd.client import ApiVersion
from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pks_cache import PKS_CLUSTER_DOMAIN_KEY
from container_service_extension.pks_cache import PKS_COMPUTE_PROFILE_KEY
from container_service_extension.pks_cache import PKS_PLANS_KEY
from container_service_extension.pks_cache import PksCache
from container_service_extension.pyvcloud_utils import get_vdc_by_id
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProviders
from container_service_extension.utils import get_org
from container_service_extension.utils import get_pks_cache
from container_service_extension.utils import get_vdc


class OvdcCache(object):

    def __init__(self, client):
        """Construct the cache for ovdc.

        :param pyvcloud.vcd.client.Client client:the client that will be used
            to make REST calls to vCD.
        """
        self.client = client
        self.pks_cache = get_pks_cache()

    @staticmethod
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
        ovdc = self.get_ovdc(ovdc_name, ovdc_id, org_name)

        all_metadata = utils.metadata_to_dict(ovdc.get_all_metadata())

        if K8S_PROVIDER_KEY not in all_metadata:
            container_provider = K8sProviders.NONE
        else:
            container_provider = all_metadata[K8S_PROVIDER_KEY]

        ctr_prov_details = {}
        if container_provider == K8sProviders.PKS:
            # Filter out container provider metadata into a dict
            ctr_prov_details = {
                metadata_key:
                    all_metadata[metadata_key]
                    for metadata_key in PksCache.get_pks_keys()
            }

            # Get the credentials from PksCache
            pvdc_id = self.get_pvdc_id(ovdc)
            pvdc_info = self.pks_cache.get_pvdc_info(pvdc_id)
            ctr_prov_details[PKS_PLANS_KEY] = \
                ctr_prov_details[PKS_PLANS_KEY].split(',')
            if credentials_required:
                pks_info = self.pks_cache.get_pks_account_info(
                    org_name, pvdc_info.vc)
                ctr_prov_details.update(pks_info.credentials._asdict())
            if nsxt_info_required:
                nsxt_info = self.pks_cache.get_nsxt_info(pvdc_info.vc)
                ctr_prov_details['nsxt'] = nsxt_info

        ctr_prov_details[K8S_PROVIDER_KEY] = container_provider

        return ctr_prov_details

    def set_ovdc_container_provider_metadata(self,
                                             ovdc,
                                             container_prov_data=None,
                                             container_provider=None):
        """Set the container provider metadata of given ovdc.

        :param resource ovdc: vdc resource
        :param dict container_prov_data: container provider context details
        :param str container_provider: name of container provider for which
            the ovdc is being enabled to deploy k8 clusters on.
        """
        ovdc_name = ovdc.resource.get('name')
        metadata = {}
        if container_provider != K8sProviders.PKS:
            LOGGER.debug(f"Remove existing metadata for ovdc:{ovdc_name}")
            self._remove_metadata(ovdc, PksCache.get_pks_keys())
            metadata[K8S_PROVIDER_KEY] = container_provider or \
                K8sProviders.NONE
            LOGGER.debug(f"Updated metadata for {container_provider}:"
                         f"{metadata}")
        else:
            container_prov_data.pop('username')
            container_prov_data.pop('secret')
            container_prov_data.pop('nsxt')
            metadata[K8S_PROVIDER_KEY] = container_provider
            metadata.update(container_prov_data)

        # set ovdc metadata into Vcd
        LOGGER.debug(f"On ovdc:{ovdc_name}, setting metadata:{metadata}")
        return ovdc.set_multiple_metadata(metadata, MetadataDomain.SYSTEM,
                                          MetadataVisibility.PRIVATE)

    def _remove_metadata(self, ovdc, keys=[]):
        metadata = utils.metadata_to_dict(ovdc.get_all_metadata())
        for k in keys:
            if k in metadata:
                ovdc.remove_metadata(k, domain=MetadataDomain.SYSTEM)

    def get_ovdc(self, ovdc_name=None, ovdc_id=None, org_name=None):
        if ovdc_id is None:
            org = get_org(self.client, org_name=org_name)
            return get_vdc(self.client, ovdc_name, org=org,
                           is_admin_operation=True)
        else:
            return get_vdc_by_id(self.client, ovdc_id)

    def get_pvdc_id(self, ovdc):
        pvdc_element = ovdc.resource.ProviderVdcReference
        # To support <= VCD 9.1 where no 'id' is present in pvdc
        # element, it has to be extracted from href. Once VCD 9.1 support
        # is discontinued, this code is not required.
        if float(self.client.get_api_version()) < \
                float(ApiVersion.VERSION_31.value):
            pvdc_href = pvdc_element.get('href')
            return pvdc_href.split("/")[-1]
        else:
            pvdc_id = pvdc_element.get('id')
            return utils.extract_id(pvdc_id)

