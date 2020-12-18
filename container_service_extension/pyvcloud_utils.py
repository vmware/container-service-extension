# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pathlib
import urllib

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import EntityNotFoundException
import pyvcloud.vcd.org as vcd_org
from pyvcloud.vcd.utils import extract_id
from pyvcloud.vcd.utils import get_admin_href
import pyvcloud.vcd.vapp as vcd_vapp
from pyvcloud.vcd.vdc import VDC
import requests

import container_service_extension.cloudapi.cloudapi_client as cloudApiClient
from container_service_extension.logger import NULL_LOGGER
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_LOGGER
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import PaginationKey
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import NullPrinter
from container_service_extension.utils import str_to_bool


# Cache to keep ovdc_id to org_name mapping for vcd cse cluster list
OVDC_TO_ORG_MAP = {}
ORG_ADMIN_RIGHTS = ['General: Administrator Control',
                    'General: Administrator View']


def raise_error_if_user_not_from_system_org(client: vcd_client.Client):
    if not client.is_sysadmin():
        raise ValueError("Client should be sysadmin.")


def connect_vcd_user_via_token(tenant_auth_token, is_jwt_token):
    server_config = get_server_runtime_config()
    vcd_uri = server_config['vcd']['host']
    version = server_config['vcd']['api_version']
    verify_ssl_certs = server_config['vcd']['verify']
    log_filename = None
    log_wire = str_to_bool(server_config['service'].get('log_wire'))
    if log_wire:
        log_filename = SERVER_DEBUG_WIRELOG_FILEPATH
    client_tenant = vcd_client.Client(
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
        SERVER_LOGGER.warning("InsecureRequestWarning: Unverified HTTPS "
                              "request is being made. Adding certificate "
                              "verification is strongly advised.")
        requests.packages.urllib3.disable_warnings()
    log_filename = None
    log_wire = str_to_bool(server_config['service'].get('log_wire'))
    if log_wire:
        log_filename = SERVER_DEBUG_WIRELOG_FILEPATH
    client = vcd_client.Client(
        uri=server_config['vcd']['host'],
        api_version=server_config['vcd']['api_version'],
        verify_ssl_certs=server_config['vcd']['verify'],
        log_file=log_filename,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    credentials = vcd_client.BasicLoginCredentials(
        server_config['vcd']['username'],
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
        org = vcd_org.Org(client, href=org_sparse_resource.get('href'))
    else:
        org = vcd_org.Org(client, resource=client.get_org_by_name(org_name))
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


def get_org_name_href_from_ovdc_id(sysadmin_client: vcd_client.Client, vdc_id):
    """Get org name and href from vdc_id using OVDC_TO_ORG_MAP.

    Update OVDC_TO_ORG_MAP for new vdc_id

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


def get_pvdc_id(sysadmin_client: vcd_client.Client, ovdc: VDC):
    """Get id of pvdc backing an ovdc.

    :param pyvcloud.vcd.VDC ovdc: This ovdc object has to be created with a
        sys admin client.

    :return: pvdc id

    :rtype: str
    """
    raise_error_if_user_not_from_system_org(sysadmin_client)

    pvdc_element = ovdc.get_resource().ProviderVdcReference
    # To support <= VCD 9.1 where no 'id' is present in pvdc
    # element, it has to be extracted from href. Once VCD 9.1 support
    # is discontinued, this code is not required.
    if float(sysadmin_client.get_api_version()) < float(vcd_client.ApiVersion.VERSION_31.value): # noqa: E501
        pvdc_href = pvdc_element.get('href')
        return pvdc_href.split("/")[-1]
    else:
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
        client = get_sys_admin_client()
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
    if network_config_section is not None and hasattr(network_config_section, 'NetworkConfig'): # noqa: E501
        network_config = network_config_section.NetworkConfig
    configuration_section = None
    if network_config is not None and hasattr(network_config, 'Configuration'): # noqa: E501
        configuration_section = network_config.Configuration
    if configuration_section is not None and hasattr(configuration_section, 'ParentNetwork'): # noqa: E501
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
    if vm_spec_section is not None and hasattr(vm_spec_section, 'DiskSection'): # noqa : E501
        disk_section = vm_spec_section.DiskSection
    disk_settings = None
    if disk_section is not None and hasattr(disk_section, 'DiskSettings'): # noqa: E501
        disk_settings = disk_section.DiskSettings
    if disk_settings is not None and hasattr(disk_settings, 'StorageProfile'): # noqa: E501
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
    return cloudApiClient.CloudApiClient(base_url=client.get_cloudapi_uri(),
                                         token=token,
                                         is_jwt_token=is_jwt,
                                         api_version=client.get_api_version(),
                                         logger_debug=logger_debug,
                                         logger_wire=logger_wire,
                                         verify_ssl=client._verify_ssl_certs,
                                         is_sys_admin=client.is_sysadmin())


def get_all_ovdcs(client: vcd_client.Client):
    query = None
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


def create_cse_page_uri(client: vcd_client.Client, cse_path: str, vcd_uri=None, query_params={}):  # noqa: E501
    """Create a CSE URI equivalent to the VCD uri.

    :param vcd_client.Client client:
    :param str path:
    :param str vcd_uri:
    :param dict query_params

    Example: To convert a vCD generated Next page URI to CSE server next page
        url:
        create_cse_page_uri(client, cse_path="/cse/3.0/ovdcs",
                            vcd_uri="https://vcd-ip/api/query?type=orgVdcs?page=2&pageSize=25)
        Output:
            https://vcd-ip/api/cse/3.0/ovdcs?page=2&pageSize=25
    """  # noqa: E501
    if vcd_uri:
        base_uri = f"{client.get_api_uri().strip('/')}{cse_path}"
        query_dict = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(vcd_uri).query))  # noqa: E501
        page_number = int(query_dict.get(PaginationKey.PAGE_NUMBER))
        page_size = int(query_dict.get(PaginationKey.PAGE_SIZE))
        cse_uri = f"{base_uri}?page={page_number}&pageSize={page_size}"
        for key, value in query_params.items():
            cse_uri += f"&{key}={value}"
        return cse_uri


def get_ovdcs_by_page(client: vcd_client.Client,
                      page=CSE_PAGINATION_FIRST_PAGE_NUMBER,
                      page_size=CSE_PAGINATION_DEFAULT_PAGE_SIZE):
    """Get the list of ovdcs in the page."""
    query = None
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
