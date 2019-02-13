# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from vcd_cli.profiles import Profiles

from container_service_extension import utils
from container_service_extension.broker import DefaultBroker
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.pksbroker import PKSBroker


def get_new_broker(headers, request_body):

    profiles = Profiles.load()
    ovdc_name = profiles.get('vdc_in_use')
    org_name = profiles.get('org_in_use')
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
        return DefaultBroker(headers, request_body)
