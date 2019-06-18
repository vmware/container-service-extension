# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.role import Role
from pyvcloud.vcd.utils import get_admin_href
from pyvcloud.vcd.vdc import VDC

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.utils import get_vcd_sys_admin_client

# Cache to keep ovdc_id to org_name mapping for vcd cse cluster list
OVDC_TO_ORG_MAP = {}
ORG_ADMIN_RIGHTS = ['General: Administrator Control',
                    'General: Administrator View']


def get_org_name_of_ovdc(vdc_id):
    """Get org_name from vdc_id using OVDC_TO_ORG_MAP.

    Update OVDC_TO_ORG_MAP for new {org_name:vdc_id} pair

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


def get_user_rights(sys_admin_client, user_session):
    """Return rights associated with the role of an user.

    :param pyvcloud.vcd.client.Client sys_admin_client: the sys admin cilent
        that will be used to query vCD about the rights and roles of the
        concerned user.
    :param lxml.objectify.ObjectifiedElement user_session:

    :return: the list of rights contained in the role of the user
        (corresponding to the user_session).

    :rtype: list of str
    """
    user_org_link = find_link(resource=user_session,
                              rel=RelationType.DOWN,
                              media_type=EntityType.ORG.value)
    user_org_href = user_org_link.href
    org = Org(sys_admin_client, href=user_org_href)
    user_role_name = user_session.get('roles')
    role = Role(sys_admin_client,
                resource=org.get_role_resource(user_role_name))

    user_rights = []
    user_rights_as_list_of_dict = role.list_rights()
    for right_dict in user_rights_as_list_of_dict:
        user_rights.append(right_dict.get('name'))
    return user_rights


def is_org_admin(user_session):
    """Return if the logged-in user is an org-admin.

    :param lxml.objectify.ObjectifiedElement user_session:

    :return True or False
    :rtype: bool
    """
    user_rights = get_user_rights(get_vcd_sys_admin_client(), user_session)
    return all(right in user_rights for right in ORG_ADMIN_RIGHTS)


def get_vdc_by_id(sys_admin_client, vdc_id):
    """Return VDC object for the given vdc_id.

    :param pyvcloud.vcd.client.Client sys_admin_client: the sys admin cilent
        that will be used to query vCD

    :param str vdc_id: UUID of the vdc

    :return VDC object
    :rtype: pyvcloud.vcd.vdc.VDC
    """
    LOGGER.debug(f"Getting vdc by id:{vdc_id}")
    admin_href = sys_admin_client.get_admin().get('href')
    ovdc_href = f'{admin_href}vdc/{vdc_id}'
    resource = sys_admin_client.get_resource(ovdc_href)
    return VDC(sys_admin_client, resource=resource)
