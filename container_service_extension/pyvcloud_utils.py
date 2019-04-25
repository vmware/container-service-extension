# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.utils import get_admin_href
from pyvcloud.vcd.vdc import VDC

from container_service_extension.utils import get_vcd_sys_admin_client

# Cache to keep ovdc_id to org_name mapping for vcd cse cluster list
OVDC_TO_ORG_MAP = {}


def get_org_name_of_ovdc(vdc_id):
    """Get org_name from vdc_id; additionally update OVDC_TO_ORG_MAP
        with key:vdc_id and value:org_name for new key-value pairs.

    :param vdc_id: unique ovdc id
    :return: org_name
    """
    if vdc_id in OVDC_TO_ORG_MAP:
        org_name = OVDC_TO_ORG_MAP.get(vdc_id)
    else:
        client = get_vcd_sys_admin_client()
        vdc_href = f"{client._uri}/vdc/{vdc_id}"
        vdc_resource = client.get_resource(get_admin_href(vdc_href))
        vdc_obj = VDC(client, resource=vdc_resource)
        link = find_link(vdc_obj.resource, RelationType.UP,
                         EntityType.ADMIN_ORG.value)
        org = Org(client, href=link.href)
        '''Add the entry to the map to be used next time the \
        same ovdc is requested'''
        OVDC_TO_ORG_MAP[vdc_id] = org.get_name()
        org_name = org.get_name()
    return org_name
