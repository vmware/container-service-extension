# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Utility module to perform operations which involve pyvcloud calls."""
from datetime import datetime, timedelta
import pathlib
import time
from typing import Optional
import urllib

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import EntityNotFoundException
import pyvcloud.vcd.org as vcd_org
from pyvcloud.vcd.utils import extract_id
from pyvcloud.vcd.utils import get_admin_href
from pyvcloud.vcd.utils import to_dict
import pyvcloud.vcd.vapp as vcd_vapp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM
import requests

import container_service_extension.common.constants.server_constants as server_constants # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.utils.core_utils import extract_id_from_href  # noqa: E501
from container_service_extension.common.utils.core_utils import NullPrinter
from container_service_extension.common.utils.core_utils import str_to_bool
from container_service_extension.common.utils.server_utils import get_server_runtime_config  # noqa: E501
import container_service_extension.exception.exceptions as exceptions
import container_service_extension.lib.cloudapi.cloudapi_client as cloud_api_client  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.logging.logger import SERVER_DEBUG_WIRELOG_FILEPATH  # noqa: E501


# Cache to keep ovdc_id to org_name mapping for vcd cse cluster list
OVDC_TO_ORG_MAP = {}
ORG_ADMIN_RIGHTS = ['General: Administrator Control',
                    'General: Administrator View']


def raise_error_if_user_not_from_system_org(client: vcd_client.Client):
    # ToDo: current implementation of client.is_sysadmin checks if
    # org of the user is System or not. If implementation changes,
    # we should adapt accordingly.
    if not client.is_sysadmin():
        raise ValueError("Client does not belong to System Org.")


def connect_vcd_user_via_token(
        tenant_auth_token: str,
        is_jwt_token: bool,
        api_version: Optional[str]):
    server_config = get_server_runtime_config()
    if not api_version:
        api_version = server_config['service']['default_api_version']
    verify_ssl_certs = server_config['vcd']['verify']
    if not verify_ssl_certs:
        requests.packages.urllib3.disable_warnings()
    log_filename = None
    log_wire = str_to_bool(server_config['service'].get('log_wire'))
    if log_wire:
        log_filename = SERVER_DEBUG_WIRELOG_FILEPATH

    client_tenant = vcd_client.Client(
        uri=server_config['vcd']['host'],
        api_version=api_version,
        verify_ssl_certs=verify_ssl_certs,
        log_file=log_filename,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    client_tenant.rehydrate_from_token(tenant_auth_token, is_jwt_token)
    return client_tenant


def get_sys_admin_client(api_version: Optional[str]):
    server_config = get_server_runtime_config()
    if not api_version:
        api_version = server_config['service']['default_api_version']
    verify_ssl_certs = server_config['vcd']['verify']
    if not verify_ssl_certs:
        requests.packages.urllib3.disable_warnings()
    log_filename = None
    log_wire = str_to_bool(server_config['service'].get('log_wire'))
    if log_wire:
        log_filename = SERVER_DEBUG_WIRELOG_FILEPATH

    client = vcd_client.Client(
        uri=server_config['vcd']['host'],
        api_version=api_version,
        verify_ssl_certs=verify_ssl_certs,
        log_file=log_filename,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    credentials = vcd_client.BasicLoginCredentials(
        server_config['vcd']['username'],
        shared_constants.SYSTEM_ORG_NAME,
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
        org = vcd_org.Org(client, href=org_sparse_resource.get('href'))
    else:
        org = vcd_org.Org(client, resource=client.get_org_by_name(org_name))
    return org


def get_vdc(client, vdc_id=None, vdc_name=None, org=None, org_name=None,
            is_admin_operation=False):
    """Get the specified VDC object.

    At least one of vdc_id or vdc_name must be specified. If org or org_name
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


def get_org_name_href_from_ovdc_id(sysadmin_client: vcd_client.Client, vdc_id):
    """Get org name and href from vdc_id using OVDC_TO_ORG_MAP.

    Update OVDC_TO_ORG_MAP for new vdc_id

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param vdc_id: unique ovdc id

    :return: org's name and href

    :rtype: dict
    """
    raise_error_if_user_not_from_system_org(sysadmin_client)

    if vdc_id in OVDC_TO_ORG_MAP:
        return OVDC_TO_ORG_MAP.get(vdc_id)

    vdc_href = f"{sysadmin_client.get_api_uri()}/vdc/{vdc_id}"
    vdc_resource = sysadmin_client.get_resource(get_admin_href(vdc_href))
    vdc_obj = VDC(sysadmin_client, resource=vdc_resource)
    link = vcd_client.find_link(
        vdc_obj.get_resource(),
        vcd_client.RelationType.UP,
        vcd_client.EntityType.ADMIN_ORG.value)
    org_href = link.href
    org = vcd_org.Org(sysadmin_client, href=org_href)
    org_name = org.get_name()

    result = {'name': org_name, 'href': org_href}
    OVDC_TO_ORG_MAP[vdc_id] = result
    return result


def get_org_name_from_ovdc_id(sysadmin_client: vcd_client.Client, vdc_id):
    return get_org_name_href_from_ovdc_id(sysadmin_client, vdc_id).get('name')


def get_org_href_from_ovdc_id(sysadmin_client: vcd_client.Client, vdc_id):
    return get_org_name_href_from_ovdc_id(sysadmin_client, vdc_id).get('href')


def get_pvdc_id(ovdc: VDC):
    """Get id of pvdc backing an ovdc.

    :param pyvcloud.vcd.VDC ovdc: This ovdc object has to be created with a
        sys admin client.

    :return: pvdc id

    :rtype: str
    """
    raise_error_if_user_not_from_system_org(ovdc.client)
    pvdc_element = ovdc.get_resource().ProviderVdcReference
    pvdc_id = pvdc_element.get('id')
    return extract_id(pvdc_id)


def get_pvdc_id_from_pvdc_name(name, vc_name_in_vcd):
    """Retrieve the pvdc id based on the pvdc name and vcenter name.

    :param str name: name of the pvdc.
    :param str vc_name_in_vcd: name of the vcenter in vcd.

    :return: UUID of the pvdc in vcd.

    :rtype: str
    """
    # cannot remove this instance of get_sys_admin_client
    # this is used only by PksCache, which is initialized on server start
    client = None
    try:
        client = get_sys_admin_client(api_version=None)
        query = client.get_typed_query(
            vcd_client.ResourceType.PROVIDER_VDC.value,
            query_result_format=vcd_client.QueryResultFormat.RECORDS,
            qfilter=f'vcName=={urllib.parse.quote(vc_name_in_vcd)}',
            equality_filter=('name', name))
        for pvdc_record in list(query.execute()):
            href = pvdc_record.get('href')
            pvdc_id = href.split("/")[-1]
            return pvdc_id
    finally:
        if client:
            client.logout()


def upload_ova_to_catalog(client, catalog_name, filepath, update=False,
                          org=None, org_name=None, logger=NULL_LOGGER,
                          msg_update_callback=NullPrinter()):
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
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.


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
            msg_update_callback.info(msg)
            logger.info(msg)

            org.delete_catalog_item(catalog_name, catalog_item_name)
            org.reload()
            wait_for_catalog_item_to_resolve(client, catalog_name,
                                             catalog_item_name, org=org)

            msg = f"Update flag set. Checking catalog '{catalog_name}' for " \
                  f"'{catalog_item_name}'"
            msg_update_callback.info(msg)
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
            msg_update_callback.general(msg)
            logger.info(msg)

            return
        except EntityNotFoundException:
            pass

    msg = f"Uploading '{catalog_item_name}' to catalog '{catalog_name}'"
    msg_update_callback.info(msg)
    logger.info(msg)

    org.upload_ovf(catalog_name, filepath)
    org.reload()
    wait_for_catalog_item_to_resolve(client, catalog_name, catalog_item_name,
                                     org=org)
    msg = f"Uploaded '{catalog_item_name}' to catalog '{catalog_name}'"
    msg_update_callback.general(msg)
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


def create_and_share_catalog(org, catalog_name, catalog_desc='',
                             logger=NULL_LOGGER,
                             msg_update_callback=NullPrinter()):
    """Create and share specified catalog.

    If catalog does not exist in vCD, create it. Share the specified catalog
    to all orgs.

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:
    :param str catalog_desc:
    :param logging.Logger logger: optional logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :return: XML representation of specified catalog.

    :rtype: lxml.objectify.ObjectifiedElement

    :raises pyvcloud.vcd.exceptions.EntityNotFoundException: if catalog sharing
        fails due to catalog creation failing.
    """
    if catalog_exists(org, catalog_name):
        msg = f"Found catalog '{catalog_name}'"
        msg_update_callback.general(msg)
        logger.info(msg)
    else:
        msg = f"Creating catalog '{catalog_name}'"
        msg_update_callback.info(msg)
        logger.info(msg)

        org.create_catalog(catalog_name, catalog_desc)

        msg = f"Created catalog '{catalog_name}'"
        msg_update_callback.general(msg)
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
    resource_type = vcd_client.ResourceType.VAPP.value
    if client.is_sysadmin():
        resource_type = vcd_client.ResourceType.ADMIN_VAPP.value

    q = client.get_typed_query(
        resource_type,
        query_result_format=vcd_client.QueryResultFormat.RECORDS,
        equality_filter=('vdc', f"{client.get_api_uri()}/vdc/{ovdc_id}")
    )

    vapps = []
    for record in q.execute():
        vapp = vcd_vapp.VApp(client, href=record.get('href'))
        vapp.reload()
        vapps.append(vapp)

    return vapps


def get_parent_network_name_of_vapp(vapp):
    network_name = ""
    if not vapp:
        return network_name

    vapp_resource = vapp.get_resource()
    network_config_section = None
    if hasattr(vapp_resource, 'NetworkConfigSection'):
        network_config_section = vapp_resource.NetworkConfigSection
    network_config = None
    if network_config_section is not None and hasattr(network_config_section, 'NetworkConfig'):  # noqa: E501
        network_config = network_config_section.NetworkConfig
    configuration_section = None
    if network_config is not None and hasattr(network_config, 'Configuration'):  # noqa: E501
        configuration_section = network_config.Configuration
    if configuration_section is not None and hasattr(configuration_section, 'ParentNetwork'):  # noqa: E501
        parent_network = configuration_section.ParentNetwork
        network_name = parent_network.get('name')

    return network_name


def get_storage_profile_name_of_first_vm_in_vapp(vapp):
    storage_profile_name = ""
    if not vapp:
        return storage_profile_name

    vms = vapp.get_all_vms()

    if len(vms) == 0:
        return storage_profile_name

    first_vm = vms[0]
    vm_spec_section = None
    if hasattr(first_vm, 'VmSpecSection'):
        vm_spec_section = first_vm.VmSpecSection
    disk_section = None
    if vm_spec_section is not None and hasattr(vm_spec_section, 'DiskSection'):  # noqa : E501
        disk_section = vm_spec_section.DiskSection
    disk_settings = None
    if disk_section is not None and hasattr(disk_section, 'DiskSettings'):  # noqa: E501
        disk_settings = disk_section.DiskSettings
    if disk_settings is not None and hasattr(disk_settings, 'StorageProfile'):  # noqa: E501
        storage_profile = disk_settings.StorageProfile
        storage_profile_name = storage_profile.get('name')

    return storage_profile_name


def get_cloudapi_client_from_vcd_client(client: vcd_client.Client,
                                        logger_debug=NULL_LOGGER,
                                        logger_wire=NULL_LOGGER):
    token = client.get_access_token()
    is_jwt = True
    if not token:
        token = client.get_xvcloud_authorization_token()
        is_jwt = False
    return cloud_api_client.CloudApiClient(
        base_url=client.get_cloudapi_uri(),
        token=token,
        is_jwt_token=is_jwt,
        api_version=client.get_api_version(),
        logger_debug=logger_debug,
        logger_wire=logger_wire,
        verify_ssl=client._verify_ssl_certs,
        is_sys_admin=client.is_sysadmin())


def get_all_ovdcs(client: vcd_client.Client):
    if client.is_sysadmin():
        # use adminOrgVdc in typed query
        query = client.get_typed_query(
            vcd_client.ResourceType.ADMIN_ORG_VDC.value,
            query_result_format=vcd_client.QueryResultFormat.ID_RECORDS)
    else:
        # use orgVdc in typed query
        query = client.get_typed_query(
            vcd_client.ResourceType.ORG_VDC.value,
            query_result_format=vcd_client.QueryResultFormat.ID_RECORDS)
    return list(query.execute())


def create_cse_page_uri(client: vcd_client.Client, cse_path: str, vcd_uri=None, query_params=None):  # noqa: E501
    """Create a CSE URI equivalent to the VCD uri.

    :param vcd_client.Client client:
    :param str cse_path:
    :param str vcd_uri:
    :param dict query_params:

    Example: To convert a vCD generated Next page URI to CSE server next page
        url:
        create_cse_page_uri(client, cse_path="/cse/3.0/ovdcs",
                            vcd_uri="https://vcd-ip/api/query?type=orgVdcs?page=2&pageSize=25)
        Output:
            https://vcd-ip/api/cse/3.0/ovdcs?page=2&pageSize=25
    """  # noqa: E501
    if query_params is None:
        query_params = {}
    if vcd_uri:
        base_uri = f"{client.get_api_uri().strip('/')}{cse_path}"
        query_dict = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(vcd_uri).query))  # noqa: E501
        page_number = int(query_dict.get(shared_constants.PaginationKey.PAGE_NUMBER))  # noqa: E501
        page_size = int(query_dict.get(shared_constants.PaginationKey.PAGE_SIZE))  # noqa: E501
        cse_uri = f"{base_uri}?page={page_number}&pageSize={page_size}"
        for key, value in query_params.items():
            cse_uri += f"&{key}={value}"
        return cse_uri


def get_ovdcs_by_page(
        client: vcd_client.Client,
        page=shared_constants.CSE_PAGINATION_FIRST_PAGE_NUMBER,
        page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE):
    """Get the list of ovdcs in the page."""
    if client.is_sysadmin():
        # use adminOrgVdc in typed query
        query = client.get_typed_query(
            vcd_client.ResourceType.ADMIN_ORG_VDC.value,
            page=page,
            page_size=page_size,
            query_result_format=vcd_client.QueryResultFormat.ID_RECORDS)
    else:
        # use orgVdc in typed query
        query = client.get_typed_query(
            vcd_client.ResourceType.ORG_VDC.value,
            page=page,
            page_size=page_size,
            query_result_format=vcd_client.QueryResultFormat.ID_RECORDS)
    vdc_results = query.execute()
    return vdc_results


def get_org_user_names(client: vcd_client.Client, org_name):
    """Get a set of user names in an org.

    :param vcd_client.Client client: current client
    :param str org_name: org name to search for users

    :return: set of user names
    :rtype: set
    """
    org_href = client.get_org_by_name(org_name).get('href')
    org = vcd_org.Org(client, org_href)
    str_elem_users: list = org.list_users()
    user_names: set = set()
    for user_str_elem in str_elem_users:
        curr_user_dict = to_dict(user_str_elem, exclude=[])
        user_name = curr_user_dict['name']
        user_names.add(user_name)
    return user_names


def create_org_user_id_to_name_dict(client: vcd_client.Client, org_name):
    """Get a dictionary of users ids to user names.

    :param vcd_client.Client client: current client
    :param str org_name: org name to search for users

    :return: dict of user id keys and user name values
    :rtype: dict
    """
    org_href = client.get_org_by_name(org_name).get('href')
    org = vcd_org.Org(client, org_href)
    str_elem_users: list = org.list_users()
    user_id_to_name_dict = {}
    for user_str_elem in str_elem_users:
        curr_user_dict = to_dict(user_str_elem, exclude=[])
        user_name = curr_user_dict['name']
        user_urn = shared_constants.USER_URN_PREFIX + \
            extract_id_from_href(curr_user_dict['href'])
        user_id_to_name_dict[user_urn] = user_name

    return user_id_to_name_dict


def get_user_role_name(client: vcd_client.Client):
    """Get the name of the role of the currently logged in user.

    :param vcd_client.Client client:

    :returns: name of the logged in users' role.

    :rtype: str
    """
    return client.get_vcloud_session().get('roles')


def get_org_id_from_vdc_name(client: vcd_client.Client, vdc_name: str):
    """Return org id given vdc name.

    :param vcd_client.Client client: vcd client
    :param str vdc_name: vdc name

    :return: org id, with no prefix, e.g., '12345'
    :rtype: str
    """
    if client.is_sysadmin():
        resource_type = vcd_client.ResourceType.ADMIN_ORG_VDC.value
    else:
        resource_type = vcd_client.ResourceType.ORG_VDC.value
    query = client.get_typed_query(
        query_type_name=resource_type,
        query_result_format=vcd_client.QueryResultFormat.ID_RECORDS,
        equality_filter=('name', vdc_name))
    records = list(query.execute())
    if len(records) == 0:
        return None

    # Process org id
    if client.is_sysadmin():
        org_urn_id = records[0].attrib['org']
    else:
        org_name = records[0].attrib['orgName']
        org_resource = client.get_org_by_name(org_name)
        org_urn_id = org_resource.attrib['id']
    return extract_id(org_urn_id)


def get_vm_extra_config_element(vm: VM, element_name: str) -> str:
    """Get the value of extra config element of given VM.

    :param VM vm:
    :param str element_name:
    :return: value of config element
    :rtype: str
    """
    vm_extra_config_elements: dict = vm.list_vm_extra_config_info()
    return vm_extra_config_elements.get(element_name)


def wait_for_completion_of_post_customization_step(
        vm: VM,
        customization_phase: str,
        timeout=server_constants.DEFAULT_POST_CUSTOMIZATION_TIMEOUT_SEC,
        poll_frequency=server_constants.DEFAULT_POST_CUSTOMIZATION_POLL_SEC,
        expected_target_status_list=server_constants.DEFAULT_POST_CUSTOMIZATION_STATUS_LIST,   # noqa: E501
        logger=NULL_LOGGER) -> str:
    """Wait for given post customization phase to reach final expected status.

    The contract is customization phase starts with first element in the
    expected_target_statuses.

    :param VM vm: vm res
    :param str customization_phase:
    :param float timeout: Time in seconds to wait for customization phase to
    finish
    :param float poll_frequency: time in seconds for how often to poll the
    status of customization_phase
    :param list expected_target_status_list: list of expected target status
    values. The contract is to explicitly spell out all the valid status values
    including None as a status to start with.
    :param logging.Logger logger: logger to use for logging custom messages.
    :return: str name of last customization phase
    :rtype: str
    :raises PostCustomizationTimeoutError: if customization phase is not
    finished within given time
    :raises InvalidCustomizationStatus: If customization enters a status
    not in valid target status
    :raises ScriptExecutionError: If script execution fails at any command
    """
    # Raise exception on empty status list
    if not expected_target_status_list:
        logger.error("VM Post guest customization error: empty target status list")  # noqa: E501
        raise exceptions.InvalidCustomizationStatus

    start_time = datetime.now()
    current_status = expected_target_status_list[0]
    remaining_statuses = list(expected_target_status_list)

    while True:
        new_status = get_vm_extra_config_element(vm, customization_phase)
        if new_status not in remaining_statuses:
            logger.error(f"Invalid VM Post guest customization status:{new_status}")  # noqa: E501
            raise exceptions.InvalidCustomizationStatus
        # update the remaining statuses on status change
        if new_status != current_status:
            remaining_statuses.remove(current_status)
            logger.info(f"Post guest customization phase {customization_phase } in {new_status}")  # noqa: E501
            current_status = new_status
        # Check for successful customization: reaching last status between
        if new_status == expected_target_status_list[-1]:
            return new_status

        # Catch any intermediate command failure and raise early exception
        script_execution_status = get_vm_extra_config_element(vm, server_constants.POST_CUSTOMIZATION_SCRIPT_EXECUTION_STATUS)  # noqa: E501
        if script_execution_status and int(script_execution_status) != 0:
            script_execution_failure_reason = get_vm_extra_config_element(vm, server_constants.POST_CUSTOMIZATION_SCRIPT_EXECUTION_FAILURE_REASON)  # noqa: E501
            logger.error(f"VM Post guest customization script failed with error:{script_execution_failure_reason}")  # noqa: E501
            raise exceptions.ScriptExecutionError

        if datetime.now() - start_time > timedelta(seconds=timeout):
            break
        time.sleep(poll_frequency)
    logger.error("VM Post guest customization failed due to timeout")  # noqa: E501
    raise exceptions.PostCustomizationTimeoutError
