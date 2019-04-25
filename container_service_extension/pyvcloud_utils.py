# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.utils import get_admin_href
from pyvcloud.vcd.vdc import VDC
from container_service_extension.utils import get_vcd_sys_admin_client

OVDC_TO_ORG_MAP = {}


def get_org_by_vdc_href(vdc_id, vdc_name):
    """ Get org_name from ovdc_id

    :param vdc_id:
    :param ovdc_to_org_map: contains mapping of vdc_name to org_name
    :param vdc_name:
    :return: org_name
    """
    if vdc_name in OVDC_TO_ORG_MAP:
        ret = OVDC_TO_ORG_MAP.get(vdc_name)
    else:
        client = get_vcd_sys_admin_client()
        vdc_href = str(client._uri) + '/vdc/' + str(vdc_id)
        resource = client.get_resource(get_admin_href(vdc_href))
        vdc_obj = VDC(client, resource=resource)
        link = find_link(vdc_obj.resource, RelationType.UP, \
                         EntityType.ADMIN_ORG.value)
        org = Org(client, href=link.href)
        # Add teh entry to the map to be used next time the same ovdc is requested
        OVDC_TO_ORG_MAP[vdc_name] = org.get_name()
        ret = org.get_name()
    return ret