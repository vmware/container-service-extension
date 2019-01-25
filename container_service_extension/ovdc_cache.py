# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils

from container_service_extension.utils import get_org
from container_service_extension.utils import get_vdc


class PvdcCacheStub(object):

    def __init__(self):
        """Construct, initialize pvdc and pks cache.

        Always returns the scanned data. This is a thrown away class
        after actual PvdcCache is implemented

        """
        self.pvdc_cache = dict()
        self.pks_cache = dict()
        self._initialize_pvdc_cache()
        self._initialize_pks_cache()

    def get_pvdc_info(self, pvdc_id):
        return self.pvdc_cache['pvdc_id']

    def get_pks_info(self, org_name, vc_name):
        return self.pks_cache['org1']['vc1']

    def _initialize_pvdc_cache(self):
        self.pvdc_cache['pvdc_id'] = dict()
        self.pvdc_cache['pvdc_id']['name'] = 'pvdc1'
        self.pvdc_cache['pvdc_id']['vc'] = 'vc1'
        self.pvdc_cache['pvdc_id']['rp_path'] = ['dc1/c1/rp1', 'dc1/c1/rp2']

    def _initialize_pks_cache(self):
        self.pks1 = dict()
        self.pks1['host'] = '10.161.148.112'
        self.pks1['port'] = '9021'
        self.pks1['username'] = 'cokeSvcAccount'
        self.pks1['secret'] = 'GhujkdfRl2dEvj1_hH9wEQxDUkxO1Lcjm3'
        self.pks1['uaac_port'] = '8443'
        self.pks_cache['org1'] = dict()
        self.pks_cache['org1']['vc1'] = self.pks1


class OvdcCache(object):

    def __init__(self, client):
        """Construct the cache for ovdc.

        :param pyvcloud.vcd.client.Client client:the client that will be used
            to make REST calls to vCD.
        """
        self.client = client
        self.pvdc_cache = PvdcCacheStub()

    def get_ovdc_backend_metadata(self, ovdc_name, org_name=None):
        """Get ovdc metadata pertaining to the backend(vcd/pks).

        The backend that this ovdc is dedicated to deploy K8 clusters on.

        :param str ovdc_name: name of the ovdc
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @client.

        :return: metadata of the ovdc

        :rtype: dict

        :raises EntityNotFoundException: if the ovdc could not be found.
        """
        # Get pvdc and pks information from pvdc cache
        ovdc = get_vdc(self.client, ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        metadata = utils.metadata_to_dict(ovdc.get_all_metadata())
        metadata['backend'] = metadata.get('backend', None)

        if metadata['backend'] is None or metadata['backend'].lower() == 'vcd':
            return {'backend': metadata['backend']}

        pvdc_element = ovdc.resource.ProviderVdcReference
        pvdc_id = pvdc_element.get('id')
        pvdc_info = self.pvdc_cache.get_pvdc_info(pvdc_id)
        pks_info = self.pvdc_cache.get_pks_info(ovdc.name, pvdc_info['vc'])

        # Get ovdc metadata from vcd; copy the credentials from pvdc cache
        metadata['rp_path'] = metadata['rp_path'].split(',')
        metadata['pks_plans'] = metadata['pks_plans'].split(',')
        metadata['username'] = pks_info['username']
        metadata['secret'] = pks_info['secret']
        return metadata

    def set_ovdc_backend_meta_data(self, ovdc_name, org_name=None,
                                   backend=None,
                                   pks_plans=''):
        """Set the backing pvdc and pks information of a given oVdc.

        :param str ovdc_name: name of the ovdc
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @client.
        :param str backend: name of back end for which this metadata is
        required.
        :param str pks_plans: pks plan for deployment. If backend is vcd
            or None, plans are not used and not relevant to the context.
        """
        metadata = dict()
        org = get_org(self.client, org_name=org_name)
        ovdc = get_vdc(self.client, ovdc_name, org=org,
                       is_admin_operation=True)
        if backend is None:
            self._remove_metadata(ovdc,
                                  keys=['name', 'vc', 'rp_path', 'host',
                                        'port',
                                        'uaac_port', 'pks_plans',
                                        'pks_compute_profile_name'])
            metadata['backend'] = ''
        else:
            # Get resource pool
            ovdc_id = ovdc.resource.get('id').split(':')[-1]
            resource_pool = f"{ovdc.name} ({ovdc_id})"

            # Get pvdc and pks information from pvdc cache
            org_name = org.resource.get('name')
            pvdc_element = ovdc.resource.ProviderVdcReference
            pvdc_id = pvdc_element.get('id')
            pvdc_info = self.pvdc_cache.get_pvdc_info(pvdc_id)
            pks_info = self.pvdc_cache.get_pks_info(org_name, pvdc_info['vc'])

            # construct ovdc metadata

            metadata['name'] = pvdc_info['name']
            metadata['vc'] = pvdc_info['vc']
            metadata['rp_path'] = ','.join(
                f'{rp_path}/{resource_pool}' for rp_path in
                pvdc_info['rp_path'])
            metadata['host'] = pks_info['host']
            metadata['port'] = pks_info['port']
            metadata['uaac_port'] = pks_info['uaac_port']
            metadata['pks_plans'] = pks_plans
            metadata['backend'] = backend
            pks_compute_profile_name = f"{org_name}-{ovdc_name}-{ovdc_id}"
            metadata['pks_compute_profile_name'] = pks_compute_profile_name

        # set ovdc metadata into Vcd
        ovdc.set_multiple_metadata(metadata)

    def _remove_metadata(self, ovdc, keys=[]):
        metadata = utils.metadata_to_dict(ovdc.get_all_metadata())
        for k in keys:
            if k in metadata:
                ovdc.remove_metadata(k)
