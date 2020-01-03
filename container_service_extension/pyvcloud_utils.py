# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pathlib

from pyvcloud.vcd.client import ApiVersion
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.client import ResourceType
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.role import Role
from pyvcloud.vcd.utils import extract_id
from pyvcloud.vcd.utils import get_admin_href
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
import requests

from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import str_to_bool

# Cache to keep ovdc_id to org_name mapping for vcd cse cluster list
OVDC_TO_ORG_MAP = {}
ORG_ADMIN_RIGHTS = ['General: Administrator Control',
                    'General: Administrator View']


def connect_vcd_user_via_token(tenant_auth_token, is_jwt_token):
    server_config = get_server_runtime_config()
    vcd_uri = server_config['vcd']['host']
    version = server_config['vcd']['api_version']
    verify_ssl_certs = server_config['vcd']['verify']
    log_filename = None
    log_wire = str_to_bool(server_config['service'].get('log_wire'))
    if log_wire:
        log_filename = SERVER_DEBUG_WIRELOG_FILEPATH
    client_tenant = Client(
        uri=vcd_uri,
        api_version=version,
        verify_ssl_certs=verify_ssl_certs,
        log_file=log_filename,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    client_tenant.rehydrate_from_token(tenant_auth_token, is_jwt_token)
    return client_tenant


def get_sys_admin_client():
    server_config = get_server_runtime_config()
    if not server_config['vcd']['verify']:
        LOGGER.warning("InsecureRequestWarning: Unverified HTTPS "
                       "request is being made. Adding certificate "
                       "verification is strongly advised.")
        requests.packages.urllib3.disable_warnings()
    log_filename = None
    log_wire = str_to_bool(server_config['service'].get('log_wire'))
    if log_wire:
        log_filename = SERVER_DEBUG_WIRELOG_FILEPATH
    client = Client(
        uri=server_config['vcd']['host'],
        api_version=server_config['vcd']['api_version'],
        verify_ssl_certs=server_config['vcd']['verify'],
        log_file=log_filename,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    credentials = BasicLoginCredentials(server_config['vcd']['username'],
                                        SYSTEM_ORG_NAME,
                                        server_config['vcd']['password'])
    client.set_credentials(credentials)
    return client


def get_org(client, org_name=None):
    """Get the specified or currently logged-in Org object.

    :param pyvcloud.vcd.client.Client client:
    :param str org_name: which org to use. If None, uses currently logged-in
        org from @client.

    :return: pyvcloud Org object

    :rtype: pyvcloud.vcd.org.Org

    :raises EntityNotFoundException: if the org could not be found.
    """
    if not org_name:
        org_sparse_resource = client.get_org()
        org = Org(client, href=org_sparse_resource.get('href'))
    else:
        org = Org(client, resource=client.get_org_by_name(org_name))
    return org


def get_vdc(client, vdc_id=None, vdc_name=None, org=None, org_name=None,
            is_admin_operation=False):
    """Get the specified VDC object.

    Atleast one of vdc_id or vdc_name must be specified. If org or org_name
    both are not specified, the currently logged in user's org will be used to
    look for the vdc.

    :param pyvcloud.vcd.client.Client client:
    :param str vdc_id: id of the vdc
    :param str vdc_name: name of the vdc
    :param pyvcloud.vcd.org.Org org: specific org to use.
    :param str org_name: specific org to use if @org is not given.
        If None, uses currently logged-in org from @client.
    :param bool is_admin_operation: if set True, will return the admin
            view of the org vdc resource.

    :return: pyvcloud VDC object

    :rtype: pyvcloud.vcd.vdc.VDC

    :raises EntityNotFoundException: if the vdc could not be found.
    """
    if vdc_id:
        base_url = client.get_api_uri()
        # add a trailing slash if missing
        if base_url[-1] != '/':
            base_url += '/'
        if is_admin_operation:
            base_url = get_admin_href(base_url)
        vdc_href = f'{base_url}vdc/{vdc_id}'
        vdc = VDC(client, href=vdc_href)
        vdc.reload()
        return vdc

    resource = None
    if vdc_name:
        if not org:
            org = get_org(client, org_name=org_name)
        resource = org.get_vdc(vdc_name, is_admin_operation=is_admin_operation)

    # TODO() org.get_vdc() should throw exception if vdc not found in the org.
    # This should be handled in pyvcloud. For now, it is handled here.
    if resource is None:
        raise EntityNotFoundException(f"VDC '{vdc_name}' not found in ORG "
                                      f"'{org.get_name()}'")
    return VDC(client, resource=resource)


def get_org_name_from_ovdc_id(vdc_id):
    """Get org_name from vdc_id using OVDC_TO_ORG_MAP.

    Update OVDC_TO_ORG_MAP for new {org_name:vdc_id} pair

    :param vdc_id: unique ovdc id

    :return: org_name

    :rtype: str
    """
    if vdc_id in OVDC_TO_ORG_MAP:
        org_name = OVDC_TO_ORG_MAP.get(vdc_id)
    else:
        client = None
        try:
            client = get_sys_admin_client()
            vdc_href = f"{client.get_api_uri()}/vdc/{vdc_id}"
            vdc_resource = client.get_resource(get_admin_href(vdc_href))
            vdc_obj = VDC(client, resource=vdc_resource)
            link = find_link(vdc_obj.get_resource(), RelationType.UP,
                             EntityType.ADMIN_ORG.value)
            org = Org(client, href=link.href)
            OVDC_TO_ORG_MAP[vdc_id] = org.get_name()
            org_name = org.get_name()
        finally:
            if client:
                client.logout

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
    """Deduce if the logged-in user is an org-admin or not.

    :param lxml.objectify.ObjectifiedElement user_session:

    :return True if the user is an Org Admin else False

    :rtype: bool
    """
    client = None
    try:
        client = get_sys_admin_client()
        user_rights = get_user_rights(client, user_session)
    finally:
        if client:
            client.logout()
    return all(right in user_rights for right in ORG_ADMIN_RIGHTS)


def get_pvdc_id(ovdc):
    """Get id of pvdc backing an ovdc.

    :param pyvcloud.vcd.VDC ovdc: This ovdc object has to be created with a
        sys admin client.

    :return: pvdc id

    :rtype: str
    """
    client = None
    try:
        client = get_sys_admin_client()
        pvdc_element = ovdc.get_resource().ProviderVdcReference
        # To support <= VCD 9.1 where no 'id' is present in pvdc
        # element, it has to be extracted from href. Once VCD 9.1 support
        # is discontinued, this code is not required.
        if float(client.get_api_version()) < \
                float(ApiVersion.VERSION_31.value):
            pvdc_href = pvdc_element.get('href')
            return pvdc_href.split("/")[-1]
        else:
            pvdc_id = pvdc_element.get('id')
            return extract_id(pvdc_id)
    finally:
        if client:
            client.logout()


def get_pvdc_id_from_pvdc_name(name, vc_name_in_vcd):
    """Retrieve the pvdc id based on the pvdc name and vcenter name.

    :param str name: name of the pvdc.
    :param str vc_name_in_vcd: name of the vcenter in vcd.

    :return: UUID of the pvdc in vcd.

    :rtype: str
    """
    client = None
    try:
        client = get_sys_admin_client()
        query = client.get_typed_query(
            ResourceType.PROVIDER_VDC.value,
            query_result_format=QueryResultFormat.RECORDS,
            qfilter=f'vcName=={vc_name_in_vcd}',
            equality_filter=('name', name))
        for pvdc_record in list(query.execute()):
            href = pvdc_record.get('href')
            pvdc_id = href.split("/")[-1]
            return pvdc_id
    finally:
        if client:
            client.logout()
    return None


def upload_ova_to_catalog(client, catalog_name, filepath, update=False,
                          org=None, org_name=None, logger=None,
                          msg_update_callback=None):
    """Upload local ova file to vCD catalog.

    :param pyvcloud.vcd.client.Client client:
    :param str filepath: file path to the .ova file.
    :param str catalog_name: name of catalog.
    :param bool update: signals whether to overwrite an existing catalog
        item with this new one.
    :param pyvcloud.vcd.org.Org org: specific org to use.
    :param str org_name: specific org to use if @org is not given.
        If None, uses currently logged-in org from @client.
    :param logging.Logger logger: optional logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.


    :raises pyvcloud.vcd.exceptions.EntityNotFoundException if catalog
        does not exist.
    :raises pyvcloud.vcd.exceptions.UploadException if upload fails.
    """
    if org is None:
        org = get_org(client, org_name=org_name)
    catalog_item_name = pathlib.Path(filepath).name
    if update:
        try:
            msg = f"Update flag set. Checking catalog '{catalog_name}' for " \
                  f"'{catalog_item_name}'"
            if msg_update_callback:
                msg_update_callback.info(msg)
            if logger:
                logger.info(msg)

            org.delete_catalog_item(catalog_name, catalog_item_name)
            org.reload()
            wait_for_catalog_item_to_resolve(client, catalog_name,
                                             catalog_item_name, org=org)

            msg = f"Update flag set. Checking catalog '{catalog_name}' for " \
                  f"'{catalog_item_name}'"
            if msg_update_callback:
                msg_update_callback.info(msg)
            if logger:
                logger.info(msg)
        except EntityNotFoundException:
            pass
    else:
        try:
            # DEV NOTE: With api v33.0 and onwards, get_catalog_item operation
            # will fail for non admin users of an org which is not hosting the
            # catalog, even if the catalog is explicitly shared with the org in
            # question. Please use this method only for org admin and
            # sys admins.
            org.get_catalog_item(catalog_name, catalog_item_name)
            msg = f"'{catalog_item_name}' already exists in catalog " \
                  f"'{catalog_name}'"
            if msg_update_callback:
                msg_update_callback.general(msg)
            if logger:
                logger.info(msg)

            return
        except EntityNotFoundException:
            pass

    msg = f"Uploading '{catalog_item_name}' to catalog '{catalog_name}'"
    if msg_update_callback:
        msg_update_callback.info(msg)
    if logger:
        logger.info(msg)

    org.upload_ovf(catalog_name, filepath)
    org.reload()
    wait_for_catalog_item_to_resolve(client, catalog_name, catalog_item_name,
                                     org=org)
    msg = f"Uploaded '{catalog_item_name}' to catalog '{catalog_name}'"
    if msg_update_callback:
        msg_update_callback.general(msg)
    if logger:
        logger.info(msg)


def catalog_exists(org, catalog_name):
    """Check if catalog exists.

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:

    :return: True if catalog exists, False otherwise.

    :rtype: bool
    """
    # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail for
    # non admin users of an org which is not hosting the catalog, even if the
    # catalog is explicitly shared with the org in question. Please use this
    # method only for org admin and sys admins.
    try:
        org.get_catalog(catalog_name)
        return True
    except EntityNotFoundException:
        return False


def catalog_item_exists(org, catalog_name, catalog_item_name):
    """Boolean function to check if catalog item exists (name check).

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:
    :param str catalog_item_name:

    :return: True if catalog item exists, False otherwise.

    :rtype: bool
    """
    # DEV NOTE: With api v33.0 and onwards, get_catalog_item operation will
    # fail for non admin users of an an org which is not hosting the catalog,
    # even if the catalog is explicitly shared with the org in question. Please
    # use this method only for org admin and sys admins.
    try:
        org.get_catalog_item(catalog_name, catalog_item_name)
        return True
    except EntityNotFoundException:
        return False


def create_and_share_catalog(org, catalog_name, catalog_desc='', logger=None,
                             msg_update_callback=None):
    """Create and share specified catalog.

    If catalog does not exist in vCD, create it. Share the specified catalog
    to all orgs.

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:
    :param str catalog_desc:
    :param logging.Logger logger: optional logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :return: XML representation of specified catalog.

    :rtype: lxml.objectify.ObjectifiedElement

    :raises pyvcloud.vcd.exceptions.EntityNotFoundException: if catalog sharing
        fails due to catalog creation failing.
    """
    if catalog_exists(org, catalog_name):
        msg = f"Found catalog '{catalog_name}'"
        if msg_update_callback:
            msg_update_callback.general(msg)
        if logger:
            logger.info(msg)
    else:
        msg = f"Creating catalog '{catalog_name}'"
        if msg_update_callback:
            msg_update_callback.info(msg)
        if logger:
            logger.info(msg)

        org.create_catalog(catalog_name, catalog_desc)

        msg = f"Created catalog '{catalog_name}'"
        if msg_update_callback:
            msg_update_callback.general(msg)
        if logger:
            logger.info(msg)
        org.reload()
    org.share_catalog(catalog_name)
    org.reload()
    # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail for
    # non admin users of an org which is not hosting the catalog, even if the
    # catalog is explicitly shared with the org in question. Please use this
    # method only for org admin and sys admins.
    return org.get_catalog(catalog_name)


def wait_for_catalog_item_to_resolve(client, catalog_name, catalog_item_name,
                                     org=None, org_name=None):
    """Wait for catalog item's most recent task to resolve.

    :param pyvcloud.vcd.client.Client client:
    :param str catalog_name:
    :param str catalog_item_name:
    :param pyvcloud.vcd.org.Org org: specific org to use.
    :param str org_name: specific org to use if @org is not provided.
        If None, uses currently logged-in org from @client.

    :raises EntityNotFoundException: if the org or catalog or catalog item
        could not be found.
    """
    if org is None:
        org = get_org(client, org_name=org_name)
    # DEV NOTE: With api v33.0 and onwards, get_catalog_item operation will
    # fail for non admin users of an an org which is not hosting the catalog,
    # even if the catalog is explicitly shared with the org in question. Please
    # use this method only for org admin and sys admins.
    item = org.get_catalog_item(catalog_name, catalog_item_name)
    resource = client.get_resource(item.Entity.get('href'))
    client.get_task_monitor().wait_for_success(resource.Tasks.Task[0])


def get_all_vapps_in_ovdc(client, ovdc_id):
    resource_type = ResourceType.VAPP.value
    if client.is_sysadmin():
        resource_type = ResourceType.ADMIN_VAPP.value

    q = client.get_typed_query(
        resource_type,
        query_result_format=QueryResultFormat.RECORDS,
        equality_filter=('vdc', f"{client.get_api_uri()}/vdc/{ovdc_id}")
    )

    vapps = []
    for record in q.execute():
        vapp = VApp(client, href=record.get('href'))
        vapp.reload()
        vapps.append(vapp)

    return vapps
