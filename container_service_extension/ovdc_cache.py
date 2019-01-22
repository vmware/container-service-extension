from container_service_extension.utils import get_vdc
from container_service_extension.utils import get_org
from pyvcloud.vcd import utils


class PvdcCacheStub(object):

    def __init__(self):
        """ Constructor for pvdc cache. Initializes pvdc and pks cache.

            Always returns the canned data. This is a thrown away class
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
        """ Constructor of OvdcCache

        :param pyvcloud.vcd.client.Client client:he client that will be used
            to make REST calls to vCD.
        """
        self.client = client
        self.pvdc_cache = PvdcCacheStub()

    def get_ovdc_metadata(self, ovdc_name, org_name=None):
        """Gets ovdc metadata for given ovdc name

        :param str ovdc_name:
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @client.

        :return: metadata of the ovdc

        :rtype: dict

        :raises EntityNotFoundException: if the ovdc could not be found.
        """
        # Get pvdc and pks information from pvdc cache
        ovdc = get_vdc(self.client, ovdc_name, org_name=org_name, is_admin_operation=True)
        pvdc_element = ovdc.resource.ProviderVdcReference
        pvdc_id = pvdc_element.get('id')
        pvdc_info = self.pvdc_cache.get_pvdc_info(pvdc_id)
        pks_info = self.pvdc_cache.get_pks_info(ovdc.name, pvdc_info['vc'])

        # Get ovdc metadata from vcd; copy the credentials from pvdc cache
        metadata = utils.metadata_to_dict(ovdc.get_all_metadata())
        metadata['rp_path'] = metadata['rp_path'].split(',')
        metadata['plans'] = metadata['plans'].split(',')
        pks_connection_details = dict()
        pks_connection_details['host'] = metadata.pop('host')
        pks_connection_details['port'] = metadata.pop('port')
        pks_connection_details['uaac_port'] = metadata.pop('uaac_port')
        pks_connection_details['username'] = pks_info['username']
        pks_connection_details['secret'] = pks_info['secret']
        metadata['pks_connection_details'] = pks_connection_details
        return metadata

    def set_ovdc_meta_data(self, ovdc_name, org_name=None, back_end='', plans=''):
        """sets the backing pvdc and pks information of a given oVdc.

        :param str ovdc_name: name of the ovdc
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @client.
        :param str back_end: name of back end for which this metadata is required.
        :param str plans: pks plan for deployment
        """

        # Get resource pool
        org = get_org(self.client, org_name=org_name)
        ovdc = get_vdc(self.client, ovdc_name, org=org, is_admin_operation=True)
        ovdc_id = ovdc.resource.get('id').split(':')[-1]
        resource_pool = f"{ovdc.name} ({ovdc_id})"

        # Get pvdc and pks information from pvdc cache
        org_name = org.resource.get('name')
        pvdc_element = ovdc.resource.ProviderVdcReference
        pvdc_id = pvdc_element.get('id')
        pvdc_info = self.pvdc_cache.get_pvdc_info(pvdc_id)
        pks_info = self.pvdc_cache.get_pks_info(org_name, pvdc_info['vc'])

        # construct ovdc metadata
        meta_data = dict()
        meta_data['name'] = pvdc_info['name']
        meta_data['vc'] = pvdc_info['vc']
        meta_data['rp_path'] = ','.join(f'{rp_path}/{resource_pool}' for rp_path in pvdc_info['rp_path'])
        meta_data['host'] = pks_info['host']
        meta_data['port'] = pks_info['port']
        meta_data['uaac_port'] = pks_info['uaac_port']
        meta_data['plans'] = plans
        meta_data['pks_compute_profile_name'] = f"{org_name}-{ovdc_name}-{ovdc_id}"

        # set ovdc metadata into Vcd
        return ovdc.set_multiple_metadata(meta_data)
