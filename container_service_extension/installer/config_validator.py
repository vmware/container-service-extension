# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from typing import Dict
from urllib.parse import urlparse

import cryptography
import pika
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.platform import Platform
from pyVmomi import vim
import requests
from requests.exceptions import HTTPError
import semantic_version
from vsphere_guest_run.vsphere import VSphere
import yaml

from container_service_extension.common.constants.server_constants import \
    CONFIG_DECRYPTION_ERROR_MSG
from container_service_extension.common.constants.server_constants import \
    VCENTER_LOGIN_ERROR_MSG
from container_service_extension.common.constants.server_constants import VERSION_V1  # noqa: E501
from container_service_extension.common.constants.shared_constants import \
    SUPPORTED_VCD_API_VERSIONS, SYSTEM_ORG_NAME
from container_service_extension.common.utils.core_utils import check_file_permissions  # noqa: E501
from container_service_extension.common.utils.core_utils import check_keys_and_value_types  # noqa: E501
from container_service_extension.common.utils.core_utils import get_duplicate_items_in_list  # noqa: E501
from container_service_extension.common.utils.core_utils import get_max_api_version  # noqa: E501
from container_service_extension.common.utils.core_utils import NullPrinter
from container_service_extension.common.utils.core_utils import str_to_bool
from container_service_extension.common.utils.server_utils import should_use_mqtt_protocol  # noqa: E501
from container_service_extension.exception.exceptions import AmqpConnectionError  # noqa: E501
from container_service_extension.exception.exceptions import AmqpError
from container_service_extension.installer.sample_generator import \
    PKS_ACCOUNTS_SECTION_KEY, PKS_NSXT_SERVERS_SECTION_KEY, \
    PKS_ORGS_SECTION_KEY, PKS_PVDCS_SECTION_KEY, PKS_SERVERS_SECTION_KEY, \
    SAMPLE_AMQP_CONFIG, SAMPLE_BROKER_CONFIG, SAMPLE_MQTT_CONFIG, \
    SAMPLE_PKS_ACCOUNTS_SECTION, SAMPLE_PKS_NSXT_SERVERS_SECTION, \
    SAMPLE_PKS_ORGS_SECTION, SAMPLE_PKS_PVDCS_SECTION, \
    SAMPLE_PKS_SERVERS_SECTION, SAMPLE_SERVICE_CONFIG, SAMPLE_VCD_CONFIG, \
    SAMPLE_VCS_CONFIG
from container_service_extension.installer.templates.remote_template_manager \
    import RemoteTemplateManager
from container_service_extension.lib.nsxt.dfw_manager import DFWManager
from container_service_extension.lib.nsxt.ipset_manager import IPSetManager
from container_service_extension.lib.nsxt.nsxt_client import NSXTClient
from container_service_extension.lib.pksclient.api_client import ApiClient
from container_service_extension.lib.pksclient.configuration import Configuration  # noqa: E501
from container_service_extension.lib.telemetry.telemetry_utils import \
    store_telemetry_settings
from container_service_extension.lib.uaaclient.uaaclient import UaaClient
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.logging.logger import SERVER_NSXT_WIRE_LOGGER
import container_service_extension.rde.utils as rde_utils
from container_service_extension.security.encryption_engine import \
    get_decrypted_file_contents
from container_service_extension.server.pks.pks_cache import Credentials


_MAX_API_VERSION_TO_RUN_CSE_WITH_AMQP_IN_NON_LEGACY_MODE = '35.0'


def get_validated_config(config_file_name,
                         pks_config_file_name=None,
                         skip_config_decryption=False,
                         decryption_password=None,
                         log_wire_file=None,
                         logger_debug=NULL_LOGGER,
                         msg_update_callback=NullPrinter()):
    """Get the config file as a dictionary and check for validity.

    Ensures that all properties exist and all values are the expected type.
    Checks that AMQP connection is available, and vCD/VCs are valid.
    Does not guarantee that CSE has been installed according to this
    config file. Additionally populates certain key-value pairs in the
    config dict to avoid repeated computation of those e.g.
    supported api versions, feature flags, RDE version in use etc.

    :param str config_file_name: path to config file.
    :param str pks_config_file_name: path to PKS config file.
    :param bool skip_config_decryption: do not decrypt the config file.
    :param str decryption_password: password to decrypt the config file.
    :param str log_wire_file: log_wire_file to use if needed to wire log
        pyvcloud requests and responses
    :param logging.Logger logger_debug: logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :return: CSE config

    :rtype: dict

    :raises KeyError: if config file has missing or extra properties.
    :raises TypeError: if the value type for a config file property
        is incorrect.
    :raises container_service_extension.exceptions.AmqpConnectionError:
        (when not using MQTT) if AMQP connection failed (host, password, port,
        username, vhost is invalid).
    :raises requests.exceptions.ConnectionError: if 'vcd' 'host' is invalid.
    :raises pyvcloud.vcd.exceptions.VcdException: if 'vcd' 'username' or
        'password' is invalid.
    :raises pyVmomi.vim.fault.InvalidLogin: if 'vcs' 'username' or 'password'
        is invalid.
    """
    check_file_permissions(config_file_name,
                           msg_update_callback=msg_update_callback)
    if skip_config_decryption:
        with open(config_file_name) as config_file:
            config = yaml.safe_load(config_file) or {}
    else:
        msg_update_callback.info(
            f"Decrypting '{config_file_name}'")
        try:
            config = yaml.safe_load(
                get_decrypted_file_contents(config_file_name,
                                            decryption_password)) or {}
        except cryptography.fernet.InvalidToken:
            raise Exception(CONFIG_DECRYPTION_ERROR_MSG)

    msg_update_callback.info(
        f"Validating config file '{config_file_name}'")
    # This allows us to compare top-level config keys and value types
    use_mqtt = should_use_mqtt_protocol(config)
    sample_message_queue_config = SAMPLE_AMQP_CONFIG if not use_mqtt \
        else SAMPLE_MQTT_CONFIG
    sample_config = {
        **sample_message_queue_config, **SAMPLE_VCD_CONFIG,
        **SAMPLE_VCS_CONFIG, **SAMPLE_SERVICE_CONFIG,
        **SAMPLE_BROKER_CONFIG
    }
    log_wire = str_to_bool(config.get('service', {}).get('log_wire'))
    nsxt_wire_logger = NULL_LOGGER
    if not log_wire:
        log_wire_file = None
        nsxt_wire_logger = SERVER_NSXT_WIRE_LOGGER
    check_keys_and_value_types(config, sample_config, location='config file',
                               msg_update_callback=msg_update_callback)
    # MQTT validation not required because no MQTT host, exchange, etc.
    # is needed in the config file since the server code creates and
    # registers the MQTT extension directly using server constants
    if not use_mqtt:
        _validate_amqp_config(config['amqp'], msg_update_callback)
    try:
        _validate_vcd_and_vcs_config(config['vcd'], config['vcs'],
                                     msg_update_callback,
                                     log_file=log_wire_file,
                                     log_wire=log_wire)
    except vim.fault.InvalidLogin:
        raise Exception(VCENTER_LOGIN_ERROR_MSG)
    except requests.exceptions.SSLError as err:
        raise Exception(f"SSL verification failed: {str(err)}")
    except requests.exceptions.ConnectionError as err:
        raise Exception(f"Cannot connect to {err.request.url}.")

    # Validation of service properties is done first as those properties are
    # used in broker validation.
    check_keys_and_value_types(config['service'],
                               SAMPLE_SERVICE_CONFIG['service'],
                               location="config file 'service' section",
                               excluded_keys=['log_wire'],
                               msg_update_callback=msg_update_callback)
    check_keys_and_value_types(config['service']['telemetry'],
                               SAMPLE_SERVICE_CONFIG['service']['telemetry'],
                               location="config file 'service->telemetry' "
                                        "section",
                               msg_update_callback=msg_update_callback)

    _validate_broker_config(config['broker'],
                            legacy_mode=config['service']['legacy_mode'],
                            msg_update_callback=msg_update_callback,
                            logger_debug=logger_debug)

    config = _add_additional_details_to_config(
        config=config, log_wire=log_wire, log_wire_file=log_wire_file)
    _raise_error_if_amqp_not_supported(
        use_mqtt,
        config['service']['default_api_version'],
        logger=logger_debug)

    msg_update_callback.general(
        f"Config file '{config_file_name}' is valid")

    if pks_config_file_name:
        check_file_permissions(pks_config_file_name,
                               msg_update_callback=msg_update_callback)
        if skip_config_decryption:
            with open(pks_config_file_name) as f:
                pks_config = yaml.safe_load(f) or {}
        else:
            msg_update_callback.info(
                f"Decrypting '{pks_config_file_name}'")
            pks_config = yaml.safe_load(
                get_decrypted_file_contents(pks_config_file_name,
                                            decryption_password)) or {}
        msg_update_callback.info(
            f"Validating PKS config file '{pks_config_file_name}'")
        _validate_pks_config_structure(pks_config, msg_update_callback)
        try:
            _validate_pks_config_data_integrity(pks_config,
                                                msg_update_callback,
                                                logger_debug=logger_debug,
                                                logger_wire=nsxt_wire_logger)
        except requests.exceptions.SSLError as err:
            raise Exception(f"SSL verification failed: {str(err)}")

        msg_update_callback.general(
            f"PKS Config file '{pks_config_file_name}' is valid")
        config['pks_config'] = pks_config
    else:
        config['pks_config'] = None

    return config


def _add_additional_details_to_config(
        config: Dict,
        log_wire: bool,
        log_wire_file: str):
    """Update config dict with computed key-value pairs.

    :param dict config:
    :param bool log_wire:
    :param str log_wire_file:

    :return: the updated config file
    :rtype: dict
    """
    is_legacy_mode = config['service']['legacy_mode']

    # Compute common supported api versions by the CSE server and vCD
    sysadmin_client = None
    try:
        sysadmin_client = Client(
            config['vcd']['host'],
            verify_ssl_certs=config['vcd']['verify'],
            log_file=log_wire_file,
            log_requests=log_wire,
            log_headers=log_wire,
            log_bodies=log_wire)
        sysadmin_client.set_credentials(BasicLoginCredentials(
            config['vcd']['username'],
            SYSTEM_ORG_NAME,
            config['vcd']['password']))

        vcd_supported_api_versions = \
            set(sysadmin_client.get_supported_versions_list())
        cse_supported_api_versions = set(SUPPORTED_VCD_API_VERSIONS)
        common_supported_api_versions = \
            list(cse_supported_api_versions.intersection(vcd_supported_api_versions))  # noqa: E501
        common_supported_api_versions.sort()

        if is_legacy_mode:
            common_supported_api_versions = \
                [x for x in common_supported_api_versions
                 if float(x) < 35.0]
        else:
            common_supported_api_versions = \
                [x for x in common_supported_api_versions
                 if float(x) >= 35.0]
        config['service']['supported_api_versions'] = \
            common_supported_api_versions
    finally:
        if sysadmin_client:
            sysadmin_client.logout()

    # Convert legacy_mode flag in service_section to corresponding
    # feature flags
    if 'feature_flags' not in config:
        config['feature_flags'] = {}
    config['feature_flags']['legacy_api'] = str_to_bool(is_legacy_mode)
    config['feature_flags']['non_legacy_api'] = \
        not str_to_bool(is_legacy_mode)

    # Compute the default api version as the max supported version
    # Also compute the RDE version in use
    max_vcd_api_version_supported: str = get_max_api_version(config['service']['supported_api_versions'])  # noqa: E501
    config['service']['default_api_version'] = max_vcd_api_version_supported
    config['service']['rde_version_in_use'] = semantic_version.Version(
        rde_utils.get_runtime_rde_version_by_vcd_api_version(
            max_vcd_api_version_supported))

    # Update the config dict with telemetry specific key value pairs
    store_telemetry_settings(config)

    return config


def _raise_error_if_amqp_not_supported(is_mqtt_used, default_api_version,
                                       logger=NULL_LOGGER):  # noqa: E501
    """Raise error if CSE is configured with AMQP but AMQP bus not supported.

    AMQP cannot be used if CSE 3.1 or above is configured with 10.3 or above.

    :param bool is_mqtt_used: boolean indicating if mqtt is used
    :param str default_api_version: max VCD API version used by CSE.
    :raises: AmqpError
    """
    if not is_mqtt_used and float(default_api_version) > \
            float(_MAX_API_VERSION_TO_RUN_CSE_WITH_AMQP_IN_NON_LEGACY_MODE):
        msg = f"Cannot use AMQP message bus when working with api version" \
            f" {default_api_version}. Please upgrade to MQTT."
        logger.error(msg)
        raise AmqpError(msg)


def _validate_amqp_config(amqp_dict, msg_update_callback=NullPrinter()):
    """Ensure that 'amqp' section of config is correct.

    Checks that 'amqp' section of config has correct keys and value types.
    Also ensures that connection to AMQP server is valid.

    :param dict amqp_dict: 'amqp' section of config file as a dict.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

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
                                           connection_attempts=3,
                                           retry_delay=2,
                                           socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        msg_update_callback.general(
            "Connected to AMQP server "
            f"({amqp_dict['host']}:{amqp_dict['port']})")
    except Exception as err:
        raise AmqpConnectionError(f"AMQP server error : {str(err)}")
    finally:
        if connection is not None:
            connection.close()


def _validate_vcd_and_vcs_config(vcd_dict,
                                 vcs,
                                 msg_update_callback=NullPrinter(),
                                 log_file=None,
                                 log_wire=False):
    """Ensure that 'vcd' and vcs' section of config are correct.

    Checks that
        * 'vcd' and 'vcs' section of config have correct keys and value types.
        * vCD and all registered VCs in vCD are accessible.
        * api version specified for vcd is supported by CSE.

    :param dict vcd_dict: 'vcd' section of config file as a dict.
    :param list vcs: 'vcs' section of config file as a list of dicts.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    :param str log_file: log_file for pyvcloud wire log.
    :param bool log_wire: If pyvcloud requests should be logged.

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
        msg_update_callback.general(
            'InsecureRequestWarning: Unverified HTTPS request is '
            'being made. Adding certificate verification is '
            'strongly advised.')
        requests.packages.urllib3.disable_warnings()

    client = None
    try:
        client = Client(vcd_dict['host'],
                        verify_ssl_certs=vcd_dict['verify'],
                        log_file=log_file,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        client.set_credentials(BasicLoginCredentials(vcd_dict['username'],
                                                     SYSTEM_ORG_NAME,
                                                     vcd_dict['password']))
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
            if not (hasattr(vcenter, 'IsConnected') and vcenter.IsConnected):
                msg = f"vCenter Server '{vc['name']}' not available"
                msg_update_callback.info(msg)
                continue
            vsphere_url = urlparse(vcenter.Url.text)
            vsphere_url_port = vsphere_url.port
            if vsphere_url_port:
                v = VSphere(vsphere_url.hostname, vc['username'],
                            vc['password'], vsphere_url.port)
            else:
                v = VSphere(vsphere_url.hostname, vc['username'],
                            vc['password'])
            v.connect()
            msg = f"Connected to vCenter Server '{vc['name']}' as " \
                f"'{vc['username']}' ({vsphere_url.hostname}"
            if vsphere_url_port:
                msg += f":{vsphere_url.port}"
            msg += ")"
            msg_update_callback.general(msg)
    finally:
        if client is not None:
            client.logout()


def _validate_broker_config(broker_dict,
                            legacy_mode=False,
                            msg_update_callback=NullPrinter(),
                            logger_debug=NULL_LOGGER):
    """Ensure that 'broker' section of config is correct.

    Checks that 'broker' section of config has correct keys and value
    types. Also checks that 'default_broker' property is a valid template.

    :param dict broker_dict: 'broker' section of config file as a dict.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises KeyError: if @broker_dict has missing or extra properties.
    :raises TypeError: if the value type for a @broker_dict property is
        incorrect.
    :raises ValueError: if 'ip_allocation_mode' is not 'dhcp' or 'pool'. Or
        if remote_template_cookbook_url is invalid.
    """
    check_keys_and_value_types(broker_dict, SAMPLE_BROKER_CONFIG['broker'],
                               location="config file 'broker' section",
                               msg_update_callback=msg_update_callback)
    valid_ip_allocation_modes = [
        'dhcp',
        'pool'
    ]
    if broker_dict['ip_allocation_mode'] not in valid_ip_allocation_modes:
        raise ValueError(f"IP allocation mode is "
                         f"'{broker_dict['ip_allocation_mode']}' when it "
                         f"should be either 'dhcp' or 'pool'")

    rtm = RemoteTemplateManager(remote_template_cookbook_url=broker_dict['remote_template_cookbook_url'],  # noqa: E501
                                legacy_mode=legacy_mode,
                                logger=logger_debug)

    remote_template_cookbook = rtm.get_filtered_remote_template_cookbook()

    if not remote_template_cookbook:
        raise Exception("Remote template cookbook is invalid.")


def _validate_pks_config_structure(pks_config,
                                   msg_update_callback=NullPrinter()):
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


def _validate_pks_config_data_integrity(pks_config,
                                        msg_update_callback=NullPrinter(),
                                        logger_debug=NULL_LOGGER,
                                        logger_wire=NULL_LOGGER):
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
                    raise ValueError(f"Unknown PKS account : {account} "
                                     f"referenced by Org : {org.get('name')} "
                                     f"in Section : {PKS_ORGS_SECTION_KEY}")

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

        uaa_client = UaaClient(pks_configuration.uaac_uri,
                               pks_configuration.username,
                               pks_configuration.secret,
                               proxy_uri=pks_configuration.proxy)
        token = uaa_client.getToken()

        if not token:
            raise ValueError(
                "Unable to connect to PKS server : "
                f"{pks_server.get('name')} ({pks_server.get('host')})")

        pks_configuration.token = token
        client = ApiClient(configuration=pks_configuration)

        if client:
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
        # server
        nsxt_client = NSXTClient(
            host=nsxt_server.get('host'),
            username=nsxt_server.get('username'),
            password=nsxt_server.get('password'),
            logger_debug=logger_debug,
            logger_wire=logger_wire,
            http_proxy=nsxt_server.get('proxy'),
            https_proxy=nsxt_server.get('proxy'),
            verify_ssl=nsxt_server.get('verify'))
        if not nsxt_client.test_connectivity():
            raise ValueError(
                "Unable to connect to NSX-T server : "
                f"{nsxt_server.get('name')} ({nsxt_server.get('host')})")

        msg_update_callback.general(
            f"Connected to NSX-T server ({nsxt_server.get('host')})")

        ipset_manager = IPSetManager(nsxt_client)
        if nsxt_server.get('nodes_ip_block_ids'):
            block_not_found = False
            ip_block_id = ''
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
            block_not_found = False
            ip_block_id = ''
            try:
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
