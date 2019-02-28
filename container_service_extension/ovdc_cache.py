# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils
from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.vdc import VDC


from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.utils import get_org
from container_service_extension.utils import get_pks_cache
from container_service_extension.utils import get_vdc


class OvdcCache(object):

    __ovdc_metadata_keys = ['name', 'datacenter', 'cluster', 'vc', 'cpi',
                            'host', 'port',
                            'uaac_port', 'proxy', 'pks_plans',
                            'pks_compute_profile_name', 'container_provider']

    def __init__(self, client):
        """Construct the cache for ovdc.

        :param pyvcloud.vcd.client.Client client:the client that will be used
            to make REST calls to vCD.
        """
        self.client = client
        self.pks_cache = get_pks_cache()

    def get_ovdc_container_provider_metadata(self, ovdc_name,
                                             ovdc_id=None, org_name=None,
                                             credentials_required=False):
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
        # Get pvdc and pks information from pvdc cache
        if ovdc_id is None:
            ovdc = get_vdc(self.client, ovdc_name, org_name=org_name,
                           is_admin_operation=True)
        else:
            # TODO() - Implement this in pyvcloud
            ovdc = self._get_vdc_by_id(ovdc_id)

        all_metadata = utils.metadata_to_dict(ovdc.get_all_metadata())

        if 'container_provider' not in all_metadata:
            container_provider = None
        else:
            container_provider = \
                all_metadata['container_provider']

        if container_provider == 'pks':
            # Filter out container provider metadata into a dict
            metadata = {metadata_key: all_metadata[metadata_key]
                        for metadata_key in self.__ovdc_metadata_keys}

            # copy the credentials from pvdc cache
            pvdc_element = ovdc.resource.ProviderVdcReference
            pvdc_id = pvdc_element.get('id')
            pvdc_info = self.pks_cache.get_pvdc_info(pvdc_id)
            metadata['pks_plans'] = metadata['pks_plans'].split(',')
            if credentials_required:
                pks_info = self.pks_cache.get_pks_account_details(
                    org_name, pvdc_info.vc)
                metadata['username'] = pks_info.uaac.username
                metadata['secret'] = pks_info.uaac.secret
        else:
            metadata = {'container_provider': container_provider}

        return metadata

    def set_ovdc_container_provider_metadata(self, ovdc_name, ovdc_id=None,
                                             org_name=None,
                                             container_provider=None,
                                             pks_plans=''):
        """Set the container provider metadata of given ovdc.

        :param str ovdc_name: name of the ovdc
        :param str ovdc_id: unique id of the ovdc
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @client.
        :param str container_provider: name of container provider for which
            the ovdc is being enabled to deploy k8 clusters on.
        :param str pks_plans: PKS plans for deployment. If container provider
            is vCD or None, pks_plans are not applicable.
        """
        metadata = dict()
        org = get_org(self.client, org_name=org_name)
        if ovdc_id is None:
            ovdc = get_vdc(self.client, ovdc_name, org=org,
                           is_admin_operation=True)
            ovdc_id = utils.extract_id(ovdc.resource.get('id'))
        else:
            ovdc = self._get_vdc_by_id(ovdc_id)

        if container_provider != 'pks':
            LOGGER.debug(f'Remove metadata for ovdc:{ovdc_name}')
            self._remove_metadata(ovdc, self.__ovdc_metadata_keys)
            metadata['container_provider'] = container_provider or ''
        else:
            # Get pvdc and pks information from pvdc cache
            org_name = org.resource.get('name')
            pvdc_element = ovdc.resource.ProviderVdcReference
            pvdc_id = pvdc_element.get('id')
            # To support <= VCD 9.1 where no 'id' is present in pvdc
            # element, it has to be extracted from href. Once VCD 9.1 support
            # is discontinued, this code is not required.
            if pvdc_id is None:
                pvdc_href = pvdc_element.get('href')
                pvdc_id = pvdc_href.split("/")[-1]

            pvdc_info = self.pks_cache.get_pvdc_info(pvdc_id)
            pks_info = self.pks_cache.get_pks_account_details(
                org_name, pvdc_info.vc)

            # construct ovdc metadata
            metadata['name'] = pvdc_info.name
            metadata['vc'] = pvdc_info.vc
            metadata['datacenter'] = pvdc_info.datacenter
            metadata['cluster'] = pvdc_info.cluster
            metadata['cpi'] = pvdc_info.cpi
            metadata['host'] = pks_info.host
            metadata['port'] = pks_info.port
            if hasattr(pks_info, 'proxy') and pks_info.proxy is not None:
                metadata['proxy'] = pks_info.proxy
            else:
                metadata['proxy'] = ''
            metadata['uaac_port'] = pks_info.uaac.port
            metadata['pks_plans'] = pks_plans or ''
            metadata['container_provider'] = container_provider
            pks_compute_profile_name = f"{org_name}-{ovdc_name}-{ovdc_id}"
            metadata['pks_compute_profile_name'] = pks_compute_profile_name

        # set ovdc metadata into Vcd
        LOGGER.debug(f"Setting below metadata on ovdc {ovdc_name}:{metadata}")
        return ovdc.set_multiple_metadata(metadata, MetadataDomain.SYSTEM,
                                          MetadataVisibility.PRIVATE)

    def _remove_metadata(self, ovdc, keys=[]):
        metadata = utils.metadata_to_dict(ovdc.get_all_metadata())
        for k in keys:
            if k in metadata:
                ovdc.remove_metadata(k, domain=MetadataDomain.SYSTEM)

    def _get_vdc_by_id(self, vdc_id):
        LOGGER.debug(f"Getting vdc by id:{vdc_id}")
        admin_href = self.client.get_admin().get('href')
        ovdc_href = f'{admin_href}vdc/{vdc_id}'
        resource = self.client.get_resource(ovdc_href)
        return VDC(self.client, resource=resource)
