# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from urllib.parse import urlparse

import pika
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import FenceMode
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.platform import Platform
import requests
from requests.exceptions import HTTPError
from vsphere_guest_run.vsphere import VSphere
import yaml

from container_service_extension.exceptions import AmqpConnectionError
from container_service_extension.exceptions import AmqpError
from container_service_extension.local_template_manager import \
    set_metadata_on_catalog_item
from container_service_extension.logger import configure_install_logger
from container_service_extension.logger import INSTALL_LOG_FILEPATH
from container_service_extension.logger import INSTALL_LOGGER as LOGGER
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import setup_log_file_directory
from container_service_extension.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.nsxt.dfw_manager import DFWManager
from container_service_extension.nsxt.ipset_manager import IPSetManager
from container_service_extension.nsxt.nsxt_client import NSXTClient
from container_service_extension.pks_cache import Credentials
from container_service_extension.pksclient.client.v1.api_client \
    import ApiClient as ApiClientV1
from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pyvcloud_utils import catalog_exists
from container_service_extension.pyvcloud_utils import catalog_item_exists
from container_service_extension.pyvcloud_utils import create_and_share_catalog
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.remote_template_manager import \
    get_revisioned_template_name
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
from container_service_extension.sample_generator import \
    PKS_ACCOUNTS_SECTION_KEY, PKS_NSXT_SERVERS_SECTION_KEY, \
    PKS_ORGS_SECTION_KEY, PKS_PVDCS_SECTION_KEY, PKS_SERVERS_SECTION_KEY, \
    SAMPLE_AMQP_CONFIG, SAMPLE_BROKER_CONFIG, SAMPLE_PKS_ACCOUNTS_SECTION, \
    SAMPLE_PKS_NSXT_SERVERS_SECTION, SAMPLE_PKS_ORGS_SECTION, \
    SAMPLE_PKS_PVDCS_SECTION, SAMPLE_PKS_SERVERS_SECTION, \
    SAMPLE_SERVICE_CONFIG, SAMPLE_VCD_CONFIG, SAMPLE_VCS_CONFIG # noqa: H301
from container_service_extension.server_constants import \
    CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY, CSE_NATIVE_DEPLOY_RIGHT_CATEGORY, \
    CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION, CSE_NATIVE_DEPLOY_RIGHT_NAME, \
    CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY, CSE_PKS_DEPLOY_RIGHT_CATEGORY, \
    CSE_PKS_DEPLOY_RIGHT_DESCRIPTION, CSE_PKS_DEPLOY_RIGHT_NAME, \
    CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, EXCHANGE_TYPE, \
    SYSTEM_ORG_NAME # noqa: H301
from container_service_extension.template_builder import TemplateBuilder
from container_service_extension.uaaclient.uaaclient import UaaClient
from container_service_extension.utils import check_file_permissions
from container_service_extension.utils import check_keys_and_value_types
from container_service_extension.utils import ConsoleMessagePrinter
from container_service_extension.utils import get_duplicate_items_in_list


# used for creating temp vapp
TEMP_VAPP_NETWORK_ADAPTER_TYPE = "vmxnet3"
TEMP_VAPP_FENCE_MODE = FenceMode.BRIDGED.value
VERSION_V1 = 'v1'


def get_validated_config(config_file_name, msg_update_callback=None):
    """Get the config file as a dictionary and check for validity.

    Ensures that all properties exist and all values are the expected type.
    Checks that AMQP connection is available, and vCD/VCs are valid.
    Does not guarantee that CSE has been installed according to this
    config file.

    :param str config_file_name: path to config file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :return: CSE config

    :rtype: dict

    :raises KeyError: if config file has missing or extra properties.
    :raises TypeError: if the value type for a config file property
        is incorrect.
    :raises container_service_extension.exceptions.AmqpConnectionError: if
        AMQP connection failed (host, password, port, username,
        vhost is invalid).
    :raises pyvcloud.vcd.exceptions.NotAcceptableException: if 'vcd'
        'api_version' is unsupported.
    :raises requests.exceptions.ConnectionError: if 'vcd' 'host' is invalid.
    :raises pyvcloud.vcd.exceptions.VcdException: if 'vcd' 'username' or
        'password' is invalid.
    :raises pyVmomi.vim.fault.InvalidLogin: if 'vcs' 'username' or 'password'
        is invalid.
    """
    check_file_permissions(config_file_name,
                           msg_update_callback=msg_update_callback)
    with open(config_file_name) as config_file:
        config = yaml.safe_load(config_file) or {}
    pks_config_location = config.get('pks_config')
    if msg_update_callback:
        msg_update_callback.info(
            f"Validating config file '{config_file_name}'")
    # This allows us to compare top-level config keys and value types
    sample_config = {
        **SAMPLE_AMQP_CONFIG, **SAMPLE_VCD_CONFIG,
        **SAMPLE_VCS_CONFIG, **SAMPLE_SERVICE_CONFIG,
        **SAMPLE_BROKER_CONFIG
    }
    check_keys_and_value_types(config, sample_config, location='config file',
                               msg_update_callback=msg_update_callback)
    _validate_amqp_config(config['amqp'], msg_update_callback)
    _validate_vcd_and_vcs_config(config['vcd'], config['vcs'],
                                 msg_update_callback)
    _validate_broker_config(config['broker'], msg_update_callback)
    check_keys_and_value_types(config['service'],
                               SAMPLE_SERVICE_CONFIG['service'],
                               location="config file 'service' section",
                               msg_update_callback=msg_update_callback)
    if msg_update_callback:
        msg_update_callback.general(
            f"Config file '{config_file_name}' is valid")
    if isinstance(pks_config_location, str) and pks_config_location:
        check_file_permissions(pks_config_location,
                               msg_update_callback=msg_update_callback)
        with open(pks_config_location) as f:
            pks_config = yaml.safe_load(f) or {}
        if msg_update_callback:
            msg_update_callback.info(
                f"Validating PKS config file '{pks_config_location}'")
        _validate_pks_config_structure(pks_config, msg_update_callback)
        _validate_pks_config_data_integrity(pks_config, msg_update_callback)
        if msg_update_callback:
            msg_update_callback.general(
                f"PKS Config file '{pks_config_location}' is valid")
        config['pks_config'] = pks_config
    else:
        config['pks_config'] = None

    return config


def _validate_amqp_config(amqp_dict, msg_update_callback=None):
    """Ensure that 'amqp' section of config is correct.

    Checks that 'amqp' section of config has correct keys and value types.
    Also ensures that connection to AMQP server is valid.

    :param dict amqp_dict: 'amqp' section of config file as a dict.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises KeyError: if @amqp_dict has missing or extra properties.
    :raises TypeError: if the value type for an @amqp_dict property
        is incorrect.
    :raises AmqpConnectionError: if AMQP connection failed.
    """
    check_keys_and_value_types(amqp_dict, SAMPLE_AMQP_CONFIG['amqp'],
                               location="config file 'amqp' section",
                               msg_update_callback=msg_update_callback)
    credentials = pika.PlainCredentials(amqp_dict['username'],
                                        amqp_dict['password'])
    parameters = pika.ConnectionParameters(amqp_dict['host'],
                                           amqp_dict['port'],
                                           amqp_dict['vhost'],
                                           credentials,
                                           ssl=amqp_dict['ssl'],
                                           connection_attempts=3,
                                           retry_delay=2,
                                           socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        if msg_update_callback:
            msg_update_callback.general(
                "Connected to AMQP server "
                f"({amqp_dict['host']}:{amqp_dict['port']})")
    except Exception as err:
        raise AmqpConnectionError("Amqp connection failed:", str(err))
    finally:
        if connection is not None:
            connection.close()


def _validate_vcd_and_vcs_config(vcd_dict, vcs, msg_update_callback=None):
    """Ensure that 'vcd' and vcs' section of config are correct.

    Checks that 'vcd' and 'vcs' section of config have correct keys and value
    types. Also checks that vCD and all registered VCs in vCD are accessible.

    :param dict vcd_dict: 'vcd' section of config file as a dict.
    :param list vcs: 'vcs' section of config file as a list of dicts.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises KeyError: if @vcd_dict or a vc in @vcs has missing or
        extra properties.
    :raises TypeError: if the value type for a @vcd_dict or vc property
        is incorrect.
    :raises ValueError: if vCD has a VC that is not listed in the config file.
    """
    check_keys_and_value_types(vcd_dict, SAMPLE_VCD_CONFIG['vcd'],
                               location="config file 'vcd' section",
                               msg_update_callback=msg_update_callback)
    if not vcd_dict['verify']:
        if msg_update_callback:
            msg_update_callback.general(
                'InsecureRequestWarning: Unverified HTTPS request is '
                'being made. Adding certificate verification is '
                'strongly advised.')
        requests.packages.urllib3.disable_warnings()

    client = None
    try:
        # TODO() we get an error during client initialization if the specified
        # logfile points to the directory which doesn't exist. This issue
        # should be fixed in pyvcloud, where the logging setup creates
        # directories used in the log filepath if they do not exist yet.
        setup_log_file_directory()
        client = Client(vcd_dict['host'],
                        api_version=vcd_dict['api_version'],
                        verify_ssl_certs=vcd_dict['verify'],
                        log_file=SERVER_DEBUG_WIRELOG_FILEPATH,
                        log_requests=True,
                        log_headers=True,
                        log_bodies=True)
        client.set_credentials(BasicLoginCredentials(vcd_dict['username'],
                                                     SYSTEM_ORG_NAME,
                                                     vcd_dict['password']))
        if msg_update_callback:
            msg_update_callback.general(
                "Connected to vCloud Director "
                f"({vcd_dict['host']}:{vcd_dict['port']})")

        for index, vc in enumerate(vcs, 1):
            check_keys_and_value_types(
                vc, SAMPLE_VCS_CONFIG['vcs'][0],
                location=f"config file 'vcs' section, vc #{index}",
                msg_update_callback=msg_update_callback)

        # Check that all registered VCs in vCD are listed in config file
        platform = Platform(client)
        config_vc_names = [vc['name'] for vc in vcs]
        for platform_vc in platform.list_vcenters():
            platform_vc_name = platform_vc.get('name')
            if platform_vc_name not in config_vc_names:
                raise ValueError(f"vCenter '{platform_vc_name}' registered in "
                                 f"vCD but not found in config file")

        # Check that all VCs listed in config file are registered in vCD
        for vc in vcs:
            vcenter = platform.get_vcenter(vc['name'])
            vsphere_url = urlparse(vcenter.Url.text)
            v = VSphere(vsphere_url.hostname, vc['username'],
                        vc['password'], vsphere_url.port)
            v.connect()
            if msg_update_callback:
                msg_update_callback.general(
                    f"Connected to vCenter Server '{vc['name']}' as "
                    f"'{vc['username']}' ({vsphere_url.hostname}:"
                    f"{vsphere_url.port})")
    finally:
        if client is not None:
            client.logout()


def _validate_broker_config(broker_dict, msg_update_callback=None):
    """Ensure that 'broker' section of config is correct.

    Checks that 'broker' section of config has correct keys and value
    types. Also checks that 'default_broker' property is a valid template.

    :param dict broker_dict: 'broker' section of config file as a dict.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises KeyError: if @broker_dict has missing or extra properties.
    :raises TypeError: if the value type for a @broker_dict property is
        incorrect.
    :raises ValueError: if 'default_template' value is not found in listed
        'templates, or if 'ip_allocation_mode' is not 'dhcp' or 'pool'
    """
    check_keys_and_value_types(broker_dict, SAMPLE_BROKER_CONFIG['broker'],
                               location="config file 'broker' section",
                               excluded_keys=['remote_template_cookbook_url'],
                               msg_update_callback=msg_update_callback)

    valid_ip_allocation_modes = [
        'dhcp',
        'pool'
    ]
    if broker_dict['ip_allocation_mode'] not in valid_ip_allocation_modes:
        raise ValueError(f"IP allocation mode is "
                         f"'{broker_dict['ip_allocation_mode']}' when it "
                         f"should be either 'dhcp' or 'pool'")


def _validate_pks_config_structure(pks_config, msg_update_callback=None):
    sample_config = {
        **SAMPLE_PKS_SERVERS_SECTION, **SAMPLE_PKS_ACCOUNTS_SECTION,
        **SAMPLE_PKS_ORGS_SECTION, **SAMPLE_PKS_PVDCS_SECTION,
        **SAMPLE_PKS_NSXT_SERVERS_SECTION
    }
    check_keys_and_value_types(pks_config, sample_config,
                               location='pks config file',
                               excluded_keys=[PKS_ORGS_SECTION_KEY],
                               msg_update_callback=msg_update_callback)

    pks_servers = pks_config[PKS_SERVERS_SECTION_KEY]
    for index, pks_server in enumerate(pks_servers, 1):
        check_keys_and_value_types(
            pks_server,
            SAMPLE_PKS_SERVERS_SECTION[PKS_SERVERS_SECTION_KEY][0],
            location=f"pks config file '{PKS_SERVERS_SECTION_KEY}' "
                     f"section, pks server #{index}",
            excluded_keys=['proxy'],
            msg_update_callback=msg_update_callback)
    pks_accounts = pks_config[PKS_ACCOUNTS_SECTION_KEY]
    for index, pks_account in enumerate(pks_accounts, 1):
        check_keys_and_value_types(
            pks_account,
            SAMPLE_PKS_ACCOUNTS_SECTION[PKS_ACCOUNTS_SECTION_KEY][0],
            location=f"pks config file '{PKS_ACCOUNTS_SECTION_KEY}' "
                     f"section, pks account #{index}",
            msg_update_callback=msg_update_callback)
    if PKS_ORGS_SECTION_KEY in pks_config.keys():
        orgs = pks_config[PKS_ORGS_SECTION_KEY]
        for index, org in enumerate(orgs, 1):
            check_keys_and_value_types(
                org,
                SAMPLE_PKS_ORGS_SECTION[PKS_ORGS_SECTION_KEY][0],
                location=f"pks config file '{PKS_ORGS_SECTION_KEY}' "
                         f"section, org #{index}",
                msg_update_callback=msg_update_callback)
    pvdcs = pks_config[PKS_PVDCS_SECTION_KEY]
    for index, pvdc in enumerate(pvdcs, 1):
        check_keys_and_value_types(
            pvdc,
            SAMPLE_PKS_PVDCS_SECTION[PKS_PVDCS_SECTION_KEY][0],
            location=f"pks config file '{PKS_PVDCS_SECTION_KEY}' "
                     f"section, pvdc #{index}",
            msg_update_callback=msg_update_callback)
    nsxt_servers = pks_config[PKS_NSXT_SERVERS_SECTION_KEY]
    for index, nsxt_server in enumerate(nsxt_servers, 1):
        check_keys_and_value_types(
            nsxt_server,
            SAMPLE_PKS_NSXT_SERVERS_SECTION[PKS_NSXT_SERVERS_SECTION_KEY][0],
            location=f"pks config file '{PKS_NSXT_SERVERS_SECTION_KEY}' "
                     f"section, nsxt server #{index}",
            excluded_keys=['proxy'],
            msg_update_callback=msg_update_callback)


def _validate_pks_config_data_integrity(pks_config, msg_update_callback=None):
    all_pks_servers = \
        [entry['name'] for entry in pks_config[PKS_SERVERS_SECTION_KEY]]
    all_pks_accounts = \
        [entry['name'] for entry in pks_config[PKS_ACCOUNTS_SECTION_KEY]]

    # Create a cache with pks_account to Credentials mapping
    pks_account_info_table = {}
    for pks_account in pks_config[PKS_ACCOUNTS_SECTION_KEY]:
        pks_account_name = pks_account['pks_api_server']
        credentials = Credentials(pks_account['username'],
                                  pks_account['secret'])

        pks_account_info_table[pks_account_name] = credentials

    # Check for duplicate pks api server names
    duplicate_pks_server_names = get_duplicate_items_in_list(all_pks_servers)
    if len(duplicate_pks_server_names) != 0:
        raise ValueError(
            f"Duplicate PKS api server(s) : {duplicate_pks_server_names} found"
            f" in Section : {PKS_SERVERS_SECTION_KEY}")

    # Check for duplicate pks account names
    duplicate_pks_account_names = get_duplicate_items_in_list(all_pks_accounts)
    if len(duplicate_pks_account_names) != 0:
        raise ValueError(
            f"Duplicate PKS account(s) : {duplicate_pks_account_names} found"
            f" in Section : {PKS_ACCOUNTS_SECTION_KEY}")

    # Check validity of all PKS api servers referenced in PKS accounts section
    for pks_account in pks_config[PKS_ACCOUNTS_SECTION_KEY]:
        pks_server_name = pks_account.get('pks_api_server')
        if pks_server_name not in all_pks_servers:
            raise ValueError(
                f"Unknown PKS api server : {pks_server_name} referenced by "
                f"PKS account : {pks_account.get('name')} in Section : "
                f"{PKS_ACCOUNTS_SECTION_KEY}")

    # Check validity of all PKS accounts referenced in Orgs section
    if PKS_ORGS_SECTION_KEY in pks_config.keys():
        for org in pks_config[PKS_ORGS_SECTION_KEY]:
            referenced_accounts = org.get('pks_accounts')
            if not referenced_accounts:
                continue
            for account in referenced_accounts:
                if account not in all_pks_accounts:
                    raise ValueError(f"Unknown PKS account : {account} refere"
                                     f"nced by Org : {org.get('name')} in "
                                     f"Section : {PKS_ORGS_SECTION_KEY}")

    # Check validity of all PKS api servers referenced in PVDC section
    for pvdc in pks_config[PKS_PVDCS_SECTION_KEY]:
        pks_server_name = pvdc.get('pks_api_server')
        if pks_server_name not in all_pks_servers:
            raise ValueError(f"Unknown PKS api server : {pks_server_name} "
                             f"referenced by PVDC : {pvdc.get('name')} in "
                             f"Section : {PKS_PVDCS_SECTION_KEY}")

    # Check validity of all PKS api servers referenced in the pks_api_servers
    # section
    for pks_server in pks_config[PKS_SERVERS_SECTION_KEY]:
        pks_account = pks_account_info_table.get(pks_server.get('name'))
        pks_configuration = Configuration()
        pks_configuration.proxy = f"http://{pks_server['proxy']}:80" \
            if pks_server.get('proxy') else None
        pks_configuration.host = \
            f"https://{pks_server['host']}:{pks_server['port']}/" \
            f"{VERSION_V1}"
        pks_configuration.access_token = None
        pks_configuration.username = pks_account.username
        pks_configuration.verify_ssl = pks_server['verify']
        pks_configuration.secret = pks_account.secret
        pks_configuration.uaac_uri = \
            f"https://{pks_server['host']}:{pks_server['uaac_port']}"

        uaaClient = UaaClient(pks_configuration.uaac_uri,
                              pks_configuration.username,
                              pks_configuration.secret,
                              proxy_uri=pks_configuration.proxy)
        token = uaaClient.getToken()

        if not token:
            raise ValueError(
                "Unable to connect to PKS server : "
                f"{pks_server.get('name')} ({pks_server.get('host')})")

        pks_configuration.token = token
        client = ApiClientV1(configuration=pks_configuration)

        if client and msg_update_callback:
            msg_update_callback.general(
                "Connected to PKS server ("
                f"{pks_server.get('name')} : {pks_server.get('host')})")

    # Check validity of all PKS api servers referenced in NSX-T section
    for nsxt_server in pks_config[PKS_NSXT_SERVERS_SECTION_KEY]:
        pks_server_name = nsxt_server.get('pks_api_server')
        if pks_server_name not in all_pks_servers:
            raise ValueError(
                f"Unknown PKS api server : {pks_server_name} referenced by "
                f"NSX-T server : {nsxt_server.get('name')} in Section : "
                f"{PKS_NSXT_SERVERS_SECTION_KEY}")

        # Create a NSX-T client and verify connection
        nsxt_client = NSXTClient(
            host=nsxt_server.get('host'),
            username=nsxt_server.get('username'),
            password=nsxt_server.get('password'),
            http_proxy=nsxt_server.get('proxy'),
            https_proxy=nsxt_server.get('proxy'),
            verify_ssl=nsxt_server.get('verify'))
        if not nsxt_client.test_connectivity():
            raise ValueError(
                "Unable to connect to NSX-T server : "
                f"{nsxt_server.get('name')} ({nsxt_server.get('host')})")

        if msg_update_callback:
            msg_update_callback.general(
                f"Connected to NSX-T server ({nsxt_server.get('host')})")

        ipset_manager = IPSetManager(nsxt_client)
        if nsxt_server.get('nodes_ip_block_ids'):
            block_not_found = False
            try:
                for ip_block_id in nsxt_server.get('nodes_ip_block_ids'):
                    if not ipset_manager.get_ip_block_by_id(ip_block_id):
                        block_not_found = True
            except HTTPError:
                block_not_found = True
            if block_not_found:
                raise ValueError(
                    f"Unknown Node IP Block : {ip_block_id} referenced by "
                    f"NSX-T server : {nsxt_server.get('name')}.")
        if nsxt_server.get('pods_ip_block_ids'):
            try:
                block_not_found = False
                for ip_block_id in nsxt_server.get('pods_ip_block_ids'):
                    if not ipset_manager.get_ip_block_by_id(ip_block_id):
                        block_not_found = True
            except HTTPError:
                block_not_found = True
            if block_not_found:
                raise ValueError(
                    f"Unknown Pod IP Block : {ip_block_id} referenced by "
                    f"NSX-T server : {nsxt_server.get('name')}.")

        dfw_manager = DFWManager(nsxt_client)
        fw_section_id = \
            nsxt_server.get('distributed_firewall_section_anchor_id')
        section = dfw_manager.get_firewall_section(id=fw_section_id)
        if not section:
            raise ValueError(
                f"Unknown Firewall section : {fw_section_id} referenced by "
                f"NSX-T server : {nsxt_server.get('name')}.")


def check_cse_installation(config, check_template='*',
                           msg_update_callback=None):
    """Ensure that CSE is installed on vCD according to the config file.

    Checks if CSE is registered to vCD, if catalog exists, and if templates
    exist.

    :param dict config: config yaml file as a dictionary
    :param str check_template: which template to check for. Default value of
        '*' means to check all templates specified in @config
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises EntityNotFoundException: if CSE is not registered to vCD as an
        extension, or if specified catalog does not exist, or if specified
        template(s) do not exist.
    """
    if msg_update_callback:
        msg_update_callback.info(
            "Validating CSE installation according to config file")
    err_msgs = []
    client = None
    try:
        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=SERVER_DEBUG_WIRELOG_FILEPATH,
                        log_requests=True,
                        log_headers=True,
                        log_bodies=True)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)

        # check that AMQP exchange exists
        amqp = config['amqp']
        credentials = pika.PlainCredentials(amqp['username'], amqp['password'])
        parameters = pika.ConnectionParameters(amqp['host'], amqp['port'],
                                               amqp['vhost'], credentials,
                                               ssl=amqp['ssl'],
                                               connection_attempts=3,
                                               retry_delay=2, socket_timeout=5)
        connection = None
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            try:
                channel.exchange_declare(exchange=amqp['exchange'],
                                         exchange_type=EXCHANGE_TYPE,
                                         durable=True,
                                         passive=True,
                                         auto_delete=False)
                if msg_update_callback:
                    msg_update_callback.general(
                        f"AMQP exchange '{amqp['exchange']}' exists")
            except pika.exceptions.ChannelClosed:
                msg = f"AMQP exchange '{amqp['exchange']}' does not exist"
                if msg_update_callback:
                    msg_update_callback.error(msg)
                err_msgs.append(msg)
        except Exception:  # TODO() replace raw exception with specific
            msg = f"Could not connect to AMQP exchange '{amqp['exchange']}'"
            if msg_update_callback:
                msg_update_callback.error(msg)
            err_msgs.append(msg)
        finally:
            if connection is not None:
                connection.close()

        # check that CSE is registered to vCD correctly
        ext = APIExtension(client)
        try:
            cse_info = ext.get_extension(CSE_SERVICE_NAME,
                                         namespace=CSE_SERVICE_NAMESPACE)
            rkey_matches = cse_info['routingKey'] == amqp['routing_key']
            exchange_matches = cse_info['exchange'] == amqp['exchange']
            if not rkey_matches or not exchange_matches:
                msg = "CSE is registered as an extension, but the extension " \
                      "settings on vCD are not the same as config settings."
                if not rkey_matches:
                    msg += f"\nvCD-CSE routing key: {cse_info['routingKey']}" \
                           f"\nCSE config routing key: {amqp['routing_key']}"
                if not exchange_matches:
                    msg += f"\nvCD-CSE exchange: {cse_info['exchange']}" \
                           f"\nCSE config exchange: {amqp['exchange']}"
                if msg_update_callback:
                    msg_update_callback.info(msg)
                err_msgs.append(msg)
            if cse_info['enabled'] == 'true':
                if msg_update_callback:
                    msg_update_callback.general(
                        "CSE on vCD is currently enabled")
            else:
                if msg_update_callback:
                    msg_update_callback.info(
                        "CSE on vCD is currently disabled")
        except MissingRecordException:
            msg = "CSE is not registered to vCD"
            if msg_update_callback:
                msg_update_callback.error(msg)
            err_msgs.append(msg)

        # check that catalog exists in vCD
        org = Org(client, resource=client.get_org())
        catalog_name = config['broker']['catalog']
        if catalog_exists(org, catalog_name):
            if msg_update_callback:
                msg_update_callback.general(f"Found catalog '{catalog_name}'")
            # check that templates exist in vCD
            # Aritra : fix this to fit new template model
            for template in config['broker']['templates']:
                if check_template != '*' \
                        and check_template != template['name']:
                    continue
                catalog_item_name = template['catalog_item']
                if catalog_item_exists(org, catalog_name, catalog_item_name):
                    if msg_update_callback:
                        msg_update_callback.general(
                            f"Found template '{catalog_item_name}' in "
                            f"catalog '{catalog_name}'")
                else:
                    msg = f"Template '{catalog_item_name}' not found in " \
                          f"catalog '{catalog_name}'"
                    if msg_update_callback:
                        msg_update_callback.error(msg)
                    err_msgs.append(msg)
        else:
            msg = f"Catalog '{catalog_name}' not found"
            if msg_update_callback:
                msg_update_callback.error(msg)
            err_msgs.append(msg)
    finally:
        if client is not None:
            client.logout()

    if err_msgs:
        raise EntityNotFoundException(err_msgs)
    if msg_update_callback:
        msg_update_callback.general("CSE installation is valid")


def install_cse(ctx, config_file_name='config.yaml', template_name='*',
                update=False, no_capture=False, ssh_key=None,
                msg_update_callback=None):
    """Handle logistics for CSE installation.

    Handles decision making for configuring AMQP exchange/settings,
    extension registration, catalog setup, and template creation.

    :param click.core.Context ctx:
    :param str config_file_name: config file name.
    :param str template_name: which templates to create/update. A value of '*'
        means to create/update all templates specified in config file.
    :param bool update: if True and templates already exist in vCD,
        overwrites existing templates.
    :param bool no_capture: if True, temporary vApp will not be captured or
        destroyed, so the user can ssh into and debug the VM.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    config = get_validated_config(config_file_name,
                                  msg_update_callback=msg_update_callback)
    configure_install_logger()
    msg = f"Installing CSE on vCloud Director using config file " \
          f"'{config_file_name}'"
    if msg_update_callback:
        msg_update_callback.info(msg)
    LOGGER.info(msg)
    client = None
    try:
        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=INSTALL_LOG_FILEPATH,
                        log_requests=True,
                        log_headers=True,
                        log_bodies=True)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        if msg_update_callback:
            msg_update_callback.general(msg)
        LOGGER.info(msg)

        # create amqp exchange if it doesn't exist
        amqp = config['amqp']
        create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                             amqp['vhost'], amqp['ssl'], amqp['username'],
                             amqp['password'],
                             msg_update_callback=msg_update_callback)

        # register or update cse on vCD
        register_cse(client, amqp['routing_key'], amqp['exchange'],
                     msg_update_callback=msg_update_callback)

        # register rights to vCD
        # TODO() should also remove rights when unregistering CSE
        register_right(client, right_name=CSE_NATIVE_DEPLOY_RIGHT_NAME,
                       description=CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION,
                       category=CSE_NATIVE_DEPLOY_RIGHT_CATEGORY,
                       bundle_key=CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY,
                       msg_update_callback=msg_update_callback)
        register_right(client, right_name=CSE_PKS_DEPLOY_RIGHT_NAME,
                       description=CSE_PKS_DEPLOY_RIGHT_DESCRIPTION,
                       category=CSE_PKS_DEPLOY_RIGHT_CATEGORY,
                       bundle_key=CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY,
                       msg_update_callback=msg_update_callback)

        org_name = config['broker']['org']
        catalog_name = config['broker']['catalog']

        # set up cse catalog
        org = get_org(client, org_name=org_name)
        create_and_share_catalog(
            org, catalog_name, catalog_desc='CSE templates',
            msg_update_callback=msg_update_callback)

        # read remote template cookbook, download all scripts
        rtm = RemoteTemplateManager(
            remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'], # noqa: E501
            logger=LOGGER, msg_update_callback=ConsoleMessagePrinter())
        remote_template_cookbook = rtm.get_remote_template_cookbook()
        rtm.download_all_template_scripts()

        # create all templates mentioned in cookbook
        for template in remote_template_cookbook['templates']:
            catalog_item_name = get_revisioned_template_name(
                template['name'], template['revision'])
            build_params = {
                'template_name': template['name'],
                'template_revision': template['revision'],
                'source_ova_name': template['source_ova_name'],
                'source_ova_href': template['source_ova'],
                'source_ova_sha256': template['sha256_ova'],
                'org_name': org_name,
                'vdc_name': config['broker']['vdc'],
                'catalog_name': catalog_name,
                'catalog_item_name': catalog_item_name,
                'catalog_item_description': template['description'],
                'temp_vapp_name': template['name'] + '_temp',
                'cpu': template['cpu'],
                'memory': template['mem'],
                'network_name': config['broker']['network'],
                'ip_allocation_mode': config['broker']['ip_allocation_mode'],
                'storage_profile': config['broker']['storage_profile']
            }
            builder = TemplateBuilder(
                client, client, build_params, logger=LOGGER,
                msg_update_callback=ConsoleMessagePrinter())
            builder.build()

            set_metadata_on_catalog_item(
                client=client,
                catalog_name=catalog_name,
                catalog_item_name=catalog_item_name,
                data=template,
                org_name=org_name)

        # if it's a PKS setup, setup NSX-T constructs
        if config.get('pks_config'):
            nsxt_servers = config.get('pks_config')['nsxt_servers']
            for nsxt_server in nsxt_servers:
                msg = f"Configuring NSX-T server ({nsxt_server.get('name')})" \
                      " for CSE. Please check install logs for details."
                if msg_update_callback:
                    msg_update_callback.general(msg)
                LOGGER.info(msg)
                nsxt_client = NSXTClient(
                    host=nsxt_server.get('host'),
                    username=nsxt_server.get('username'),
                    password=nsxt_server.get('password'),
                    http_proxy=nsxt_server.get('proxy'),
                    https_proxy=nsxt_server.get('proxy'),
                    verify_ssl=nsxt_server.get('verify'),
                    logger_instance=LOGGER,
                    log_requests=True,
                    log_headers=True,
                    log_body=True)
                setup_nsxt_constructs(
                    nsxt_client=nsxt_client,
                    nodes_ip_block_id=nsxt_server.get('nodes_ip_block_ids'),
                    pods_ip_block_id=nsxt_server.get('pods_ip_block_ids'),
                    ncp_boundary_firewall_section_anchor_id=nsxt_server.get('distributed_firewall_section_anchor_id')) # noqa: E501

    except Exception:
        if msg_update_callback:
            msg_update_callback.error(
                "CSE Installation Error. Check CSE install logs")
        LOGGER.error("CSE Installation Error", exc_info=True)
        raise  # TODO() need installation relevant exceptions for rollback
    finally:
        if client is not None:
            client.logout()


def create_amqp_exchange(exchange_name, host, port, vhost, use_ssl,
                         username, password, msg_update_callback=None):
    """Create the specified AMQP exchange if it does not exist.

    If specified AMQP exchange exists already, does nothing.

    :param str exchange_name: The AMQP exchange name to check for or create.
    :param str host: AMQP host name.
    :param str password: AMQP password.
    :param int port: AMQP port number.
    :param bool use_ssl: Enable ssl.
    :param str username: AMQP username.
    :param str vhost: AMQP vhost.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    msg = f"Checking for AMQP exchange '{exchange_name}'"
    if msg_update_callback:
        msg_update_callback.info(msg)
    LOGGER.info(msg)
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, port, vhost, credentials,
                                           ssl=use_ssl, connection_attempts=3,
                                           retry_delay=2, socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name,
                                 exchange_type=EXCHANGE_TYPE,
                                 durable=True, auto_delete=False)
    except Exception as err:
        msg = f"Cannot create AMQP exchange '{exchange_name}'"
        if msg_update_callback:
            msg_update_callback.error(msg)
        LOGGER.error(msg, exc_info=True)
        raise AmqpError(msg, str(err))
    finally:
        if connection is not None:
            connection.close()
    msg = f"AMQP exchange '{exchange_name}' is ready"
    if msg_update_callback:
        msg_update_callback.general(msg)
    LOGGER.info(msg)


def register_cse(client, routing_key, exchange, msg_update_callback=None):
    """Register or update CSE on vCD.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.client.Client client:
    :param str routing_key:
    :param str exchange:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.
    """
    ext = APIExtension(client)
    patterns = [
        f'/api/{CSE_SERVICE_NAME}',
        f'/api/{CSE_SERVICE_NAME}/.*',
        f'/api/{CSE_SERVICE_NAME}/.*/.*'
    ]

    cse_info = None
    try:
        cse_info = ext.get_extension_info(CSE_SERVICE_NAME,
                                          namespace=CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        pass

    if cse_info is None:
        ext.add_extension(CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, routing_key,
                          exchange, patterns)
        msg = f"Registered {CSE_SERVICE_NAME} as an API extension in vCD"
    else:
        ext.update_extension(CSE_SERVICE_NAME, namespace=CSE_SERVICE_NAMESPACE,
                             routing_key=routing_key, exchange=exchange)
        msg = f"Updated {CSE_SERVICE_NAME} API Extension in vCD"

    if msg_update_callback:
        msg_update_callback.general(msg)
    LOGGER.info(msg)


def register_right(client, right_name, description, category, bundle_key,
                   msg_update_callback=None):
    """Register a right for CSE.

    :param pyvcloud.vcd.client.Client client:
    :param str right_name: the name of the new right to be registered.
    :param str description: brief description about the new right.
    :param str category: add the right in existing categories in
        vCD Roles and Rights or specify a new category name.
    :param str bundle_key: is used to identify the right name and change
        its value to different languages using localization bundle.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises BadRequestException: if a right with given name already
        exists in vCD.
    """
    ext = APIExtension(client)
    # Since the client is a sys admin, org will hold a reference to System org
    system_org = Org(client, resource=client.get_org())
    try:
        right_name_in_vcd = f"{{{CSE_SERVICE_NAME}}}:{right_name}"
        # TODO(): When org.get_right_record() is moved outside the org scope in
        # pyvcloud, update the code below to adhere to the new method names.
        system_org.get_right_record(right_name_in_vcd)
        msg = f"Right: {right_name} already exists in vCD"
        if msg_update_callback:
            msg_update_callback.general(msg)
        LOGGER.info(msg)
        # Presence of the right in vCD is not a guarantee that the right will
        # be assigned to system org too.
        rights_in_system = system_org.list_rights_of_org()
        for dikt in rights_in_system:
            # TODO(): When localization support comes in, this check should be
            # ditched for a better one.
            if dikt['name'] == right_name_in_vcd:
                msg = f"Right: {right_name} already assigned to System " \
                    f"organization."
                if msg_update_callback:
                    msg_update_callback.general(msg)
                LOGGER.info(msg)
                return
        # Since the right is not assigned to system org, we need to add it.
        msg = f"Assigning Right: {right_name} to System organization."
        if msg_update_callback:
            msg_update_callback.general(msg)
        LOGGER.info(msg)
        system_org.add_rights([right_name_in_vcd])
    except EntityNotFoundException:
        # Registering a right via api extension end point auto assigns it to
        # System org.
        msg = f"Registering Right: {right_name} in vCD"
        if msg_update_callback:
            msg_update_callback.general(msg)
        LOGGER.info(msg)
        ext.add_service_right(
            right_name, CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, description,
            category, bundle_key)
