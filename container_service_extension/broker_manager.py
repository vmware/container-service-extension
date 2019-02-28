# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension import utils
from container_service_extension.broker import DefaultBroker
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.utils import get_pks_cache

from enum import Enum, unique

@unique
class Operation(Enum):
    CREATE_CLUSTER = 'create cluster'
    DELETE_CLUSTER = 'delete clsuter'
    GET_CLUSTER = 'get cluster info'
    LIST_CLUSTERS = 'list clusters'
    RESIZE_CLUSTER = 'resize cluster'


class Broker_manager(object):
    def __init__(self, headers, body):
        self.headers = headers
        self.body = body
        self.pks_cache = get_pks_cache()

    def invoke(self, op, on_the_fly_request_body=None):

        request_body = self.body
        if on_the_fly_request_body:
            request_body = on_the_fly_request_body

        if op == Operation.GET_CLUSTER:
            ovdc_name = request_body.get('vdc') if request_body else None
            cluster_name = request_body['cluster_name']
            if ovdc_name:
                broker = self.get_new_broker(request_body)
                broker.get_cluster_info(cluster_name)
            else:
                vcd_broker = DefaultBroker(self.headers, request_body)
                result = vcd_broker.get_cluster_info(cluster_name)
                if len(result['body']) > 0:
                    return result
                session = vcd_broker.get_tenant_client_session()
                pks_acc_list = self.pks_cache.\
                    get_all_pks_accounts_for_org(org_name=session.get('org'))
                for pks_account in pks_acc_list:
                    return








    def get_new_broker(self, on_the_fly_request_body=None):

        request_body = self.body
        if on_the_fly_request_body:
            request_body = on_the_fly_request_body

        config = utils.get_server_runtime_config()
        tenant_client, session = utils.connect_vcd_user_via_token(
            vcd_uri=config['vcd']['host'],
            headers=self.headers,
            verify_ssl_certs=config['vcd']['verify'])
        ovdc_name = request_body.get('vdc') if request_body else None
        org_name = session.get('org')
        LOGGER.debug(f"org_name={org_name};vdc_name=\'{ovdc_name}\'")

        """
        Get the ovdc metadata from the logged-in org and ovdc.
        Create the right broker based on value of 'container_provider'.
        Fall back to DefaultBroker for missing ovdc or org.
        """
        if ovdc_name and org_name:
            admin_client = utils.get_vcd_sys_admin_client()
            ovdc_cache = OvdcCache(admin_client)
            metadata = ovdc_cache.get_ovdc_container_provider_metadata(
                ovdc_name=ovdc_name, org_name=org_name,
                credentials_required=True)
            LOGGER.debug(
                f"ovdc metadata for {ovdc_name}-{org_name}=>{metadata}")
            if metadata.get('container_provider') == 'pks':
                return PKSBroker(self.headers, request_body,
                                 ovdc_cache=metadata)
            else:
                return DefaultBroker(self.headers, request_body)
        else:
            # TODO() - This call should be based on a boolean flag
            # Specify flag in config file whether to have default
            # handling is required for missing ovdc or org.
            return DefaultBroker(self.headers, request_body)

b = Broker_manager(None, None)
b.invoke(Operation.GET_CLUSTER)
