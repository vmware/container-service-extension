# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple
from enum import Enum
from enum import unique
from http import HTTPStatus

from pyvcloud.vcd import utils
from pyvcloud.vcd.client import ApiVersion
from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.vdc import VDC


from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pks_cache import PKS_COMPUTE_PROFILE
from container_service_extension.pks_cache import PKS_PLANS
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pksclient.rest import ApiException
from container_service_extension.utils import get_org
from container_service_extension.utils import get_pks_cache
from container_service_extension.utils import get_vdc


# TODO(Constants) Refer the TODO(Constants) in broker_manager.py
@unique
class CtrProvType(Enum):
    VCD = 'vcd'
    PKS = 'pks'


CONTAINER_PROVIDER = 'container_provider'


class OvdcCache(object):

    def __init__(self, client):
        """Construct the cache for ovdc.

        :param pyvcloud.vcd.client.Client client:the client that will be used
            to make REST calls to vCD.
        """
        self.client = client
        self.pks_cache = get_pks_cache()

    @staticmethod
    def construct_pks_context(pks_info, pvdc_info=None,
                              pks_compute_profile_name=None, pks_plans='',
                              credentials_required=False):
        """Construct PKS context dictionary.

        :param container_service_extension.pks_cache.PksInfo pks_info:
        pks connection details
        :param container_service_extension.pks_cache.PvdcInfo pvdc_info:
        pvdc details including datacenter and cluster.
        :param str pks_compute_profile_name: name of the compute profile
        :param str pks_plans: comma separated values for pks plans
        :param bool credentials_required: determines if credentials have to
        be part of the resultant dictionary

        :return: dict of pks context details

        :rtype: dict
        """
        pks_ctx = pks_info._asdict()
        credentials = pks_ctx.pop('credentials')
        if credentials_required is True:
            pks_ctx.update(credentials._asdict())
        if pvdc_info is not None:
            pks_ctx.update(pvdc_info._asdict())
        pks_ctx[PKS_COMPUTE_PROFILE] = '' if pks_compute_profile_name is None \
            else pks_compute_profile_name
        pks_ctx[PKS_PLANS] = '' if pks_plans is None else pks_plans
        return pks_ctx

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
        # Get pvdc and pks information from oVdc metadata
        if ovdc_id is None:
            ovdc = get_vdc(self.client, ovdc_name, org_name=org_name,
                           is_admin_operation=True)
        else:
            # TODO() - Implement this in pyvcloud
            ovdc = self._get_vdc_by_id(ovdc_id)

        all_metadata = utils.metadata_to_dict(ovdc.get_all_metadata())

        if CONTAINER_PROVIDER not in all_metadata:
            container_provider = None
        else:
            container_provider = \
                all_metadata[CONTAINER_PROVIDER]

        ctr_prov_details = {}
        if container_provider == CtrProvType.PKS.value:
            # Filter out container provider metadata into a dict
            metadata = {metadata_key: all_metadata[metadata_key]
                        for metadata_key in self.pks_cache.get_pks_keys()}

            # Get the credentials from PksCache
            pvdc_id = self._get_pvdc_id(ovdc)
            pvdc_info = self.pks_cache.get_pvdc_info(pvdc_id)
            metadata[PKS_PLANS] = metadata[PKS_PLANS].split(',')
            if credentials_required:
                pks_info = self.pks_cache.get_pks_account_details(
                    org_name, pvdc_info.vc)
                metadata.update(pks_info.credentials._asdict())
            ctr_prov_details.update(metadata)

        ctr_prov_details[CONTAINER_PROVIDER] = container_provider
        return ctr_prov_details

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

        if container_provider != CtrProvType.PKS.value:
            LOGGER.debug(f'Remove metadata for ovdc:{ovdc_name}')
            self._remove_metadata(ovdc, self.pks_cache.get_pks_keys())
            metadata[CONTAINER_PROVIDER] = container_provider or ''
        else:

            # Get pvdc and pks information from pks cache
            org_name = org.resource.get('name')
            pvdc_id = self._get_pvdc_id(ovdc)
            pvdc_info = self.pks_cache.get_pvdc_info(pvdc_id)
            pks_info = self.pks_cache.get_pks_account_details(
                org_name, pvdc_info.vc)
            metadata[CONTAINER_PROVIDER] = container_provider

            # Compute profile creation
            pks_compute_profile_name = f"cp-{ovdc_id}"
            pks_compute_profile_description = f"{org_name}-{ovdc_name}" \
                f"-{ovdc_id}"
            pks_az_name = f"az-{ovdc_id}"
            ovdc_rp_name = f"{ovdc.name} ({ovdc_id})"

            pks_ctx = self.construct_pks_context(pks_info, pvdc_info,
                                                 pks_compute_profile_name,
                                                 pks_plans,
                                                 credentials_required=True)
            compute_profile_params = PksComputeProfileParams(
                pks_compute_profile_name, pks_az_name,
                pks_compute_profile_description,
                pks_ctx.get('cpi'),
                pks_ctx.get('datacenter'),
                pks_ctx.get('cluster'),
                ovdc_rp_name).as_dict()

            self._create_compute_profile(pks_ctx, compute_profile_params)
            pks_ctx.pop('username')
            pks_ctx.pop('secret')
            metadata.update(pks_ctx)

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

    def _get_pvdc_id(self, ovdc):
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

    def _create_compute_profile(self, pks_ctx, compute_profile_params):
        try:
            pksbroker = PKSBroker(None, None, pks_ctx)
            pksbroker.create_compute_profile(**compute_profile_params)
        except ApiException as ex:
            # if profile already exists,continue metadata update
            # Any other reason -> re-raise the exception
            if ex.status == HTTPStatus.CONFLICT.value:
                LOGGER.debug(f'{str(ex)}')
            else:
                raise ex


class PksComputeProfileParams(namedtuple("PksComputeProfileParams",
                                         'cp_name, az_name, description,'
                                         'cpi,datacenter_name, '
                                         'cluster_name, ovdc_rp_name')):
    """Immutable class representing PKS ComputeProfile Parameters ."""

    def __str__(self):
        return f"class:{PksComputeProfileParams.__name__}," \
            f" cp_name:{self.cp_name}, az_name:{self.az_name}, " \
            f" description:{self.description}, cpi:{self.cpi}, " \
            f" datacenter_name:{self.datacenter_name}, " \
            f" cluster_name:{self.cluster_name}, " \
            f" ovdc_rp_name:{self.ovdc_rp_name}"

    def as_dict(self):
        return dict(self._asdict())




