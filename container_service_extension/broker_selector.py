# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension import utils
from container_service_extension.broker import DefaultBroker
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pksbroker import PKSBroker


def get_new_broker(headers, request_body):

    config = utils.get_server_runtime_config()
    tenant_client, session = utils.connect_vcd_user_via_token(
        vcd_uri=config['vcd']['host'],
        headers=headers,
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
            ovdc_name=ovdc_name, org_name=org_name)
        LOGGER.debug(f"ovdc metadata for {ovdc_name}-{org_name}=>{metadata}")
        if metadata.get('container_provider') == 'pks':
            return PKSBroker(headers, request_body,
                             ovdc_cache=ovdc_cache)
        else:
            return DefaultBroker(headers, request_body)
    else:
        # TODO() - This call should be based on a boolean flag
        # Specify flag in config file whether to have default
        # handling is required for missing ovdc or org.
        return DefaultBroker(headers, request_body)
