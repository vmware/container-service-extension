# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import json

import pika
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from requests.exceptions import HTTPError

from container_service_extension.config_validator import get_validated_config
import container_service_extension.def_modules.schema_svc as def_schema_svc
import container_service_extension.def_modules.utils as def_utils
from container_service_extension.exceptions import AmqpError
import container_service_extension.local_template_manager as ltm
from container_service_extension.logger import INSTALL_LOGGER
from container_service_extension.logger import INSTALL_WIRELOG_FILEPATH
from container_service_extension.logger import NULL_LOGGER
from container_service_extension.logger import SERVER_CLI_LOGGER
from container_service_extension.logger import SERVER_CLI_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_CLOUDAPI_WIRE_LOGGER
from container_service_extension.logger import SERVER_NSXT_WIRE_LOGGER
from container_service_extension.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.nsxt.nsxt_client import NSXTClient
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
from container_service_extension.server_constants import \
    CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY, CSE_NATIVE_DEPLOY_RIGHT_CATEGORY, \
    CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION, CSE_NATIVE_DEPLOY_RIGHT_NAME, \
    CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY, CSE_PKS_DEPLOY_RIGHT_CATEGORY, \
    CSE_PKS_DEPLOY_RIGHT_DESCRIPTION, CSE_PKS_DEPLOY_RIGHT_NAME, \
    CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, EXCHANGE_TYPE, LocalTemplateKey, \
    PKS_SERVICE_NAME, RemoteTemplateKey, SYSTEM_ORG_NAME, \
    TemplateBuildKey # noqa: H301
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.telemetry.telemetry_utils import \
    store_telemetry_settings
from container_service_extension.template_builder import TemplateBuilder
import container_service_extension.utils as utils
from container_service_extension.vsphere_utils import populate_vsphere_list


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
                msg = f"AMQP exchange '{amqp['exchange']}' exists"
                msg_update_callback.general(msg)
                SERVER_CLI_LOGGER.debug(msg)
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
                msg_update_callback.info(msg)
                SERVER_CLI_LOGGER.debug(msg)
                err_msgs.append(msg)
            if cse_info['enabled'] == 'true':
                msg = "CSE on vCD is currently enabled"
                msg_update_callback.general(msg)
                SERVER_CLI_LOGGER.debug(msg)
            else:
                msg = "CSE on vCD is currently disabled"
                msg_update_callback.info(msg)
                SERVER_CLI_LOGGER.debug(msg)
        except MissingRecordException:
            msg = "CSE is not registered to vCD"
            msg_update_callback.error(msg)
            SERVER_CLI_LOGGER.error(msg)
            err_msgs.append(msg)

        # check that catalog exists in vCD
        org_name = config['broker']['org']
        org = vcd_utils.get_org(client, org_name=org_name)
        catalog_name = config['broker']['catalog']
        if vcd_utils.catalog_exists(org, catalog_name):
            msg = f"Found catalog '{catalog_name}'"
            msg_update_callback.general(msg)
            SERVER_CLI_LOGGER.debug(msg)
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
    SERVER_CLI_LOGGER.debug(msg)


def install_cse(config_file_name, skip_template_creation, force_update,
                ssh_key, retain_temp_vapp, pks_config_file_name=None,
                skip_config_decryption=False,
                decryption_password=None,
                msg_update_callback=utils.NullPrinter()):
    """Handle logistics for CSE installation.

    Handles decision making for configuring AMQP exchange/settings,
    defined entity schema registration for vCD api version >= 35,
    extension registration, catalog setup and template creation.

    Also records telemetry data on installation details.

    :param str config_file_name: config file name.
    :param bool skip_template_creation: If True, skip creating the templates.
    :param bool force_update: if True and templates already exist in vCD,
        overwrites existing templates.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param str pks_config_file_name: pks config file name.
    :param bool skip_config_decryption: do not decrypt the config file.
    :param str decryption_password: password to decrypt the config file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    config = get_validated_config(
        config_file_name, pks_config_file_name=pks_config_file_name,
        skip_config_decryption=skip_config_decryption,
        decryption_password=decryption_password,
        log_wire_file=INSTALL_WIRELOG_FILEPATH,
        logger_debug=INSTALL_LOGGER,
        msg_update_callback=msg_update_callback)

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
            PayloadKey.WERE_TEMPLATES_FORCE_UPDATED: bool(force_update),  # noqa: E501
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
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # create amqp exchange if it doesn't exist
        amqp = config['amqp']
        _create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                              amqp['vhost'], amqp['ssl'], amqp['username'],
                              amqp['password'],
                              msg_update_callback=msg_update_callback)

        # register or update cse on vCD
        _register_cse(client, amqp['routing_key'], amqp['exchange'],
                      msg_update_callback=msg_update_callback)

        # register cse def schema on VCD
        # schema should be located at
        # ~/.cse-schema/api-v<API VERSION>/schema.json
        _register_def_schema(client, msg_update_callback=msg_update_callback,
                             log_wire=log_wire)

        # Since we use CSE extension id as our telemetry instance_id, the
        # validated config won't have the instance_id yet. Now that CSE has
        # been registered as an extension, we should update the telemetry
        # config with the correct instance_id
        if config['service']['telemetry']['enable']:
            store_telemetry_settings(config)

        # register rights to vCD
        # TODO() should also remove rights when unregistering CSE
        _register_right(client, right_name=CSE_NATIVE_DEPLOY_RIGHT_NAME,
                        description=CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION,
                        category=CSE_NATIVE_DEPLOY_RIGHT_CATEGORY,
                        bundle_key=CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY,
                        msg_update_callback=msg_update_callback)
        _register_right(client, right_name=CSE_PKS_DEPLOY_RIGHT_NAME,
                        description=CSE_PKS_DEPLOY_RIGHT_DESCRIPTION,
                        category=CSE_PKS_DEPLOY_RIGHT_CATEGORY,
                        bundle_key=CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY,
                        msg_update_callback=msg_update_callback)

        # set up cse catalog
        org = vcd_utils.get_org(client, org_name=config['broker']['org'])
        vcd_utils.create_and_share_catalog(
            org, config['broker']['catalog'], catalog_desc='CSE templates',
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)

        if skip_template_creation:
            msg = "Skipping creation of templates."
            msg_update_callback.info(msg)
            INSTALL_LOGGER.warning(msg)
        else:
            # read remote template cookbook, download all scripts
            rtm = RemoteTemplateManager(
                remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'], # noqa: E501
                logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)
            remote_template_cookbook = rtm.get_remote_template_cookbook()

            # create all templates defined in cookbook
            for template in remote_template_cookbook['templates']:
                _install_template(
                    client=client,
                    remote_template_manager=rtm,
                    template=template,
                    org_name=config['broker']['org'],
                    vdc_name=config['broker']['vdc'],
                    catalog_name=config['broker']['catalog'],
                    network_name=config['broker']['network'],
                    ip_allocation_mode=config['broker']['ip_allocation_mode'],
                    storage_profile=config['broker']['storage_profile'],
                    force_update=force_update,
                    retain_temp_vapp=retain_temp_vapp,
                    ssh_key=ssh_key,
                    msg_update_callback=msg_update_callback)

        # if it's a PKS setup, setup NSX-T constructs
        if config.get('pks_config'):
            nsxt_servers = config['pks_config']['nsxt_servers']
            wire_logger = NULL_LOGGER
            if log_wire:
                wire_logger = SERVER_NSXT_WIRE_LOGGER

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


def install_template(template_name, template_revision, config_file_name,
                     force_create, retain_temp_vapp, ssh_key,
                     skip_config_decryption=False, decryption_password=None,
                     msg_update_callback=utils.NullPrinter()):
    """Install a particular template in CSE.

    If template_name and revision are wild carded to *, all templates defined
    in remote template cookbook will be installed.

    :param str template_name:
    :param str template_revision:
    :param str config_file_name: config file name.
    :param bool force_create: if True and template already exists in vCD,
        overwrites existing template.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param bool skip_config_decryption: do not decrypt the config file.
    :param str decryption_password: password to decrypt the config file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    config = get_validated_config(
        config_file_name, skip_config_decryption=skip_config_decryption,
        decryption_password=decryption_password,
        log_wire_file=INSTALL_WIRELOG_FILEPATH,
        logger_debug=INSTALL_LOGGER,
        msg_update_callback=msg_update_callback)

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
                                            SYSTEM_ORG_NAME,
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
            template_name_matched = template_name in (template[RemoteTemplateKey.NAME], '*') # noqa: E501
            template_revision_matched = str(template_revision) in (str(template[RemoteTemplateKey.REVISION]), '*') # noqa: E501
            if template_name_matched and template_revision_matched:
                found_template = True
                _install_template(
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


def _create_amqp_exchange(exchange_name, host, port, vhost, use_ssl,
                          username, password,
                          msg_update_callback=utils.NullPrinter()):
    """Create the specified AMQP exchange if it does not exist.

    If specified AMQP exchange exists already, does nothing.

    :param str exchange_name: The AMQP exchange name to check for or create.
    :param str host: AMQP host name.
    :param str password: AMQP password.
    :param int port: AMQP port number.
    :param bool use_ssl: Enable ssl.
    :param str username: AMQP username.
    :param str vhost: AMQP vhost.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    msg = f"Checking for AMQP exchange '{exchange_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)
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
        msg_update_callback.error(msg)
        INSTALL_LOGGER.error(msg, exc_info=True)
        raise AmqpError(msg, str(err))
    finally:
        if connection is not None:
            connection.close()
    msg = f"AMQP exchange '{exchange_name}' is ready"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _register_def_schema(client: Client,
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
    msg = "Registering defined entity schema"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.debug(msg)
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
        native_interface = \
            def_utils.DefInterface(name=keys_map[defKey.INTERFACE_NAME],
                                   vendor=keys_map[defKey.VENDOR],
                                   nss=keys_map[defKey.INTERFACE_NSS],
                                   version=keys_map[defKey.INTERFACE_VERSION],
                                   readonly=False)
        msg = ""
        try:
            schema_svc.get_interface(native_interface.get_id())
            msg = "defined entity interface already exists." \
                  " Skipping defined entity interface creation"
        except HTTPError:
            # TODO handle this part only if the interface was not found
            native_interface = schema_svc.create_interface(native_interface)
            msg = "Successfully created defined entity interface"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.debug(msg)

        # TODO stop-gap fix - find efficient way to import schema
        import importlib
        import importlib.resources as pkg_resources
        schema_module = importlib.import_module(
            f'{def_utils.DEF_SCHEMA_DIRECTORY}.{keys_map[defKey.ENTITY_TYPE_SCHEMA_VERSION]}') # noqa: E501
        schema_file = pkg_resources.open_text(schema_module, def_utils.DEF_ENTITY_TYPE_SCHEMA_FILE) # noqa: E501

        native_entity_type = \
            def_utils.DefEntityType(name=keys_map[defKey.ENTITY_TYPE_NAME],
                                    description='',
                                    vendor=keys_map[defKey.VENDOR],
                                    nss=keys_map[defKey.ENTITY_TYPE_NSS],
                                    version=keys_map[defKey.ENTITY_TYPE_VERSION], # noqa: E501
                                    schema=json.load(schema_file),
                                    interfaces=[native_interface.get_id()],
                                    readonly=False)
        msg = ""
        try:
            schema_svc.get_entity_type(native_entity_type.get_id())
            msg = "defined entity type already exists." \
                  " Skipping defined entity type creation"
        except HTTPError:
            # TODO handle this part only if the entity type was not found
            native_entity_type = schema_svc.create_entity_type(native_entity_type) # noqa: E501
            msg = "Successfully registered defined entity type"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.debug(msg)
    except def_utils.DefNotSupportedException:
        msg = "Skipping defined entity type and defined entity interface" \
              " registration"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.debug(msg)
    except Exception as e:
        msg = f"Error occured while registering defined entity schema: {str(e)}" # noqa: E501
        msg_update_callback.error(msg)
        INSTALL_LOGGER.error(msg)
        raise(e)
    finally:
        try:
            schema_file.close()
        except Exception:
            pass


def _register_cse(client, routing_key, exchange,
                  msg_update_callback=utils.NullPrinter()):
    """Register or update CSE on vCD.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.client.Client client:
    :param str routing_key:
    :param str exchange:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    ext = APIExtension(client)
    patterns = [
        f'/api/{CSE_SERVICE_NAME}',
        f'/api/{CSE_SERVICE_NAME}/.*',
        f'/api/{CSE_SERVICE_NAME}/.*/.*',
        f'/api/{PKS_SERVICE_NAME}',
        f'/api/{PKS_SERVICE_NAME}/.*',
        f'/api/{PKS_SERVICE_NAME}/.*/.*'
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

    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


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
    ext = APIExtension(client)
    # Since the client is a sys admin, org will hold a reference to System org
    system_org = Org(client, resource=client.get_org())
    try:
        right_name_in_vcd = f"{{{CSE_SERVICE_NAME}}}:{right_name}"
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
        system_org.add_rights([right_name_in_vcd])
    except EntityNotFoundException:
        # Registering a right via api extension end point, auto assigns it to
        # System org.
        msg = f"Registering Right: {right_name} in vCD"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
        ext.add_service_right(
            right_name, CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, description,
            category, bundle_key)


def _install_template(client, remote_template_manager, template, org_name,
                      vdc_name, catalog_name, network_name, ip_allocation_mode,
                      storage_profile, force_update, retain_temp_vapp,
                      ssh_key, msg_update_callback=utils.NullPrinter()):
    remote_template_manager.download_template_scripts(
        template_name=template[RemoteTemplateKey.NAME],
        revision=template[RemoteTemplateKey.REVISION],
        force_overwrite=force_update)
    catalog_item_name = ltm.get_revisioned_template_name(
        template[RemoteTemplateKey.NAME],
        template[RemoteTemplateKey.REVISION])

    # remote template data is a super set of local template data, barring
    # the key 'catalog_item_name'
    template_data = dict(template)
    template_data[LocalTemplateKey.CATALOG_ITEM_NAME] = catalog_item_name

    missing_keys = [k for k in LocalTemplateKey if k not in template_data]
    if len(missing_keys) > 0:
        raise ValueError(f"Invalid template data. Missing keys: {missing_keys}") # noqa: E501

    temp_vm_name = \
        f"{template[RemoteTemplateKey.OS].replace('.','')}-k8s" \
        f"{template[RemoteTemplateKey.KUBERNETES_VERSION].replace('.', '')}" \
        f"-{template[RemoteTemplateKey.CNI]}{template[RemoteTemplateKey.CNI_VERSION].replace('.','')}-vm" # noqa: E501
    build_params = {
        TemplateBuildKey.TEMPLATE_NAME: template[RemoteTemplateKey.NAME], # noqa: E501
        TemplateBuildKey.TEMPLATE_REVISION: template[RemoteTemplateKey.REVISION], # noqa: E501
        TemplateBuildKey.SOURCE_OVA_NAME: template[RemoteTemplateKey.SOURCE_OVA_NAME], # noqa: E501
        TemplateBuildKey.SOURCE_OVA_HREF: template[RemoteTemplateKey.SOURCE_OVA_HREF], # noqa: E501
        TemplateBuildKey.SOURCE_OVA_SHA256: template[RemoteTemplateKey.SOURCE_OVA_SHA256], # noqa: E501
        TemplateBuildKey.ORG_NAME: org_name,
        TemplateBuildKey.VDC_NAME: vdc_name,
        TemplateBuildKey.CATALOG_NAME: catalog_name,
        TemplateBuildKey.CATALOG_ITEM_NAME: catalog_item_name,
        TemplateBuildKey.CATALOG_ITEM_DESCRIPTION: template[RemoteTemplateKey.DESCRIPTION], # noqa: E501
        TemplateBuildKey.TEMP_VAPP_NAME: template[RemoteTemplateKey.NAME] + '_temp', # noqa: E501
        TemplateBuildKey.TEMP_VM_NAME: temp_vm_name,
        TemplateBuildKey.CPU: template[RemoteTemplateKey.CPU],
        TemplateBuildKey.MEMORY: template[RemoteTemplateKey.MEMORY],
        TemplateBuildKey.NETWORK_NAME: network_name,
        TemplateBuildKey.IP_ALLOCATION_MODE: ip_allocation_mode, # noqa: E501
        TemplateBuildKey.STORAGE_PROFILE: storage_profile
    }
    builder = TemplateBuilder(client, client, build_params, ssh_key=ssh_key,
                              logger=INSTALL_LOGGER,
                              msg_update_callback=msg_update_callback)
    builder.build(force_recreate=force_update,
                  retain_temp_vapp=retain_temp_vapp)

    ltm.save_metadata(client, org_name, catalog_name, catalog_item_name,
                      template_data)
