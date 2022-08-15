# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import importlib
import importlib.resources as pkg_resources
import json
import time

import pika
import pyvcloud.vcd.api_extension as api_extension
from pyvcloud.vcd.client import ApiVersion as vCDApiVersion
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import NSMAP
from pyvcloud.vcd.exceptions import AccessForbiddenException
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.role import Role
import pyvcloud.vcd.utils as pyvcloud_vcd_utils
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
import requests
import semantic_version

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.models as def_models
import container_service_extension.def_.schema_service as def_schema_svc
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as cse_exception
import container_service_extension.local_template_manager as ltm
from container_service_extension.logger import INSTALL_LOGGER
from container_service_extension.logger import INSTALL_WIRELOG_FILEPATH
from container_service_extension.logger import NULL_LOGGER
from container_service_extension.logger import SERVER_CLI_LOGGER
from container_service_extension.logger import SERVER_CLI_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_CLOUDAPI_WIRE_LOGGER
from container_service_extension.logger import SERVER_NSXT_WIRE_LOGGER
from container_service_extension.mqtt_extension_manager import \
    MQTTExtensionManager
from container_service_extension.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.nsxt.nsxt_client import NSXTClient
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
from container_service_extension.right_bundle_manager import RightBundleManager
import container_service_extension.server_constants as server_constants
import container_service_extension.shared_constants as shared_constants
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.telemetry.telemetry_utils import \
    store_telemetry_settings
import container_service_extension.template_builder as template_builder
from container_service_extension.user_context import UserContext
import container_service_extension.utils as utils
from container_service_extension.vcdbroker import get_all_clusters as get_all_cse_clusters # noqa: E501
from container_service_extension.vsphere_utils import populate_vsphere_list

API_FILTER_PATTERNS = [
    f'/api/{shared_constants.CSE_URL_FRAGMENT}',
    f'/api/{shared_constants.CSE_URL_FRAGMENT}/.*',
    f'/api/{shared_constants.PKS_URL_FRAGMENT}',
    f'/api/{shared_constants.PKS_URL_FRAGMENT}/.*',
]


def check_cse_installation(config, msg_update_callback=utils.NullPrinter()):
    """Ensure that CSE is installed on vCD according to the config file.

    Checks,
        1. AMQP exchange exists
        2. CSE is registered with vCD,
        3. CSE K8 catalog exists

    :param dict config: config yaml file as a dictionary
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises Exception: if CSE is not registered to vCD as an extension, or if
        specified catalog does not exist, or if specified template(s) do not
        exist.
    """
    msg_update_callback.info(
        "Validating CSE installation according to config file")
    err_msgs = []
    client = None
    try:
        log_filename = None
        log_wire = utils.str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = SERVER_CLI_WIRELOG_FILEPATH

        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            server_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)

        if utils.should_use_mqtt_protocol(config):
            _check_mqtt_extension_installation(client, msg_update_callback,
                                               err_msgs)
        else:
            _check_amqp_extension_installation(client, config,
                                               msg_update_callback, err_msgs)

        # check that catalog exists in vCD
        org_name = config['broker']['org']
        org = vcd_utils.get_org(client, org_name=org_name)
        catalog_name = config['broker']['catalog']
        if vcd_utils.catalog_exists(org, catalog_name):
            msg = f"Found catalog '{catalog_name}'"
            msg_update_callback.general(msg)
            SERVER_CLI_LOGGER.info(msg)
        else:
            msg = f"Catalog '{catalog_name}' not found"
            msg_update_callback.error(msg)
            SERVER_CLI_LOGGER.error(msg)
            err_msgs.append(msg)
    finally:
        if client:
            client.logout()

    if err_msgs:
        raise Exception(err_msgs)
    msg = "CSE installation is valid"
    msg_update_callback.general(msg)
    SERVER_CLI_LOGGER.info(msg)


def _check_amqp_extension_installation(client, config, msg_update_callback,
                                       err_msgs):
    """Check that AMQP exchange and api extension exists."""
    amqp = config['amqp']
    credentials = pika.PlainCredentials(amqp['username'],
                                        amqp['password'])
    parameters = pika.ConnectionParameters(amqp['host'], amqp['port'],
                                           amqp['vhost'], credentials,
                                           connection_attempts=3,
                                           retry_delay=2,
                                           socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        try:
            channel.exchange_declare(exchange=amqp['exchange'],
                                     exchange_type=server_constants.EXCHANGE_TYPE,  # noqa: E501
                                     durable=True,
                                     passive=True,
                                     auto_delete=False)
            msg = f"AMQP exchange '{amqp['exchange']}' exists"
            msg_update_callback.general(msg)
            SERVER_CLI_LOGGER.info(msg)
        except pika.exceptions.ChannelClosed:
            msg = f"AMQP exchange '{amqp['exchange']}' does not exist"
            msg_update_callback.error(msg)
            SERVER_CLI_LOGGER.error(msg)
            err_msgs.append(msg)
    except Exception:  # TODO() replace raw exception with specific
        msg = f"Could not connect to AMQP exchange '{amqp['exchange']}'"
        msg_update_callback.error(msg)
        SERVER_CLI_LOGGER.error(msg)
        err_msgs.append(msg)
    finally:
        if connection is not None:
            connection.close()

    # check that CSE is registered to vCD correctly
    ext = api_extension.APIExtension(client)
    try:
        cse_info = ext.get_extension(server_constants.CSE_SERVICE_NAME,
                                     namespace=server_constants.CSE_SERVICE_NAMESPACE)  # noqa: E501
        rkey_matches = cse_info['routingKey'] == amqp['routing_key']
        exchange_matches = cse_info['exchange'] == amqp['exchange']
        if not rkey_matches or not exchange_matches:
            msg = "CSE is registered as an extension, but the " \
                  "extension settings on vCD are not the same as " \
                  "config settings."
            if not rkey_matches:
                msg += f"\nvCD-CSE routing key: " \
                       f"{cse_info['routingKey']}" \
                       f"\nCSE config routing key: " \
                       f"{amqp['routing_key']}"
            if not exchange_matches:
                msg += f"\nvCD-CSE exchange: {cse_info['exchange']}" \
                       f"\nCSE config exchange: {amqp['exchange']}"
            msg_update_callback.info(msg)
            SERVER_CLI_LOGGER.info(msg)
            err_msgs.append(msg)
        if cse_info['enabled'] == 'true':
            msg = "CSE on vCD is currently enabled"
            msg_update_callback.general(msg)
            SERVER_CLI_LOGGER.info(msg)
        else:
            msg = "CSE on vCD is currently disabled"
            msg_update_callback.info(msg)
            SERVER_CLI_LOGGER.info(msg)
    except MissingRecordException:
        msg = "CSE is not registered to vCD"
        msg_update_callback.error(msg)
        SERVER_CLI_LOGGER.error(msg)
        err_msgs.append(msg)


def _check_mqtt_extension_installation(client, msg_update_callback, err_msgs):
    """Check that MQTT extension exists with its API filter."""
    mqtt_ext_manager = MQTTExtensionManager(client)
    mqtt_ext_info = mqtt_ext_manager.get_extension_info(
        ext_name=server_constants.CSE_SERVICE_NAME,
        ext_version=server_constants.MQTT_EXTENSION_VERSION,
        ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
    if mqtt_ext_info:
        # Check MQTT api filter status
        ext_urn_id = mqtt_ext_info['ext_urn_id']
        ext_uuid = mqtt_ext_manager.get_extension_uuid(ext_urn_id)
        api_filters_status = mqtt_ext_manager.check_api_filters_setup(
            ext_uuid, API_FILTER_PATTERNS)
        if not api_filters_status:
            msg = f"Could not find MQTT API Filter: " \
                  f"{server_constants.MQTT_API_FILTER_PATTERN}"
            msg_update_callback.error(msg)
            SERVER_CLI_LOGGER.error(msg)
            err_msgs.append(msg)
        else:
            msg = "MQTT extension and API filters found"
            msg_update_callback.general(msg)
            SERVER_CLI_LOGGER.info(msg)
    else:
        msg = "Could not find MQTT Extension"
        msg_update_callback.error(msg)
        SERVER_CLI_LOGGER.error(msg)
        err_msgs.append(msg)


def _construct_cse_extension_description(target_vcd_api_version):
    """."""
    cse_version = utils.get_installed_cse_version()
    description = f"cse-{cse_version},vcd_api-{target_vcd_api_version}"
    return description


def parse_cse_extension_description(sys_admin_client, is_mqtt_extension):
    """Parse CSE extension description.

    :param Client sys_admin_client: system admin vcd client
    :param bool is_mqtt_extension: whether or not the extension is MQTT

    :raises: (when using MQTT) HTTPError if there is an error when making the
        GET request for the extension info
    """
    description = ''
    if is_mqtt_extension:
        mqtt_ext_manager = MQTTExtensionManager(sys_admin_client)
        mqtt_ext_info = mqtt_ext_manager.get_extension_info(
            ext_name=server_constants.CSE_SERVICE_NAME,
            ext_version=server_constants.MQTT_EXTENSION_VERSION,
            ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
        if mqtt_ext_info:
            description = \
                mqtt_ext_info[server_constants.MQTTExtKey.EXT_DESCRIPTION]
    else:
        ext = api_extension.APIExtension(sys_admin_client)
        ext_dict = ext.get_extension_info(
            server_constants.CSE_SERVICE_NAME,
            namespace=server_constants.CSE_SERVICE_NAMESPACE)
        ext_xml = ext.get_extension_xml(ext_dict['id'])
        child = ext_xml.find(f"{{{NSMAP['vcloud']}}}Description")
        if child:
            description = child.text

    cse_version = server_constants.UNKNOWN_CSE_VERSION
    vcd_api_version = server_constants.UNKNOWN_VCD_API_VERSION
    tokens = description.split(",")
    if len(tokens) == 2:
        cse_tokens = tokens[0].split("-")
        if len(cse_tokens) == 2:
            cse_version = semantic_version.Version(cse_tokens[1])
        vcd_api_tokens = tokens[1].split("-")
        if len(vcd_api_tokens) == 2:
            vcd_api_version = vcd_api_tokens[1]
    return cse_version, vcd_api_version


def install_cse(config_file_name, config, skip_template_creation,
                ssh_key, retain_temp_vapp, pks_config_file_name=None,
                skip_config_decryption=False,
                msg_update_callback=utils.NullPrinter()):
    """Handle logistics for CSE installation.

    Handles decision making for configuring AMQP exchange/settings,
    defined entity schema registration for vCD api version >= 35,
    extension registration, catalog setup and template creation.

    Also records telemetry data on installation details.

    :param str config_file_name: config file name.
    :param dict config: content of the CSE config file.
    :param bool skip_template_creation: If True, skip creating the templates.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param str pks_config_file_name: pks config file name.
    :param bool skip_config_decryption: do not decrypt the config file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises cse_exception.AmqpError: (when using AMQP) if AMQP exchange
        could not be created.
    :raises requests.exceptions.HTTPError: (when using MQTT) if there is an
        issue in retrieving MQTT info or in setting up the MQTT components
    """
    populate_vsphere_list(config['vcs'])

    msg = f"Installing CSE on vCloud Director using config file " \
          f"'{config_file_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    client = None
    try:
        # Telemetry - Construct telemetry data
        telemetry_data = {
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption),  # noqa: E501
            PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(pks_config_file_name),  # noqa: E501
            PayloadKey.WERE_TEMPLATES_SKIPPED: bool(skip_template_creation),  # noqa: E501
            PayloadKey.WAS_TEMP_VAPP_RETAINED: bool(retain_temp_vapp),  # noqa: E501
            PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(ssh_key)  # noqa: E501
        }

        # Telemetry - Record detailed telemetry data on install
        record_user_action_details(CseOperation.SERVICE_INSTALL,
                                   telemetry_data,
                                   telemetry_settings=config['service']['telemetry'])  # noqa: E501

        log_filename = None
        log_wire = utils.str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = INSTALL_WIRELOG_FILEPATH

        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            server_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        ext_type = _get_existing_extension_type(client)
        if ext_type != server_constants.ExtensionType.NONE:
            ext_found_msg = f"{ext_type} extension found. Use `cse upgrade` " \
                            f"instead of 'cse install'."
            INSTALL_LOGGER.error(ext_found_msg)
            raise Exception(ext_found_msg)

        # register cse def schema on VCD
        _register_def_schema(client=client, config=config,
                             msg_update_callback=msg_update_callback,
                             log_wire=log_wire)

        # set up placement policies for all types of clusters
        is_tkg_plus_enabled = utils.is_tkg_plus_enabled(config=config)
        is_tkg_m_enabled = utils.is_tkg_m_enabled(config=config)
        _setup_placement_policies(
            client=client,
            policy_list=shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES,
            is_tkg_plus_enabled=is_tkg_plus_enabled,
            is_tkg_m_enabled=is_tkg_m_enabled,
            msg_update_callback=msg_update_callback,
            log_wire=log_wire)

        # set up cse catalog
        org = vcd_utils.get_org(client, org_name=config['broker']['org'])
        vcd_utils.create_and_share_catalog(
            org, config['broker']['catalog'], catalog_desc='CSE templates',
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)

        if skip_template_creation:
            msg = "Skipping creation of templates."
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)
        else:
            # install all templates
            _install_all_templates(
                client=client,
                config=config,
                force_create=False,
                retain_temp_vapp=retain_temp_vapp,
                ssh_key=retain_temp_vapp,
                msg_update_callback=msg_update_callback)

        # if it's a PKS setup, setup NSX-T constructs
        if config.get('pks_config'):
            configure_nsxt_for_cse(
                nsxt_servers=config['pks_config']['nsxt_servers'],
                log_wire=log_wire,
                msg_update_callback=msg_update_callback
            )

        # Setup extension based on message bus protocol
        if utils.should_use_mqtt_protocol(config):
            _register_cse_as_mqtt_extension(client,
                                            config['vcd']['api_version'],
                                            msg_update_callback)
        else:
            # create amqp exchange if it doesn't exist
            amqp = config['amqp']
            _create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                                  amqp['vhost'], amqp['username'],
                                  amqp['password'],
                                  msg_update_callback=msg_update_callback)

            # register cse as an api extension to vCD
            _register_cse_as_amqp_extension(
                client=client,
                routing_key=amqp['routing_key'],
                exchange=amqp['exchange'],
                target_vcd_api_version=config['vcd']['api_version'],
                msg_update_callback=msg_update_callback)

            # register rights to vCD
            # TODO() should also remove rights when unregistering CSE
            _register_right(client,
                            right_name=server_constants.CSE_NATIVE_DEPLOY_RIGHT_NAME,  # noqa: E501
                            description=server_constants.CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION,  # noqa: E501
                            category=server_constants.CSE_NATIVE_DEPLOY_RIGHT_CATEGORY,  # noqa: E501
                            bundle_key=server_constants.CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY,  # noqa: E501
                            msg_update_callback=msg_update_callback)
            _register_right(client,
                            right_name=server_constants.CSE_PKS_DEPLOY_RIGHT_NAME,  # noqa: E501
                            description=server_constants.CSE_PKS_DEPLOY_RIGHT_DESCRIPTION,  # noqa: E501
                            category=server_constants.CSE_PKS_DEPLOY_RIGHT_CATEGORY,  # noqa: E501
                            bundle_key=server_constants.CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY,  # noqa: E501
                            msg_update_callback=msg_update_callback)

        msg = "Installed CSE successfully."
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # Since we use CSE extension id as our telemetry instance_id, the
        # validated config won't have the instance_id yet. Now that CSE has
        # been registered as an extension, we should update the telemetry
        # config with the correct instance_id
        if config['service']['telemetry']['enable']:
            store_telemetry_settings(config)

        # Telemetry - Record successful install action
        record_user_action(CseOperation.SERVICE_INSTALL,
                           telemetry_settings=config['service']['telemetry'])
    except Exception:
        msg_update_callback.error(
            "CSE Installation Error. Check CSE install logs")
        INSTALL_LOGGER.error("CSE Installation Error", exc_info=True)
        # Telemetry - Record failed install action
        record_user_action(CseOperation.SERVICE_INSTALL,
                           status=OperationStatus.FAILED,
                           telemetry_settings=config['service']['telemetry'])
        raise  # TODO() need installation relevant exceptions for rollback
    finally:
        if client is not None:
            client.logout()


def _get_existing_extension_type(client):
    """Get the existing extension type.

    Only one extension type will be returned because having two extensions
        is prevented in install_cse.

    ::param Client client: client used to install cse server components

    :return: the current extension type: ExtensionType.MQTT, AMQP, or NONE
    :rtype: str
    """
    # If API version meets minimum MQTT API version requirement,
    # check for MQTT extension
    if float(client.get_api_version()) >= \
            server_constants.MQTT_MIN_API_VERSION:
        try:
            mqtt_ext_manager = MQTTExtensionManager(client)
            ext_info = mqtt_ext_manager.get_extension_info(
                ext_name=server_constants.CSE_SERVICE_NAME,
                ext_version=server_constants.MQTT_EXTENSION_VERSION,
                ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
            if ext_info:
                return server_constants.ExtensionType.MQTT
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code != requests.codes.not_found:
                raise

    # Check for AMQP extension
    try:
        amqp_ext = api_extension.APIExtension(client)
        amqp_ext.get_extension_info(
            server_constants.CSE_SERVICE_NAME,
            namespace=server_constants.CSE_SERVICE_NAMESPACE)
        return server_constants.ExtensionType.AMQP
    except MissingRecordException:
        pass

    return server_constants.ExtensionType.NONE


def _register_cse_as_mqtt_extension(client, target_vcd_api_version,
                                    msg_update_callback):
    """Install the MQTT extension and api filter.

    :param Client client: client used to install cse server components
    :param str target_vcd_api_version: the desired vcd api version
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises requests.exceptions.HTTPError: if the MQTT extension and api filter
        were not set up correctly
    """
    mqtt_ext_manager = MQTTExtensionManager(client)
    description = _construct_cse_extension_description(
        target_vcd_api_version)
    ext_info = mqtt_ext_manager.setup_extension(
        ext_name=server_constants.CSE_SERVICE_NAME,
        ext_version=server_constants.MQTT_EXTENSION_VERSION,
        ext_vendor=server_constants.MQTT_EXTENSION_VENDOR,
        description=description)
    ext_uuid = mqtt_ext_manager.get_extension_uuid(
        ext_info['ext_urn_id'])
    _ = mqtt_ext_manager.setup_api_filter_patterns(ext_uuid,
                                                   API_FILTER_PATTERNS)

    mqtt_msg = 'MQTT extension is ready'
    msg_update_callback.general(mqtt_msg)
    INSTALL_LOGGER.info(mqtt_msg)


def _create_amqp_exchange(exchange_name, host, port, vhost,
                          username, password,
                          msg_update_callback=utils.NullPrinter()):
    """Create the specified AMQP exchange if it does not exist.

    If specified AMQP exchange exists already, does nothing.

    :param str exchange_name: The AMQP exchange name to check for or create.
    :param str host: AMQP host name.
    :param str password: AMQP password.
    :param int port: AMQP port number.
    :param str username: AMQP username.
    :param str vhost: AMQP vhost.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises cse_exception.AmqpError: if AMQP exchange could not be created.
    """
    msg = f"Checking for AMQP exchange '{exchange_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, port, vhost, credentials,
                                           connection_attempts=3,
                                           retry_delay=2, socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name,
                                 exchange_type=server_constants.EXCHANGE_TYPE,
                                 durable=True, auto_delete=False)
    except Exception as err:
        msg = f"Cannot create AMQP exchange '{exchange_name}'"
        msg_update_callback.error(msg)
        INSTALL_LOGGER.error(msg, exc_info=True)
        raise cse_exception.AmqpError(msg, str(err))
    finally:
        if connection is not None:
            connection.close()
    msg = f"AMQP exchange '{exchange_name}' is ready"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _deregister_cse_mqtt_extension(client,
                                   msg_update_callback=utils.NullPrinter()):
    mqtt_ext_manager = MQTTExtensionManager(client)
    mqtt_ext_info = mqtt_ext_manager.get_extension_info(
        ext_name=server_constants.CSE_SERVICE_NAME,
        ext_version=server_constants.MQTT_EXTENSION_VERSION,
        ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
    ext_urn_id = mqtt_ext_info[server_constants.MQTTExtKey.EXT_URN_ID]
    mqtt_ext_manager.delete_extension(
        ext_name=server_constants.CSE_SERVICE_NAME,
        ext_version=server_constants.MQTT_EXTENSION_VERSION,
        ext_vendor=server_constants.MQTT_EXTENSION_VENDOR,
        ext_urn_id=ext_urn_id)

    msg = f"Deleted MQTT extension '{server_constants.CSE_SERVICE_NAME}'"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _deregister_cse_amqp_extension(client,
                                   msg_update_callback=utils.NullPrinter()):
    """Deregister CSE AMQP extension from VCD."""
    ext = api_extension.APIExtension(client)
    ext.remove_all_api_filters_from_service(
        name=server_constants.CSE_SERVICE_NAME,
        namespace=server_constants.CSE_SERVICE_NAMESPACE)
    ext.delete_extension(name=server_constants.CSE_SERVICE_NAME,
                         namespace=server_constants.CSE_SERVICE_NAMESPACE)
    msg = "Successfully de-registered CSE AMQP extension from VCD"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _register_cse_as_amqp_extension(client, routing_key, exchange,
                                    target_vcd_api_version,
                                    msg_update_callback=utils.NullPrinter()):
    """Register CSE on vCD.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.client.Client client:
    :param str routing_key:
    :param str exchange:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    ext = api_extension.APIExtension(client)

    vcd_api_versions = client.get_supported_versions_list()
    if target_vcd_api_version not in vcd_api_versions:
        raise ValueError(f"Target VCD API version '{target_vcd_api_version}' "
                         f" is not in supported versions: {vcd_api_versions}")
    description = _construct_cse_extension_description(target_vcd_api_version)

    # No need to check for existing extension because the calling function
    # (install_cse) already handles checking for an existing extension
    ext.add_extension(
        server_constants.CSE_SERVICE_NAME,
        server_constants.CSE_SERVICE_NAMESPACE,
        routing_key,
        exchange,
        API_FILTER_PATTERNS,
        description=description)

    msg = f"Registered {server_constants.CSE_SERVICE_NAME} as an API extension in vCD" # noqa: E501
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _update_user_role_with_right_bundle(right_bundle_name,
                                        client: Client,
                                        msg_update_callback=utils.NullPrinter(), # noqa: E501
                                        logger_debug=NULL_LOGGER,
                                        log_wire=False):
    """Add defined entity rights to user's role.

    This method should only be called on valid configurations.
    In order to call this function, caller has to make sure that the
    contextual defined entity is already created inside VCD and corresponding
    right-bundle exists in VCD.
    The defined entity right bundle is created by VCD at the time of defined
    entity creation, dynamically. Hence, it doesn't exist before-hand
    (when user initiated the operation).
    :param str right_bundle_name:
    :param pyvcloud.vcd.client.Client client:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    :param bool log_wire: wire logging enabled

    :rtype: bool

    :return: result of operation. If the rights were added to user's role or
     not
    """
    # Only a user from System Org can execute this function
    vcd_utils.raise_error_if_user_not_from_system_org(client)

    logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER if log_wire else NULL_LOGGER
    cloudapi_client = \
        vcd_utils.get_cloudapi_client_from_vcd_client(client=client,
                                                      logger_debug=logger_debug, # noqa: E501
                                                      logger_wire=logger_wire) # noqa: E501

    # Determine role name for the user
    user_context = UserContext(client, cloudapi_client)
    role_name = user_context.role

    # Given that this user is sysadmin, Org must be System
    # If its not, we should receive an exception during one of the below
    # operations
    system_org = Org(client, resource=client.get_org())

    # Using the Org, determine Role object (using Role-name we identified)
    role_record = system_org.get_role_record(role_name)
    role_record_read_only = utils.str_to_bool(role_record.get('isReadOnly'))
    if role_record_read_only:
        msg = "User has predefined non editable role. Not adding native entitlement rights." # noqa: E501
        msg_update_callback.general(msg)
        return False

    # Determine the rights necessary from rights bundle
    # It is assumed that user already has "View Rights Bundle" Right
    rbm = RightBundleManager(client, log_wire, msg_update_callback)
    try:
        native_def_rights = \
            rbm.get_rights_for_right_bundle(right_bundle_name)
    except Exception as err:
        msg = "Right bundle " + str(right_bundle_name) + " doesn't exist"
        msg_update_callback.general_no_color(msg)
        msg_update_callback.error(str(err))
        return False

    # Get rights as a list of right-name strings
    rights = []
    for right_record in native_def_rights.get("values"):
        rights.append(right_record["name"])

    try:
        # Add rights to the Role
        role_obj = Role(client, resource=system_org.get_role_resource(role_name)) # noqa: E501
        role_obj.add_rights(rights, system_org)
    except AccessForbiddenException as err:
        msg = "User doesn't have permission to edit Roles."
        msg_update_callback.error(msg)
        msg_update_callback.error(str(err))
        raise err

    msg = "Updated user-role: " + str(role_name) + " with Rights-bundle: " + \
        str(right_bundle_name)
    msg_update_callback.general(msg)
    logger_debug.info(msg)

    return True


def _update_user_role_with_necessary_right_bundles(
        client: Client,
        msg_update_callback=utils.NullPrinter(),
        logger_debug=NULL_LOGGER,
        log_wire=False):
    """Add necessary rights from right bundles to user's role.

    As of now, CSE admin user requires:
        Native Defined Entity Right Bundle
        TKG Defined Entity Right Bundle

    :param pyvcloud.vcd.client.Client  : client
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    :param logging.Logger logger_debug:
    :param bool log_wire: wire logging enabled

    :rtype: bool

    :return: result of operation. If the rights from any right bundles
    were added to user's role or not
    """
    try:
        _update_user_role_with_right_bundle(
            def_utils.DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE,
            client=client,
            msg_update_callback=msg_update_callback,
            logger_debug=logger_debug,
            log_wire=log_wire)
    except Exception:
        msg = "Error Adding Native Def Entity Rights in User Role"
        msg_update_callback.error(msg)
        logger_debug.error(msg, exc_info=True)
        raise

    try:
        _update_user_role_with_right_bundle(
            def_utils.DEF_TKG_ENTITY_TYPE_RIGHT_BUNDLE,
            client=client,
            msg_update_callback=msg_update_callback,
            logger_debug=logger_debug,
            log_wire=log_wire)
    except Exception as err:
        # TKG Def Entity Rights Bundle might not be present in VCD always
        # (e.g. VCD 10.1) so ignore the error and move on
        msg = "Error Adding TKG Def Entity Rights in User Role" + str(err)
        msg_update_callback.general_no_color(msg)
        logger_debug.error(msg, exc_info=True)


def _register_def_schema(client: Client,
                         config=None,
                         update_schema=False,
                         msg_update_callback=utils.NullPrinter(),
                         log_wire=False):
    """Register defined entity interface and defined entity type.

    If vCD api version is >= 35, register the vCD api version based
    defined entity interface and defined entity type. Read the schema present
    in the location dictated by api version to register the
    defined entity type.

    :param pyvcloud.vcd.client.Client client:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    :param bool log_wire: wire logging enabled
    """
    if config is None:
        config = {}
    msg = "Registering defined entity schema"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)
    logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER if log_wire else NULL_LOGGER
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(client=client, # noqa: E501
                                                                    logger_debug=INSTALL_LOGGER, # noqa: E501
                                                                    logger_wire=logger_wire) # noqa: E501
    schema_file = None
    try:
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
        keys_map = def_utils.MAP_API_VERSION_TO_KEYS[float(client.get_api_version())] # noqa: E501
        defKey = def_utils.DefKey
        kubernetes_interface = def_models.\
            DefInterface(name=keys_map[defKey.INTERFACE_NAME],
                         vendor=keys_map[defKey.INTERFACE_VENDOR],
                         nss=keys_map[defKey.INTERFACE_NSS],
                         version=keys_map[defKey.INTERFACE_VERSION], # noqa: E501
                         readonly=False)
        try:
            # k8s interface should always be present
            schema_svc.get_interface(kubernetes_interface.get_id())
        except cse_exception.DefSchemaServiceError:
            msg = "Failed to obtain built-in defined entity interface " \
                  f"{keys_map[defKey.INTERFACE_NAME]}"
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)
            raise

        schema_module = importlib.import_module(
            f'{def_utils.DEF_SCHEMA_DIRECTORY}.{keys_map[defKey.ENTITY_TYPE_SCHEMA_VERSION]}') # noqa: E501
        schema_file = pkg_resources.open_text(schema_module, def_utils.DEF_ENTITY_TYPE_SCHEMA_FILE) # noqa: E501
        native_entity_type = def_models.\
            DefEntityType(name=keys_map[defKey.ENTITY_TYPE_NAME],
                          description='',
                          vendor=keys_map[defKey.ENTITY_TYPE_VENDOR],
                          nss=keys_map[defKey.ENTITY_TYPE_NSS],
                          version=keys_map[defKey.ENTITY_TYPE_VERSION],
                          schema=json.load(schema_file),
                          interfaces=[kubernetes_interface.get_id()],
                          readonly=False)

        try:
            current_native_entity_type = \
                schema_svc.get_entity_type(native_entity_type.get_id())
            if update_schema:
                updated_native_entity_type = def_models.DefEntityType(
                    id=current_native_entity_type.id,
                    name=native_entity_type.name, # updated
                    description=current_native_entity_type.description,
                    vendor=current_native_entity_type.vendor,
                    nss=current_native_entity_type.nss,
                    version=current_native_entity_type.version,
                    schema=native_entity_type.schema, # updated
                    interfaces=current_native_entity_type.interfaces,
                    readonly=current_native_entity_type.readonly)
                msg = "Updating existing CSE native Defined Entity Type."
                schema_svc.update_entity_type(updated_native_entity_type)
            else:
                msg = "Skipping creation of Defined Entity Type. Defined Entity Type already exists."  # noqa: E501
        except cse_exception.DefSchemaServiceError:
            # TODO handle this part only if the entity type was not found
            native_entity_type = schema_svc.create_entity_type(native_entity_type)  # noqa: E501
            msg = "Successfully registered defined entity type\n"

            entity_svc = def_entity_svc.DefEntityService(cloudapi_client)
            entity_svc.create_acl_for_entity(
                native_entity_type.get_id(),
                grant_type=server_constants.AclGrantType.MembershipACLGrant,
                access_level_id=server_constants.AclAccessLevelId.AccessLevelReadWrite, # noqa: E501
                member_id=server_constants.AclMemberId.SystemOrgId)
            msg += "Successfully added ReadWrite ACL for native defined entity to System Org" # noqa: E501

        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # Update user's role with right bundle associated with all necessary
        # right bundles
        _update_user_role_with_necessary_right_bundles(
            client=client,
            msg_update_callback=msg_update_callback,
            logger_debug=INSTALL_LOGGER,
            log_wire=log_wire)

        # Given that Rights for the current user have been updated, CSE
        # should logout the user and login again.
        # This will make sure that SecurityContext object in VCD is
        # recreated and newly added rights are effective for the user.
        client.logout()
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            server_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)

    except cse_exception.DefNotSupportedException:
        msg = "Skipping defined entity type and defined entity interface" \
              " registration"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
    except (ImportError, ModuleNotFoundError, FileNotFoundError) as e:
        msg = f"Error while loading defined entity schema: {str(e)}"
        msg_update_callback.error(msg)
        INSTALL_LOGGER.error(msg)
        raise e
    except Exception as e:
        msg = f"Error occurred while registering defined entity schema: {str(e)}" # noqa: E501
        msg_update_callback.error(msg)
        INSTALL_LOGGER.error(msg)
        raise e
    finally:
        try:
            schema_file.close()
        except Exception:
            pass


def _register_right(client, right_name, description, category, bundle_key,
                    msg_update_callback=utils.NullPrinter()):
    """Register a right for CSE.

    :param pyvcloud.vcd.client.Client client:
    :param str right_name: the name of the new right to be registered.
    :param str description: brief description about the new right.
    :param str category: add the right in existing categories in
        vCD Roles and Rights or specify a new category name.
    :param str bundle_key: is used to identify the right name and change
        its value to different languages using localization bundle.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises BadRequestException: if a right with given name already
        exists in vCD.
    """
    ext = api_extension.APIExtension(client)
    # Since the client is a sys admin, org will hold a reference to System org
    system_org = Org(client, resource=client.get_org())
    try:
        right_name_in_vcd = f"{{{server_constants.CSE_SERVICE_NAME}}}:{right_name}" # noqa: E501
        # TODO(): When org.get_right_record() is moved outside the org scope in
        # pyvcloud, update the code below to adhere to the new method names.
        system_org.get_right_record(right_name_in_vcd)
        msg = f"Right: {right_name} already exists in vCD"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
        # Presence of the right in vCD is not a guarantee that the right will
        # be assigned to system org too.
        rights_in_system = system_org.list_rights_of_org()
        for dikt in rights_in_system:
            # TODO(): When localization support comes in, this check should be
            # ditched for a better one.
            if dikt['name'] == right_name_in_vcd:
                msg = f"Right: {right_name} already assigned to System " \
                    f"organization."
                msg_update_callback.general(msg)
                INSTALL_LOGGER.info(msg)
                return
        # Since the right is not assigned to system org, we need to add it.
        msg = f"Assigning Right: {right_name} to System organization."
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
        system_org.add_rights((right_name_in_vcd,))
    except EntityNotFoundException:
        # Registering a right via api extension end point, auto assigns it to
        # System org.
        msg = f"Registering Right: {right_name} in vCD"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
        ext.add_service_right(
            right_name, server_constants.CSE_SERVICE_NAME,
            server_constants.CSE_SERVICE_NAMESPACE, description,
            category, bundle_key)


def _setup_placement_policies(client,
                              policy_list,
                              is_tkg_plus_enabled,
                              is_tkg_m_enabled,
                              msg_update_callback=utils.NullPrinter(),
                              log_wire=False):
    """Create placement policies for each cluster type.

    Create the global pvdc compute policy if not present and create placement
    policy for each policy in the policy list. This should be done only for
    vcd api version >= 35 (zeus)

    :parma client vcdClient.Client
    :param policy_list str[]
    """
    msg = "Setting up placement policies for cluster types"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)
    cpm = \
        compute_policy_manager.ComputePolicyManager(client, log_wire=log_wire)
    try:
        try:
            pvdc_compute_policy = \
                compute_policy_manager.get_cse_pvdc_compute_policy(
                    cpm,
                    server_constants.CSE_GLOBAL_PVDC_COMPUTE_POLICY_NAME)
            msg = "Skipping creation of global PVDC compute policy. Policy already exists" # noqa: E501
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
        except EntityNotFoundException:
            msg = "Creating global PVDC compute policy"
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
            pvdc_compute_policy = \
                compute_policy_manager.add_cse_pvdc_compute_policy(
                    cpm,
                    server_constants.CSE_GLOBAL_PVDC_COMPUTE_POLICY_NAME,
                    server_constants.CSE_GLOBAL_PVDC_COMPUTE_POLICY_DESCRIPTION)  # noqa: E501

        for policy_name in policy_list:
            if not is_tkg_plus_enabled and \
                    policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
                continue
            if not is_tkg_m_enabled and \
                    policy_name == shared_constants.TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
                continue
            try:
                compute_policy_manager.get_cse_vdc_compute_policy(
                    cpm,
                    policy_name,
                    is_placement_policy=True)
                msg = f"Skipping creation of VDC placement policy '{policy_name}'. Policy already exists" # noqa: E501
                msg_update_callback.general(msg)
                INSTALL_LOGGER.info(msg)
            except EntityNotFoundException:
                msg = f"Creating placement policy '{policy_name}'"
                msg_update_callback.general(msg)
                INSTALL_LOGGER.info(msg)
                compute_policy_manager.add_cse_vdc_compute_policy(
                    cpm,
                    policy_name,
                    pvdc_compute_policy_id=pvdc_compute_policy['id'])
    except cse_exception.GlobalPvdcComputePolicyNotSupported:
        msg = "Global PVDC compute policies are not supported." \
              "Skipping creation of placement policy."
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)


def _assign_placement_policies_to_existing_templates(
        client,
        config,
        is_tkg_plus_enabled,
        is_tkg_m_enabled,
        log_wire=False,
        msg_update_callback=utils.NullPrinter()):
    """Read existing templates and assign respective placement policies.

    Read metadata of existing templates, get the value for the 'kind' metadata,
    assign the respective placement policy to the template.

    :param vcdClient.Client client:
    :param dict config: content of the CSE config file.
    :param bool is_tkg_plus_enabled:
    :param bool is_tkg_m_enabled:
    :param bool log_wire:
    :param utils.ConsoleMessagePrinter msg_update_callback:
    """
    # NOTE: In CSE 3.0 if `enable_tkg_plus` flag in the config is set to false,
    # And there is an existing TKG+ template, throw an exception on the console
    # and fail the upgrade.
    msg = 'Assigning placement policies to existing templates.'
    INSTALL_LOGGER.debug(msg)
    msg_update_callback.general(msg)

    catalog_name = config['broker']['catalog']
    org_name = config['broker']['org']
    all_templates = \
        ltm.get_all_k8s_local_template_definition(
            client,
            catalog_name=catalog_name,  # noqa: E501
            org_name=org_name,
            logger_debug=INSTALL_LOGGER)
    for template in all_templates:
        kind = template.get(server_constants.LocalTemplateKey.KIND)
        catalog_item_name = ltm.get_revisioned_template_name(
            template[server_constants.RemoteTemplateKey.NAME],
            template[server_constants.RemoteTemplateKey.REVISION])
        msg = f"Processing template {catalog_item_name}"
        INSTALL_LOGGER.debug(msg)
        msg_update_callback.general(msg)
        if not kind:
            # skip processing the template if kind value is not present
            msg = f"Skipping processing of template {catalog_item_name}. Template kind not found"  # noqa: E501
            INSTALL_LOGGER.debug(msg)
            msg_update_callback.general(msg)
            continue
        if kind == shared_constants.ClusterEntityKind.TKG_PLUS.value and \
                not is_tkg_plus_enabled:
            msg = "Found a TKG+ template. However TKG+ is not enabled on " \
                  "CSE. Please enable TKG+ for CSE via config file and " \
                  "re-run `cse upgrade` to process these template(s)."
            INSTALL_LOGGER.error(msg)
            raise cse_exception.CseUpgradeError(msg)
        if kind == shared_constants.ClusterEntityKind.TKG_M.value and \
                not is_tkg_m_enabled:
            msg = "Found a TKGm template. However TKGm is not enabled on " \
                  "CSE. Please enable TKGm for CSE via config file and " \
                  "re-run `cse upgrade` to process these template(s)."
            INSTALL_LOGGER.error(msg)
            raise cse_exception.CseUpgradeError(msg)

        placement_policy_name = \
            shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP[kind]  # noqa: E501
        template_builder.assign_placement_policy_to_template(
            client,
            placement_policy_name,
            catalog_name,
            catalog_item_name,
            org_name,
            logger=INSTALL_LOGGER,
            log_wire=log_wire,
            msg_update_callback=msg_update_callback)


def _install_all_templates(
        client, config, force_create, retain_temp_vapp,
        ssh_key, msg_update_callback=utils.NullPrinter()):
    # read remote template cookbook, download all scripts
    rtm = RemoteTemplateManager(
        remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'], # noqa: E501
        logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)
    remote_template_cookbook = rtm.get_remote_template_cookbook()

    # create all templates defined in cookbook
    for template in remote_template_cookbook['templates']:
        _install_single_template(
            client=client,
            remote_template_manager=rtm,
            template=template,
            org_name=config['broker']['org'],
            vdc_name=config['broker']['vdc'],
            catalog_name=config['broker']['catalog'],
            network_name=config['broker']['network'],
            ip_allocation_mode=config['broker']['ip_allocation_mode'],
            storage_profile=config['broker']['storage_profile'],
            force_update=force_create,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=ssh_key,
            is_tkg_plus_enabled=utils.is_tkg_plus_enabled(config),
            is_tkg_m_enabled=utils.is_tkg_m_enabled(config),
            msg_update_callback=msg_update_callback)


def install_template(template_name, template_revision, config_file_name,
                     config, force_create, retain_temp_vapp, ssh_key,
                     skip_config_decryption=False,
                     msg_update_callback=utils.NullPrinter()):
    """Install a particular template in CSE.

    If template_name and revision are wild carded to *, all templates defined
    in remote template cookbook will be installed.

    :param str template_name:
    :param str template_revision:
    :param str config_file_name: config file name.
    :param dict config: content of the CSE config file.
    :param bool force_create: if True and template already exists in vCD,
        overwrites existing template.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param bool skip_config_decryption: do not decrypt the config file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    populate_vsphere_list(config['vcs'])

    msg = f"Installing template '{template_name}' at revision " \
          f"'{template_revision}' on vCloud Director using config file " \
          f"'{config_file_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    client = None
    try:
        # Telemetry data construction
        cse_params = {
            PayloadKey.TEMPLATE_NAME: template_name,
            PayloadKey.TEMPLATE_REVISION: template_revision,
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption),
            PayloadKey.WERE_TEMPLATES_FORCE_UPDATED: bool(force_create),
            PayloadKey.WAS_TEMP_VAPP_RETAINED: bool(retain_temp_vapp),
            PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(ssh_key)
        }
        # Record telemetry data
        record_user_action_details(
            cse_operation=CseOperation.TEMPLATE_INSTALL,
            cse_params=cse_params,
            telemetry_settings=config['service']['telemetry'])

        log_filename = None
        log_wire = utils.str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = INSTALL_WIRELOG_FILEPATH

        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            server_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # read remote template cookbook
        rtm = RemoteTemplateManager(
            remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'], # noqa: E501
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)
        remote_template_cookbook = rtm.get_remote_template_cookbook()

        found_template = False
        for template in remote_template_cookbook['templates']:
            template_name_matched = template_name in (template[server_constants.RemoteTemplateKey.NAME], '*') # noqa: E501
            template_revision_matched = \
                str(template_revision) in (str(template[server_constants.RemoteTemplateKey.REVISION]), '*') # noqa: E501
            if template_name_matched and template_revision_matched:
                found_template = True
                _install_single_template(
                    client=client,
                    remote_template_manager=rtm,
                    template=template,
                    org_name=config['broker']['org'],
                    vdc_name=config['broker']['vdc'],
                    catalog_name=config['broker']['catalog'],
                    network_name=config['broker']['network'],
                    ip_allocation_mode=config['broker']['ip_allocation_mode'],
                    storage_profile=config['broker']['storage_profile'],
                    force_update=force_create,
                    retain_temp_vapp=retain_temp_vapp,
                    ssh_key=ssh_key,
                    is_tkg_plus_enabled=utils.is_tkg_plus_enabled(config),
                    is_tkg_m_enabled=utils.is_tkg_m_enabled(config),
                    msg_update_callback=msg_update_callback)

        if not found_template:
            msg = f"Template '{template_name}' at revision " \
                  f"'{template_revision}' not found in remote template " \
                  "cookbook."
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg, exc_info=True)
            raise Exception(msg)

        # Record telemetry data on successful template install
        record_user_action(cse_operation=CseOperation.TEMPLATE_INSTALL,
                           status=OperationStatus.SUCCESS,
                           telemetry_settings=config['service']['telemetry'])  # noqa: E501
    except Exception:
        msg_update_callback.error(
            "Template Installation Error. Check CSE install logs")
        INSTALL_LOGGER.error("Template Installation Error", exc_info=True)

        # Record telemetry data on template install failure
        record_user_action(cse_operation=CseOperation.TEMPLATE_INSTALL,
                           status=OperationStatus.FAILED,
                           telemetry_settings=config['service']['telemetry'])
    finally:
        if client is not None:
            client.logout()


def _install_single_template(
        client, remote_template_manager, template, org_name,
        vdc_name, catalog_name, network_name, ip_allocation_mode,
        storage_profile, force_update, retain_temp_vapp,
        ssh_key, is_tkg_plus_enabled=False, is_tkg_m_enabled=False,
        msg_update_callback=utils.NullPrinter()):
    # NOTE: For CSE 3.0, if the template is a TKG+ template
    # and `enable_tkg_plus` is set to false,
    # An error should be thrown and template installation should be skipped.
    api_version = float(client.get_api_version())
    if api_version >= float(vCDApiVersion.VERSION_35.value):
        if template[server_constants.LocalTemplateKey.KIND] == \
                shared_constants.ClusterEntityKind.TKG_PLUS.value and \
                not is_tkg_plus_enabled:
            msg = "Found a TKG+ template. However TKG+ is not enabled on " \
                  "CSE. Please enable TKG+ for CSE via config file."
            INSTALL_LOGGER.error(msg)
            msg_update_callback.error(msg)
            raise Exception(msg)
        if template[server_constants.LocalTemplateKey.KIND] == \
                shared_constants.ClusterEntityKind.TKG_M.value and \
                not is_tkg_m_enabled:
            msg = "Found a TKGm template. However TKGm is not enabled on " \
                  "CSE. Please enable TKGm for CSE via config file."
            INSTALL_LOGGER.error(msg)
            msg_update_callback.error(msg)
            raise Exception(msg)
    localTemplateKey = server_constants.LocalTemplateKey
    templateBuildKey = server_constants.TemplateBuildKey
    remote_template_manager.download_template_scripts(
        template_name=template[server_constants.RemoteTemplateKey.NAME],
        revision=template[server_constants.RemoteTemplateKey.REVISION],
        force_overwrite=force_update)
    catalog_item_name = ltm.get_revisioned_template_name(
        template[server_constants.RemoteTemplateKey.NAME],
        template[server_constants.RemoteTemplateKey.REVISION])

    # remote template data is a super set of local template data, barring
    # the key 'catalog_item_name'
    template_data = dict(template)
    template_data[localTemplateKey.CATALOG_ITEM_NAME] = catalog_item_name

    missing_keys = [k for k in localTemplateKey if k not in template_data]
    if len(missing_keys) > 0:
        raise ValueError(f"Invalid template data. Missing keys: {missing_keys}") # noqa: E501

    temp_vm_name = (
        f"{template[server_constants.RemoteTemplateKey.OS].replace('.','')}-"
        f"k8s{template[server_constants.RemoteTemplateKey.KUBERNETES_VERSION].replace('.', '')}-" # noqa: E501
        f"{template[server_constants.RemoteTemplateKey.CNI]}"
        f"{template[server_constants.RemoteTemplateKey.CNI_VERSION].replace('.','')}-vm" # noqa: E501
    )
    build_params = {
        templateBuildKey.TEMPLATE_NAME: template[server_constants.RemoteTemplateKey.NAME], # noqa: E501
        templateBuildKey.TEMPLATE_REVISION: template[server_constants.RemoteTemplateKey.REVISION], # noqa: E501
        templateBuildKey.SOURCE_OVA_NAME: template[server_constants.RemoteTemplateKey.SOURCE_OVA_NAME], # noqa: E501
        templateBuildKey.SOURCE_OVA_HREF: template[server_constants.RemoteTemplateKey.SOURCE_OVA_HREF], # noqa: E501
        templateBuildKey.SOURCE_OVA_SHA256: template[server_constants.RemoteTemplateKey.SOURCE_OVA_SHA256], # noqa: E501
        templateBuildKey.ORG_NAME: org_name,
        templateBuildKey.VDC_NAME: vdc_name,
        templateBuildKey.CATALOG_NAME: catalog_name,
        templateBuildKey.CATALOG_ITEM_NAME: catalog_item_name,
        templateBuildKey.CATALOG_ITEM_DESCRIPTION: template[server_constants.RemoteTemplateKey.DESCRIPTION], # noqa: E501
        templateBuildKey.TEMP_VAPP_NAME: template[server_constants.RemoteTemplateKey.NAME] + '_temp', # noqa: E501
        templateBuildKey.TEMP_VM_NAME: temp_vm_name,
        templateBuildKey.CPU: template[server_constants.RemoteTemplateKey.CPU],
        templateBuildKey.MEMORY: template[server_constants.RemoteTemplateKey.MEMORY], # noqa: E501
        templateBuildKey.NETWORK_NAME: network_name,
        templateBuildKey.IP_ALLOCATION_MODE: ip_allocation_mode, # noqa: E501
        templateBuildKey.STORAGE_PROFILE: storage_profile
    }
    if float(client.get_api_version()) >= float(vCDApiVersion.VERSION_35.value): # noqa: E501
        if template.get(server_constants.RemoteTemplateKey.KIND) not in shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP: # noqa: E501
            raise ValueError(f"Cluster kind is {template.get(server_constants.RemoteTemplateKey.KIND)}" # noqa: E501
                             f" Expected {shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP.keys()}") # noqa: E501
        build_params[templateBuildKey.CSE_PLACEMENT_POLICY] = \
            shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP[template.get(server_constants.RemoteTemplateKey.KIND)] # noqa: E501
    builder = template_builder.TemplateBuilder(client, client, build_params,
                                               ssh_key=ssh_key,
                                               logger=INSTALL_LOGGER,
                                               msg_update_callback=msg_update_callback)  # noqa: E501
    builder.build(force_recreate=force_update,
                  retain_temp_vapp=retain_temp_vapp)

    ltm.save_metadata(client, org_name, catalog_name, catalog_item_name,
                      template_data)


def upgrade_cse(config_file_name, config, skip_template_creation,
                ssh_key, retain_temp_vapp, admin_password,
                msg_update_callback=utils.NullPrinter()):
    """Handle logistics for upgrading CSE to v3.0.

    Handles decision making for configuring AMQP exchange/settings,
    defined entity schema registration for vCD api version >= 35,
    extension registration, catalog setup and template creation, removing old
    CSE sizing based compute policies, assigning the new placement compute
    policy to concerned org VDCs, and create DEF entity for existing clusters.

    :param str config_file_name: config file name.
    :param dict config: content of the CSE config file.
    :param bool skip_template_creation: If True, skip creating the templates.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param str admin_password: New password to be set on existing CSE k8s
        cluster vms. If omitted, old password will be retained, however if
        old password is missing a new password will be auto generated
        regardless.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    populate_vsphere_list(config['vcs'])

    msg = f"Upgrading CSE on vCloud Director using config file " \
          f"'{config_file_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    client = None
    try:
        log_filename = None
        log_wire = utils.str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = INSTALL_WIRELOG_FILEPATH

        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            server_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # Handle no extension and upgrading from MQTT extension
        existing_ext_type = _get_existing_extension_type(client)
        if existing_ext_type == server_constants.ExtensionType.NONE:
            msg = "No existing extension.  Please use `cse install' instead " \
                "of 'cse upgrade'."
            raise Exception(msg)
        elif existing_ext_type == server_constants.ExtensionType.MQTT and \
                not utils.should_use_mqtt_protocol(config):
            # Upgrading from MQTT to AMQP extension
            msg = "Upgrading from MQTT extension to AMQP extension is not " \
                  "supported"
            raise Exception(msg)

        ext_cse_version, ext_vcd_api_version = \
            parse_cse_extension_description(
                client, utils.should_use_mqtt_protocol(config))
        if ext_cse_version == server_constants.UNKNOWN_CSE_VERSION or \
                ext_vcd_api_version == server_constants.UNKNOWN_VCD_API_VERSION: # noqa: E501
            msg = "Found CSE api extension registered with vCD, but " \
                  "couldn't determine version of CSE and/or vCD api " \
                  "used previously."
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)
        else:
            msg = "Found CSE api extension registered by CSE " \
                  f"'{ext_cse_version}' at vCD api version " \
                  f"'v{ext_vcd_api_version}'."
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)

        target_vcd_api_version = config['vcd']['api_version']
        target_cse_version = utils.get_installed_cse_version()

        telemetry_data = {
            PayloadKey.SOURCE_CSE_VERSION: str(ext_cse_version),
            PayloadKey.SOURCE_VCD_API_VERSION: ext_vcd_api_version,
            PayloadKey.TARGET_CSE_VERSION: str(target_cse_version),
            PayloadKey.TARGET_VCD_API_VERSION: target_vcd_api_version,
            PayloadKey.WERE_TEMPLATES_SKIPPED: bool(skip_template_creation),  # noqa: E501
            PayloadKey.WAS_TEMP_VAPP_RETAINED: bool(retain_temp_vapp),
            PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(ssh_key)
        }

        # Telemetry - Record detailed telemetry data on upgrade
        record_user_action_details(CseOperation.SERVICE_UPGRADE,
                                   telemetry_data,
                                   telemetry_settings=config['service']['telemetry'])  # noqa: E501

        # Handle various upgrade scenarios
        # Post CSE 3.0.0 only the following upgrades should be allowed
        # CSE X.Y.Z -> CSE X+1.0.*, CSE X.Y+1.*, X.Y.Z+
        # vCD api X -> vCD api X+ (as supported by CSE and pyvcloud)
        # It should be noted that if CSE X.Y.Z is upgradable to CSE X'.Y'.Z',
        # then CSE X.Y.Z+ should also be allowed to upgrade to CSE X'.Y'.Z'
        # irrespective of when these patches were released.

        # Upgrading from Unknown version is allowed only in
        # CSE 3.0.0 (2.6.0.devX for the time being)

        update_path_not_valid_msg = "CSE upgrade "
        if ext_cse_version == server_constants.UNKNOWN_CSE_VERSION or \
                ext_vcd_api_version == server_constants.UNKNOWN_VCD_API_VERSION: # noqa: E501
            update_path_not_valid_msg += "to "
        else:
            update_path_not_valid_msg += \
                f"path (CSE '{ext_cse_version}', vCD " \
                f"api 'v{ext_vcd_api_version}') -> "
        update_path_not_valid_msg += f"(CSE '{target_cse_version}', vCD api " \
                                     f"'v{target_vcd_api_version}') is not " \
                                     "supported."

        if target_cse_version < ext_cse_version or \
                float(target_vcd_api_version) < float(ext_vcd_api_version):
            raise Exception(update_path_not_valid_msg)

        # CSE version info in extension description is only applicable for
        # CSE 2.6.02b.dev and CSE 3.0.0+ versions.
        cse_2_6_any_patch = semantic_version.SimpleSpec('>=2.6.0,<2.7.0')
        cse_3_0_any_previous_patch = semantic_version.SimpleSpec('>=3.0.0,<=3.0.5')  # noqa: E501
        cse_3_0_patch_below_3 = semantic_version.SimpleSpec('>=3.0.0,<3.0.3')
        allow_upgrade = \
            ext_cse_version == server_constants.UNKNOWN_CSE_VERSION or \
            cse_2_6_any_patch.match(ext_cse_version) or \
            cse_3_0_any_previous_patch.match(ext_cse_version)
        # The TKGm value for kind enum was added in CSE 3.0.3, so any
        # upgrade from CSE 3.0.0, 3.0.1, 3.0.2 should update the schema.
        update_schema = cse_3_0_patch_below_3.match(ext_cse_version)

        if not allow_upgrade:
            raise Exception(update_path_not_valid_msg)

        if target_vcd_api_version in (vCDApiVersion.VERSION_33.value,
                                      vCDApiVersion.VERSION_34.value):
            _legacy_upgrade_to_33_34(
                client=client,
                config=config,
                skip_template_creation=skip_template_creation,
                retain_temp_vapp=retain_temp_vapp,
                admin_password=admin_password,
                msg_update_callback=msg_update_callback)
        elif target_vcd_api_version in (vCDApiVersion.VERSION_35.value,):
            _upgrade_to_35(
                client=client,
                config=config,
                skip_template_creation=skip_template_creation,
                retain_temp_vapp=retain_temp_vapp,
                admin_password=admin_password,
                update_schema=update_schema,
                msg_update_callback=msg_update_callback,
                log_wire=log_wire)
        else:
            raise Exception(update_path_not_valid_msg)

        record_user_action(CseOperation.SERVICE_UPGRADE,
                           status=OperationStatus.SUCCESS,
                           telemetry_settings=config['service']['telemetry'])

        msg = "Upgraded CSE successfully."
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
    except Exception:
        msg_update_callback.error(
            "CSE Installation Error. Check CSE install logs")
        INSTALL_LOGGER.error("CSE Installation Error", exc_info=True)
        record_user_action(CseOperation.SERVICE_UPGRADE,
                           status=OperationStatus.FAILED,
                           telemetry_settings=config['service']['telemetry'])
        raise
    finally:
        if client is not None:
            client.logout()


def _update_cse_mqtt_extension(client, target_vcd_api_version,
                               msg_update_callback=utils.NullPrinter()):
    """Update description and remove and add api filters."""
    mqtt_ext_manager = MQTTExtensionManager(client)

    description = _construct_cse_extension_description(target_vcd_api_version)
    mqtt_ext_manager.update_extension(
        ext_name=server_constants.CSE_SERVICE_NAME,
        ext_version=server_constants.MQTT_EXTENSION_VERSION,
        ext_vendor=server_constants.MQTT_EXTENSION_VENDOR,
        description=description)

    # Remove and add api filters
    ext_info = mqtt_ext_manager.get_extension_info(
        ext_name=server_constants.CSE_SERVICE_NAME,
        ext_version=server_constants.MQTT_EXTENSION_VERSION,
        ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
    ext_urn_id = ext_info[server_constants.MQTTExtKey.EXT_URN_ID]
    ext_uuid = mqtt_ext_manager.get_extension_uuid(ext_urn_id)
    mqtt_ext_manager.delete_api_filter_patterns(ext_uuid, API_FILTER_PATTERNS)
    mqtt_ext_manager.setup_api_filter_patterns(ext_uuid, API_FILTER_PATTERNS)

    msg = f"Updated MQTT extension '{server_constants.CSE_SERVICE_NAME}'"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _update_cse_amqp_extension(client, routing_key, exchange,
                               target_vcd_api_version,
                               msg_update_callback=utils.NullPrinter()):
    """."""
    ext = api_extension.APIExtension(client)
    description = _construct_cse_extension_description(target_vcd_api_version)

    ext.update_extension(
        name=server_constants.CSE_SERVICE_NAME,
        namespace=server_constants.CSE_SERVICE_NAMESPACE,
        routing_key=routing_key,
        exchange=exchange,
        description=description)

    ext.remove_all_api_filters_from_service(
        name=server_constants.CSE_SERVICE_NAME,
        namespace=server_constants.CSE_SERVICE_NAMESPACE)

    ext.add_api_filters_to_service(
        name=server_constants.CSE_SERVICE_NAME,
        patterns=API_FILTER_PATTERNS,
        namespace=server_constants.CSE_SERVICE_NAMESPACE)

    msg = f"Updated API extension '{server_constants.CSE_SERVICE_NAME}' in vCD"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _legacy_upgrade_to_33_34(client, config, skip_template_creation,
                             retain_temp_vapp, admin_password,
                             msg_update_callback=utils.NullPrinter()):
    # create amqp exchange if it doesn't exist
    amqp = config['amqp']
    _create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                          amqp['vhost'], amqp['username'],
                          amqp['password'],
                          msg_update_callback=msg_update_callback)

    if skip_template_creation:
        msg = "Skipping creation of templates."
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)
    else:
        # Recreate all supported templates
        _install_all_templates(
            client=client,
            config=config,
            force_create=True,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=retain_temp_vapp,
            msg_update_callback=msg_update_callback)

    # Fix cluster metadata and admin password
    clusters = get_all_cse_clusters(client)

    _fix_cluster_metadata(
        client=client,
        config=config,
        cse_clusters=clusters,
        msg_update_callback=msg_update_callback)
    _fix_cluster_admin_password(
        client=client,
        cse_clusters=clusters,
        new_admin_password=admin_password,
        msg_update_callback=msg_update_callback)

    # update cse api extension
    _update_cse_amqp_extension(
        client=client,
        routing_key=amqp['routing_key'],
        exchange=amqp['exchange'],
        target_vcd_api_version=config['vcd']['api_version'],
        msg_update_callback=msg_update_callback)


def _upgrade_to_35(client, config, skip_template_creation, retain_temp_vapp,
                   admin_password, update_schema,
                   msg_update_callback=utils.NullPrinter(), log_wire=False):
    """Handle upgrade to api version 35.

    :raises: MultipleRecordsException: (when using mqtt) if more than one
        service with the given name and namespace are found when trying to
        delete the amqp-based extension.
    :raises requests.exceptions.HTTPError: (when using MQTT) if the MQTT
        components were not installed correctly
    """
    is_tkg_plus_enabled = utils.is_tkg_plus_enabled(config=config)
    is_tkg_m_enabled = utils.is_tkg_m_enabled(config=config)

    # Add global placement policies
    _setup_placement_policies(
        client=client,
        policy_list=shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES,
        is_tkg_plus_enabled=is_tkg_plus_enabled,
        is_tkg_m_enabled=is_tkg_m_enabled,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    # Register def schema
    _register_def_schema(
        client=client,
        config=config,
        update_schema=update_schema,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    if skip_template_creation:
        msg = "Skipping creation of templates."
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)
        _assign_placement_policies_to_existing_templates(
            client=client,
            config=config,
            is_tkg_plus_enabled=is_tkg_plus_enabled,
            is_tkg_m_enabled=is_tkg_m_enabled,
            log_wire=utils.str_to_bool(config['service'].get('log_wire')),
            msg_update_callback=msg_update_callback)
    else:
        # Recreate all supported templates
        _install_all_templates(
            client=client,
            config=config,
            force_create=True,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=retain_temp_vapp,
            msg_update_callback=msg_update_callback)

    msg = "Loading all CSE clusters for processing..."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.info(msg)
    clusters = get_all_cse_clusters(client=client, fetch_details=False)

    # Update clusters to have auto generated password and fix their metadata
    _fix_cluster_metadata(
        client=client,
        config=config,
        cse_clusters=clusters,
        msg_update_callback=msg_update_callback)
    _fix_cluster_admin_password(
        client=client,
        cse_clusters=clusters,
        new_admin_password=admin_password,
        msg_update_callback=msg_update_callback)

    # Loading the clusters again after their metadata has been fixed.
    # This time do fetch node details, org name etc. So that the def schema
    # can be populated.
    msg = "Loading all CSE clusters for processing..."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.info(msg)
    clusters = get_all_cse_clusters(client=client, fetch_details=True)

    # Add new vdc (placement) compute policy to ovdc with existing CSE clusters
    _assign_placement_policy_to_vdc_and_right_bundle_to_org(
        client=client,
        cse_clusters=clusters,
        is_tkg_plus_enabled=is_tkg_plus_enabled,
        is_tkg_m_enabled=is_tkg_m_enabled,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    # Remove all old CSE compute policies from the system
    _remove_old_cse_sizing_compute_policies(
        client=client,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    # The new placement policies can't be assigned to existing CSE k8s clusters
    # because the support for assigning compute policy to deployed vms is not
    # there in CSE's compute policy manager. However skipping this step is not
    # going to hurt us, since the cse placement policies are dummy policies
    # designed to gate cluster deployment and has no play once the cluster has
    # been deployed.

    # Create DEF entity for all existing clusters (if missing)
    _create_def_entity_for_existing_clusters(
        client=client,
        cse_clusters=clusters,
        msg_update_callback=msg_update_callback,
        is_tkg_plus_enabled=is_tkg_plus_enabled,
        is_tkg_m_enabled=is_tkg_m_enabled,
        log_wire=log_wire)

    # Print list of users categorized by org, who currently owns CSE clusters
    # and will need DEF entity rights.
    _print_users_in_need_of_def_rights(
        cse_clusters=clusters, msg_update_callback=msg_update_callback)

    # update extension
    if utils.should_use_mqtt_protocol(config):
        # Caller guarantees that there is an extension present
        existing_ext_type = _get_existing_extension_type(client)
        if existing_ext_type == server_constants.ExtensionType.AMQP:
            _deregister_cse_amqp_extension(client)
            _register_cse_as_mqtt_extension(client,
                                            config['vcd']['api_version'],
                                            msg_update_callback)
        elif existing_ext_type == server_constants.ExtensionType.MQTT:
            # Remove api filters and update description
            _update_cse_mqtt_extension(client, config['vcd']['api_version'],
                                       msg_update_callback)
    else:
        # Update amqp exchange
        _create_amqp_exchange(
            exchange_name=config['amqp']['exchange'],
            host=config['amqp']['host'],
            port=config['amqp']['port'],
            vhost=config['amqp']['vhost'],
            username=config['amqp']['username'],
            password=config['amqp']['password'],
            msg_update_callback=msg_update_callback)

        # Update cse api extension (along with api end points)
        _update_cse_amqp_extension(
            client=client,
            routing_key=config['amqp']['routing_key'],
            exchange=config['amqp']['exchange'],
            target_vcd_api_version=config['vcd']['api_version'],
            msg_update_callback=msg_update_callback)


def _fix_cluster_metadata(client,
                          config,
                          cse_clusters,
                          msg_update_callback=utils.NullPrinter()):
    msg = "Fixing metadata on CSE k8s clusters."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.info(msg)
    if not cse_clusters:
        msg = "No CSE k8s clusters were found."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)
        return

    for cluster in cse_clusters:
        msg = f"Processing metadata of cluster '{cluster['name']}'."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

        vapp_href = cluster['vapp_href']
        vapp = VApp(client, href=vapp_href)

        # This step removes the old 'cse.template' metadata and adds
        # cse.template.name and cse.template.revision metadata
        # using hard-coded values taken from github history
        metadata_dict = \
            pyvcloud_vcd_utils.metadata_to_dict(vapp.get_metadata())
        template_name = metadata_dict.get(
            server_constants.ClusterMetadataKey.TEMPLATE_NAME)
        if not template_name:
            msg = "Reconstructing template name and revision for cluster."
            INSTALL_LOGGER.info(msg)
            msg_update_callback.info(msg)

            new_template_name = \
                _construct_template_name_from_history(metadata_dict)

            if not new_template_name:
                msg = "Unable to determine source template of cluster " \
                      f"'{cluster['name']}'. Stopped processing cluster."
                INSTALL_LOGGER.error(msg)
                msg_update_callback.error(msg)
                continue

            msg = "Updating metadata of cluster with template name and revision." # noqa: E501
            INSTALL_LOGGER.info(msg)
            msg_update_callback.info(msg)

            task = vapp.remove_metadata(
                server_constants.ClusterMetadataKey.BACKWARD_COMPATIBLE_TEMPLATE_NAME) # noqa: E501
            client.get_task_monitor().wait_for_success(task)

            new_metadata_to_add = {
                server_constants.ClusterMetadataKey.TEMPLATE_NAME: new_template_name, # noqa: E501
                server_constants.ClusterMetadataKey.TEMPLATE_REVISION: 0
            }
            task = vapp.set_multiple_metadata(new_metadata_to_add)
            client.get_task_monitor().wait_for_success(task)
            vapp.reload()

        # This step uses data from the newly updated cse.template.name and
        # cse.template.revision metadata fields as well as github history
        # to add [cse.os, cse.docker.version, cse.kubernetes,
        # cse.kubernetes.version, cse.cni, cse.cni.version] to the clusters
        # if they are missing.
        metadata_dict = \
            pyvcloud_vcd_utils.metadata_to_dict(vapp.get_metadata())
        template_name = metadata_dict.get(
            server_constants.ClusterMetadataKey.TEMPLATE_NAME)
        template_revision = str(metadata_dict.get(
            server_constants.ClusterMetadataKey.TEMPLATE_REVISION, 0))
        cse_version = metadata_dict.get(
            server_constants.ClusterMetadataKey.CSE_VERSION)
        k8s_distribution = metadata_dict.get(
            server_constants.ClusterMetadataKey.KUBERNETES)
        k8s_version = metadata_dict.get(
            server_constants.ClusterMetadataKey.KUBERNETES_VERSION)
        os_name = metadata_dict.get(
            server_constants.ClusterMetadataKey.OS)
        cni = metadata_dict.get(
            server_constants.ClusterMetadataKey.CNI)
        cni_version = metadata_dict.get(
            server_constants.ClusterMetadataKey.CNI_VERSION)
        docker_version = metadata_dict.get(
            server_constants.ClusterMetadataKey.DOCKER_VERSION)

        if not k8s_distribution or not k8s_version or not os_name or not cni \
                or not cni_version or not docker_version:
            msg = "Determining k8s version on cluster."
            INSTALL_LOGGER.info(msg)
            msg_update_callback.info(msg)

            if not template_name:
                msg = "Unable to determine source template of cluster " \
                      f"'{cluster['name']}'. Stopped processing cluster."
                INSTALL_LOGGER.error(msg)
                msg_update_callback.error(msg)
                continue

            tokens = template_name.split('_')
            k8s_data = tokens[1].split('-')
            cni_data = tokens[2].split('-')

            if not os_name:
                os_name = tokens[0]
            if not k8s_distribution:
                # old clusters that were converted can have non-existent
                # template name that has 'k8s' string in it instead of 'k8'
                if k8s_data[0] in ('k8', 'k8s'):
                    k8s_distribution = 'upstream'
                elif k8s_data[0] in ('tkg', 'tkgp', 'tkgplus'):
                    k8s_distribution = 'TKG+'
                else:
                    k8s_distribution = "Unknown Kubernetes distribution"
            if not cni:
                cni = cni_data[0]
            if not cni_version:
                cni_version = cni_data[1]
            if not k8s_version or not docker_version:
                k8s_version, docker_version = \
                    _get_k8s_and_docker_versions_from_history(
                        template_name=template_name,
                        template_revision=template_revision,
                        cse_version=cse_version)

            # Try to determine the above values using template definition
            org_name = config['broker']['org']
            catalog_name = config['broker']['catalog']
            k8s_templates = ltm.get_all_k8s_local_template_definition(
                client=client, catalog_name=catalog_name, org_name=org_name)
            for k8s_template in k8s_templates:
                # The source of truth for metadata on the clusters is always
                # the template metadata.
                if (str(k8s_template[server_constants.LocalTemplateKey.REVISION]), k8s_template[server_constants.LocalTemplateKey.NAME]) == (template_revision, template_name):  # noqa: E501
                    if k8s_template.get(server_constants.LocalTemplateKey.OS):
                        os_name = k8s_template.get(server_constants.LocalTemplateKey.OS) # noqa: E501
                    if k8s_template.get(server_constants.LocalTemplateKey.KUBERNETES): # noqa: E501
                        k8s_distribution = k8s_template.get(server_constants.LocalTemplateKey.KUBERNETES) # noqa: E501
                    if k8s_template.get(server_constants.LocalTemplateKey.KUBERNETES_VERSION): # noqa: E501
                        k8s_version = k8s_template[server_constants.LocalTemplateKey.KUBERNETES_VERSION] # noqa: E501
                    if k8s_template.get(server_constants.LocalTemplateKey.CNI):
                        cni = k8s_template.get(server_constants.LocalTemplateKey.CNI) # noqa: E501
                    if k8s_template.get(server_constants.LocalTemplateKey.CNI_VERSION): # noqa: E501
                        cni_version = k8s_template.get(server_constants.LocalTemplateKey.CNI_VERSION) # noqa: E501
                    if k8s_template.get(server_constants.LocalTemplateKey.DOCKER_VERSION): # noqa: E501
                        docker_version = k8s_template[server_constants.LocalTemplateKey.DOCKER_VERSION] # noqa: E501
                    break

            new_metadata = {
                server_constants.ClusterMetadataKey.OS: os_name,
                server_constants.ClusterMetadataKey.DOCKER_VERSION: docker_version, # noqa: E501
                server_constants.ClusterMetadataKey.KUBERNETES: k8s_distribution, # noqa: E501
                server_constants.ClusterMetadataKey.KUBERNETES_VERSION: k8s_version, # noqa: E501
                server_constants.ClusterMetadataKey.CNI: cni,
                server_constants.ClusterMetadataKey.CNI_VERSION: cni_version,
            }
            task = vapp.set_multiple_metadata(new_metadata)
            client.get_task_monitor().wait_for_success(task)

        msg = "Finished processing metadata of cluster."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)


def _construct_template_name_from_history(metadata_dict):
    old_template_name = metadata_dict.get(
        server_constants.ClusterMetadataKey.BACKWARD_COMPATIBLE_TEMPLATE_NAME)
    if not old_template_name:
        return ''

    new_template_name = None
    cse_version = metadata_dict.get(
        server_constants.ClusterMetadataKey.CSE_VERSION)
    if 'photon' in old_template_name:
        new_template_name = 'photon-v2'
        if cse_version in ('1.0.0',):
            new_template_name += '_k8-1.8_weave-2.0.5'
        elif cse_version in ('1.1.0', '1.2.0', '1.2.1', '1.2.2', '1.2.3', '1.2.4'): # noqa: E501
            new_template_name += '_k8-1.9_weave-2.3.0'
        elif cse_version in ('1.2.5', '1.2.6', '1.2.7',): # noqa: E501
            new_template_name += '_k8-1.10_weave-2.3.0'
        elif cse_version in ('2.0.0',):
            new_template_name += '_k8-1.12_weave-2.3.0'
        else:
            new_template_name += '_k8-0.0_weave-0.0.0'
    elif 'ubuntu' in old_template_name:
        new_template_name = 'ubuntu-16.04'
        if cse_version in ('1.0.0',):
            new_template_name += '_k8-1.9_weave-2.1.3'
        elif cse_version in ('1.1.0', '1.2.0', '1.2.1', '1.2.2', '1.2.3', '1.2.4', '1.2.5', '1.2.6', '1.2.7'): # noqa: E501
            new_template_name += '_k8-1.10_weave-2.3.0'
        elif cse_version in ('2.0.0',):
            new_template_name += '_k8-1.13_weave-2.3.0'
        else:
            new_template_name += '_k8-0.0_weave-0.0.0'

    return new_template_name


def _get_k8s_and_docker_versions_from_history(
        template_name,
        template_revision,
        cse_version):
    docker_version = '0.0.0'
    k8s_version = template_name.split('_')[1].split('-')[1]
    if 'photon' in template_name:
        docker_version = '17.06.0'
        if template_revision == '1':
            docker_version = '18.06.2'
        if '1.8' in template_name:
            k8s_version = '1.8.1'
        elif '1.9' in template_name:
            k8s_version = '1.9.6'
        elif '1.10' in template_name:
            k8s_version = '1.10.11'
        elif '1.12' in template_name:
            k8s_version = '1.12.7'
        elif '1.14' in template_name:
            k8s_version = '1.14.6'
    elif 'ubuntu' in template_name:
        docker_version = '18.09.7'
        if '1.9' in template_name:
            docker_version = '17.12.0'
            k8s_version = '1.9.3'
        elif '1.10' in template_name:
            docker_version = '18.03.0'
            k8s_version = '1.10.1'
            if cse_version in ('1.2.5', '1.2.6, 1.2.7'):
                k8s_version = '1.10.11'
            if cse_version in ('1.2.7',):
                docker_version = '18.06.2'
        elif '1.13' in template_name:
            docker_version = '18.06.3'
            k8s_version = '1.13.5'
            if template_revision == '2':
                k8s_version = '1.13.12'
        elif '1.15' in template_name:
            docker_version = '18.09.7'
            k8s_version = '1.15.3'
            if template_revision == '2':
                k8s_version = '1.15.5'

    return k8s_version, docker_version


def _fix_cluster_admin_password(client,
                                cse_clusters,
                                new_admin_password=None,
                                msg_update_callback=utils.NullPrinter()):
    msg = "Fixing admin password of CSE k8s clusters."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.info(msg)
    if len(cse_clusters) == 0:
        msg = "No CSE k8s clusters were found."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)
        return

    href_of_vms_to_verify = []
    for cluster in cse_clusters:
        msg = f"Processing admin password of cluster '{cluster['name']}'."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

        vm_hrefs_for_password_update = []
        vapp_href = cluster['vapp_href']
        vapp = VApp(client, href=vapp_href)
        vm_resources = vapp.get_all_vms()
        for vm_resource in vm_resources:
            vm = VM(client, href=vm_resource.get('href'))
            msg = f"Determining if vm '{vm.get_resource().get('name')}' " \
                  "needs processing'."
            INSTALL_LOGGER.info(msg)
            msg_update_callback.info(msg)

            gc_section = vm.get_guest_customization_section()
            admin_password_enabled = False
            if hasattr(gc_section, 'AdminPasswordEnabled'):
                admin_password_enabled = utils.str_to_bool(gc_section.AdminPasswordEnabled) # noqa: E501
            admin_password_on_vm = None
            if hasattr(gc_section, 'AdminPassword'):
                admin_password_on_vm = gc_section.AdminPassword.text

            skip_vm = False
            if admin_password_enabled:
                if new_admin_password:
                    if new_admin_password == admin_password_on_vm:
                        skip_vm = True
                else:
                    if admin_password_on_vm:
                        skip_vm = True
            if not skip_vm:
                href_of_vms_to_verify.append(vm.href)
                vm_hrefs_for_password_update.append(vm.href)

        # At least one vm in the vApp needs a password update
        if len(vm_hrefs_for_password_update) > 0:
            for href in vm_hrefs_for_password_update:
                vm = VM(client=client, href=href)
                try:
                    msg = "Un-deploying vm."
                    INSTALL_LOGGER.info(msg)
                    msg_update_callback.info(msg)
                    task = vm.undeploy()
                    client.get_task_monitor().wait_for_success(task)
                    msg = "Successfully un-deployed vm"
                    INSTALL_LOGGER.info(msg)
                    msg_update_callback.general(msg)
                except Exception as err:
                    INSTALL_LOGGER.debug(str(err))
                    msg_update_callback.info(str(err))

                msg = f"Processing vm '{vm.get_resource().get('name')}'." \
                      "\nUpdating vm admin password"
                INSTALL_LOGGER.info(msg)
                msg_update_callback.info(msg)
                vm.reload()
                task = vm.update_guest_customization_section(
                    enabled=True,
                    admin_password_enabled=True,
                    admin_password_auto=not new_admin_password,
                    admin_password=new_admin_password,
                )
                client.get_task_monitor().wait_for_success(task)
                msg = "Successfully updated vm"
                INSTALL_LOGGER.info(msg)
                msg_update_callback.general(msg)

                msg = "Deploying vm."
                INSTALL_LOGGER.info(msg)
                msg_update_callback.info(msg)
                vm.reload()
                task = vm.power_on_and_force_recustomization()
                client.get_task_monitor().wait_for_success(task)
                msg = "Successfully deployed vm"
                INSTALL_LOGGER.info(msg)
                msg_update_callback.general(msg)

        msg = f"Successfully processed cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)

    while len(href_of_vms_to_verify) != 0:
        msg = f"Waiting on guest customization to finish on {len(href_of_vms_to_verify)} vms." # noqa: E501
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)
        to_remove = []
        for href in href_of_vms_to_verify:
            vm = VM(client=client, href=href)
            gc_section = vm.get_guest_customization_section()
            admin_password_enabled = False
            if hasattr(gc_section, 'AdminPasswordEnabled'):
                admin_password_enabled = utils.str_to_bool(gc_section.AdminPasswordEnabled) # noqa: E501
            admin_password = None
            if hasattr(gc_section, 'AdminPassword'):
                admin_password = gc_section.AdminPassword.text
            if admin_password_enabled and admin_password:
                to_remove.append(vm.href)

        for href in to_remove:
            href_of_vms_to_verify.remove(href)

        if len(href_of_vms_to_verify) > 0:
            time.sleep(5)
        else:
            msg = "Finished Guest customization on all vms."
            INSTALL_LOGGER.info(msg)
            msg_update_callback.info(msg)


def _get_placement_policy_name_from_template_name(template_name):
    if 'k8' in template_name:
        policy_name = \
            shared_constants.NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME
    # This check should be made before the broader 'tkg' check
    # to make sure we deduce the correct template type.
    elif 'tkgm' in template_name:
        policy_name = \
            shared_constants.TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME
    # Some earlier TKG+ templates had just `tkg` in their name and
    # not `tkgplus`
    elif 'tkg' in template_name or 'tkgplus' in template_name:
        policy_name = \
            shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME
    else:
        raise Exception(f"Unknown kind of template '{template_name}'.")

    return policy_name


def _assign_placement_policy_to_vdc_and_right_bundle_to_org(
        client,
        cse_clusters,
        is_tkg_plus_enabled,
        is_tkg_m_enabled,
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):
    """Assign placement policies to VDCs and right bundles to Orgs with existing clusters."""  # noqa: E501
    msg = "Assigning placement compute policy(s) to vDC(s) hosting existing CSE clusters." # noqa: E501
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    msg = "Identifying vDC(s) that are currently hosting CSE clusters."
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    native_ovdcs = set()
    tkg_plus_ovdcs = set()
    tkg_m_ovdcs = set()
    ids_of_orgs_with_clusters = set()
    vdc_names = {}

    for cluster in cse_clusters:
        try:
            policy_name = _get_placement_policy_name_from_template_name(
                cluster['template_name'])
        except Exception:
            msg = f"Invalid template '{cluster['template_name']}' for cluster '{cluster['name']}'."  # noqa: E501
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)
            continue

        ovdc_id = cluster['vdc_id']
        vdc_names[ovdc_id] = cluster['vdc_name']
        org_id = cluster['org_href'].split('/')[-1]
        ids_of_orgs_with_clusters.add(org_id)

        if policy_name == shared_constants.NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            native_ovdcs.add(ovdc_id)
        elif policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            tkg_plus_ovdcs.add(ovdc_id)
        elif policy_name == shared_constants.TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            tkg_m_ovdcs.add(ovdc_id)

    cpm = \
        compute_policy_manager.ComputePolicyManager(client, log_wire=log_wire)

    if native_ovdcs:
        msg = f"Found {len(native_ovdcs)} vDC(s) hosting NATIVE CSE clusters."
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)
        native_policy = compute_policy_manager.get_cse_vdc_compute_policy(
            cpm,
            shared_constants.NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME,
            is_placement_policy=True)
        for vdc_id in native_ovdcs:
            cpm.add_compute_policy_to_vdc(
                vdc_id=vdc_id,
                compute_policy_href=native_policy['href'])
            msg = "Added compute policy " \
                  f"'{native_policy['display_name']}' to vDC " \
                  f"'{vdc_names[vdc_id]}'"
            INSTALL_LOGGER.info(msg)
            msg_update_callback.general(msg)

    if tkg_plus_ovdcs:
        msg = f"Found {len(tkg_plus_ovdcs)} vDC(s) hosting TKG+ clusters."
        if not is_tkg_plus_enabled:
            msg += " However TKG+ is not enabled on CSE. vDC(s) hosting " \
                   "TKG+ clusters will not be processed. Please enable " \
                   "TKG+ for CSE via config file and re-run `cse upgrade` " \
                   "to process these vDC(s)."
            INSTALL_LOGGER.error(msg)
            raise cse_exception.CseUpgradeError(msg)
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)

        tkg_plus_policy = compute_policy_manager.get_cse_vdc_compute_policy(
            cpm,
            shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME,
            is_placement_policy=True)
        for vdc_id in tkg_plus_ovdcs:
            cpm.add_compute_policy_to_vdc(
                vdc_id=vdc_id,
                compute_policy_href=tkg_plus_policy['href'])
            msg = "Added compute policy " \
                  f"'{tkg_plus_policy['display_name']}' to vDC " \
                  f"'{vdc_names[vdc_id]}'"
            INSTALL_LOGGER.info(msg)
            msg_update_callback.general(msg)

    if tkg_m_ovdcs:
        msg = f"Found {len(tkg_m_ovdcs)} vDC(s) hosting TKGm clusters."
        if not is_tkg_m_enabled:
            msg += " However TKGm is not enabled on CSE. vDC(s) hosting " \
                   "TKGm clusters will not be processed. Please enable " \
                   "TKGm for CSE via config file and re-run `cse upgrade` " \
                   "to process these vDC(s)."
            INSTALL_LOGGER.error(msg)
            raise cse_exception.CseUpgradeError(msg)
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)

        tkg_m_policy = compute_policy_manager.get_cse_vdc_compute_policy(
            cpm,
            shared_constants.TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME,
            is_placement_policy=True)
        for vdc_id in tkg_m_ovdcs:
            cpm.add_compute_policy_to_vdc(
                vdc_id=vdc_id,
                compute_policy_href=tkg_m_policy['href'])
            msg = "Added compute policy " \
                  f"'{tkg_m_policy['display_name']}' to vDC " \
                  f"'{vdc_names[vdc_id]}'"
            INSTALL_LOGGER.info(msg)
            msg_update_callback.general(msg)

    if len(ids_of_orgs_with_clusters) > 0:
        msg = "Publishing CSE native cluster right bundles to orgs where " \
              "clusters are deployed"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)
        try:
            rbm = RightBundleManager(client, log_wire=log_wire, logger_debug=INSTALL_LOGGER)  # noqa: E501
            cse_right_bundle = rbm.get_right_bundle_by_name(
                def_utils.DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE)
            rbm.publish_cse_right_bundle_to_tenants(
                right_bundle_id=cse_right_bundle['id'],
                org_ids=list(ids_of_orgs_with_clusters))
        except Exception as err:
            msg = f"Error adding right bundles to the Organizations: {err}"
            INSTALL_LOGGER.error(msg)
            raise
        msg = "Successfully published CSE native cluster right bundle to Orgs"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)


def _remove_old_cse_sizing_compute_policies(
        client,
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):
    msg = "Removing old sizing compute policies created by CSE."
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    cpm = \
        compute_policy_manager.ComputePolicyManager(client, log_wire=log_wire)
    all_cse_policy_names = []
    org_resources = client.get_org_list()
    for org_resource in org_resources:
        org = Org(client, resource=org_resource)
        org_name = org.get_name()

        msg = f"Processing Org : '{org_name}'"
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)

        vdcs = org.list_vdcs()
        for vdc_data in vdcs:
            vdc_name = vdc_data['name']

            msg = f"Processing Org VDC : '{vdc_name}'"
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)

            vdc = vcd_utils.get_vdc(client, vdc_name=vdc_name, org_name=org_name) # noqa: E501
            vdc_id = pyvcloud_vcd_utils.extract_id(vdc.get_resource().get('id')) # noqa: E501
            vdc_sizing_policies = compute_policy_manager.list_cse_sizing_policies_on_vdc(cpm, vdc_id)  # noqa: E501
            if vdc_sizing_policies:
                for policy in vdc_sizing_policies:
                    msg = f"Processing Policy : '{policy['display_name']}' on Org VDC : '{vdc_name}'" # noqa: E501
                    msg_update_callback.info(msg)
                    INSTALL_LOGGER.info(msg)

                    all_cse_policy_names.append(policy['display_name'])
                    task_data = cpm.remove_vdc_compute_policy_from_vdc(
                        ovdc_id=vdc_id,
                        compute_policy_href=policy['href'],
                        force=True)
                    fake_task_object = {'href': task_data['task_href']}
                    client.get_task_monitor().wait_for_status(fake_task_object) # noqa: E501

                    msg = f"Removed Policy : '{policy['display_name']}' from Org VDC : '{vdc_name}'" # noqa: E501
                    msg_update_callback.general(msg)
                    INSTALL_LOGGER.info(msg)

            msg = f"Finished processing Org VDC : '{vdc_name}'"
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)

        msg = f"Finished processing Org : '{org_name}'"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

    for policy_name in all_cse_policy_names:
        try:
            msg = f"Deleting  Policy : '{policy_name}'"
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)

            compute_policy_manager.delete_cse_vdc_compute_policy(cpm,
                                                                 policy_name)

            msg = f"Deleted  Policy : '{policy_name}'"
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
        except Exception:
            msg = f"Failed to deleted  Policy : '{policy_name}'"
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)


def _create_def_entity_for_existing_clusters(
        client,
        cse_clusters,
        is_tkg_plus_enabled,
        is_tkg_m_enabled,
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):
    msg = "Making old CSE k8s clusters compatible with CSE 3.0"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER if log_wire else NULL_LOGGER
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client,
        logger_debug=INSTALL_LOGGER,
        logger_wire=logger_wire)
    entity_svc = def_entity_svc.DefEntityService(cloudapi_client)
    schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
    keys_map = def_utils.MAP_API_VERSION_TO_KEYS[float(client.get_api_version())] # noqa: E501
    entity_type_id = def_utils.generate_entity_type_id(
        vendor=keys_map[def_utils.DefKey.ENTITY_TYPE_VENDOR],
        nss=keys_map[def_utils.DefKey.ENTITY_TYPE_NSS],
        version=keys_map[def_utils.DefKey.ENTITY_TYPE_VERSION])
    native_entity_type = schema_svc.get_entity_type(entity_type_id)

    for cluster in cse_clusters:
        msg = f"Processing cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

        cluster_id = cluster['cluster_id']
        try:
            entity_svc.get_entity(cluster_id)
            msg = f"Skipping cluster '{cluster['name']}' since it has " \
                  "already been processed."
            INSTALL_LOGGER.info(msg)
            msg_update_callback.info(msg)
            continue
        except Exception as err:
            INSTALL_LOGGER.debug(str(err))

        try:
            policy_name = _get_placement_policy_name_from_template_name(
                cluster['template_name'])
        except Exception:
            msg = f"Invalid template '{cluster['template_name']}' for cluster '{cluster['name']}'." # noqa: E501
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)
            continue

        kind = None
        if policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            if not is_tkg_plus_enabled:
                msg = "Found a TKG+ cluster. However TKG+ is not enabled " \
                      "on CSE. Please enable TKG+ for CSE via config " \
                      "file and re-run`cse upgrade` to process these " \
                      "clusters"
                INSTALL_LOGGER.error(msg)
                raise cse_exception.CseUpgradeError(msg)
            else:
                kind = shared_constants.ClusterEntityKind.TKG_PLUS.value
        elif policy_name == shared_constants.TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            if not is_tkg_m_enabled:
                msg = "Found a TKGm cluster. However TKGm is not enabled " \
                      "on CSE. Please enable TKGm for CSE via config " \
                      "file and re-run`cse upgrade` to process these " \
                      "clusters"
                INSTALL_LOGGER.error(msg)
                raise cse_exception.CseUpgradeError(msg)
            else:
                kind = shared_constants.ClusterEntityKind.TKG_M.value
        elif policy_name == shared_constants.NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            kind = shared_constants.ClusterEntityKind.NATIVE.value

        worker_nodes = []
        for item in cluster['nodes']:
            worker_nodes.append(
                def_models.Node(name=item['name'], ip=item['ipAddress']))
        nfs_nodes = []
        for item in cluster['nfs_nodes']:
            nfs_nodes.append(def_models.NfsNode(
                name=item['name'],
                ip=item['ipAddress'],
                exports=item['exports']))

        cluster_entity = def_models.NativeEntity(
            kind=kind,
            spec=def_models.ClusterSpec(
                workers=def_models.Workers(
                    count=len(cluster['nodes']),
                    storage_profile=cluster['storage_profile_name']),
                control_plane=def_models.ControlPlane(
                    count=len(cluster['master_nodes']),
                    storage_profile=cluster['storage_profile_name']),
                nfs=def_models.Nfs(
                    count=len(cluster['nfs_nodes']),
                    storage_profile=cluster['storage_profile_name']),
                settings=def_models.Settings(
                    network=cluster['network_name'],
                    ssh_key=""),  # Impossible to get this value from clusters
                k8_distribution=def_models.Distribution(
                    template_name=cluster['template_name'],
                    template_revision=int(cluster['template_revision']))),
            status=def_models.Status(
                phase=str(shared_constants.DefEntityPhase(
                    shared_constants.DefEntityOperation.CREATE,
                    shared_constants.DefEntityOperationStatus.SUCCEEDED)),
                kubernetes=f"{cluster['kubernetes']} {cluster['kubernetes_version']}", # noqa: E501
                cni=f"{cluster['cni']} {cluster['cni_version']}",
                os=cluster['os'],
                docker_version=cluster['docker_version'],
                nodes=def_models.Nodes(
                    control_plane=def_models.Node(
                        name=cluster['master_nodes'][0]['name'],
                        ip=cluster['master_nodes'][0]['ipAddress']),
                    workers=worker_nodes,
                    nfs=nfs_nodes)),
            metadata=def_models.Metadata(
                org_name=cluster['org_name'],
                ovdc_name=cluster['vdc_name'],
                cluster_name=cluster['name']),
            api_version="")

        org_resource = vcd_utils.get_org(client, org_name=cluster['org_name'])
        org_id = org_resource.href.split('/')[-1]
        def_entity = def_models.DefEntity(entity=cluster_entity)
        entity_svc.create_entity(native_entity_type.id, entity=def_entity,
                                 tenant_org_context=org_id)

        def_entity = entity_svc.get_native_entity_by_name(cluster['name'])
        def_entity_id = def_entity.id
        def_entity.externalId = cluster['vapp_href']

        # update ownership of the entity
        try:
            user = client.get_user_in_org(
                user_name=cluster['owner_name'],
                org_href=cluster['org_href'])
            user_urn = user.get('id')
            orgmember_urn = user_urn.replace(":user:", ":orgMember:")

            org_href = cluster['org_href']
            org_id = org_href.split("/")[-1]
            org_urn = f"urn:vcloud:org:{org_id}"

            def_entity.owner = def_models.Owner(
                name=cluster['owner_name'],
                id=orgmember_urn)
            def_entity.org = def_models.Org(
                name=cluster['org_name'],
                id=org_urn)
        except Exception as err:
            INSTALL_LOGGER.debug(str(err))
            msg = "Unable to determine current owner of cluster " \
                  f"'{cluster['name']}'. Unable to process ownership."
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)

        entity_svc.update_entity(def_entity_id, def_entity)
        entity_svc.resolve_entity(def_entity_id)

        msg = f"Generated new id for cluster '{cluster['name']}' "
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)

        # update vapp metadata to reflect new cluster_id
        msg = f"Updating metadata of cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

        tags = {
            server_constants.ClusterMetadataKey.CLUSTER_ID: def_entity_id
        }
        vapp = VApp(client, href=cluster['vapp_href'])
        task = vapp.set_multiple_metadata(tags)
        client.get_task_monitor().wait_for_status(task)

        msg = f"Updated metadata of cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)

        msg = f"Finished processing cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)

    msg = "Finished processing all clusters."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.general(msg)


def _print_users_in_need_of_def_rights(
        cse_clusters, msg_update_callback=utils.NullPrinter()):
    org_user_dict = {}
    for cluster in cse_clusters:
        if cluster['org_name'] not in org_user_dict:
            org_user_dict[cluster['org_name']] = []
        org_user_dict[cluster['org_name']].append(cluster['owner_name'])

    msg = "The following users own CSE k8s clusters and will require " \
          "`cse:nativeCluster Entitlement` right bundle " \
          "to access them in CSE 3.0"
    org_users_msg = ""
    for org_name, user_list in org_user_dict.items():
        org_users_msg += f"\nOrg : {org_name} -> Users : {', '.join(set(user_list))}"  # noqa: E501

    if org_users_msg:
        msg = msg + org_users_msg
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)


def configure_nsxt_for_cse(nsxt_servers, log_wire=False, msg_update_callback=utils.NullPrinter()):  # noqa: E501
    """Configure NSXT-T server for CSE.

    :param dict nsxt_servers: nsxt_server details
    :param Logger log_wire:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    wire_logger = SERVER_NSXT_WIRE_LOGGER if log_wire else NULL_LOGGER
    try:
        for nsxt_server in nsxt_servers:
            msg = f"Configuring NSX-T server ({nsxt_server.get('name')})" \
                " for CSE. Please check install logs for details."
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
            nsxt_client = NSXTClient(
                host=nsxt_server.get('host'),
                username=nsxt_server.get('username'),
                password=nsxt_server.get('password'),
                logger_debug=INSTALL_LOGGER,
                logger_wire=wire_logger,
                http_proxy=nsxt_server.get('proxy'),
                https_proxy=nsxt_server.get('proxy'),
                verify_ssl=nsxt_server.get('verify'))
            setup_nsxt_constructs(
                nsxt_client=nsxt_client,
                nodes_ip_block_id=nsxt_server.get('nodes_ip_block_ids'),
                pods_ip_block_id=nsxt_server.get('pods_ip_block_ids'),
                ncp_boundary_firewall_section_anchor_id=nsxt_server.get('distributed_firewall_section_anchor_id')) # noqa: E501
    except Exception:
        msg_update_callback.error(
            "NSXT Configuration Error. Check CSE install logs")
        INSTALL_LOGGER.error("NSXT Configuration Error", exc_info=True)
        raise
