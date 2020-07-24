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
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
import pyvcloud.vcd.utils as pyvcloud_vcd_utils
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
import semantic_version

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
from container_service_extension.config_validator import get_validated_config
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
from container_service_extension.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.nsxt.nsxt_client import NSXTClient
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
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
from container_service_extension.template_builder import TemplateBuilder
import container_service_extension.utils as utils
from container_service_extension.vcdbroker import get_all_clusters as get_all_cse_clusters # noqa: E501
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
                                            server_constants.SYSTEM_ORG_NAME,
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
                                         exchange_type=server_constants.EXCHANGE_TYPE, # noqa: E501
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
                                         namespace=server_constants.CSE_SERVICE_NAMESPACE) # noqa: E501
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


def _construct_cse_extension_description(target_vcd_api_version):
    """."""
    cse_version = utils.get_installed_cse_version()
    description = f"cse-{cse_version},vcd_api-{target_vcd_api_version}"
    return description


def parse_cse_extension_description(sys_admin_client):
    """."""
    ext = api_extension.APIExtension(sys_admin_client)
    ext_dict = ext.get_extension_info(
        server_constants.CSE_SERVICE_NAME,
        namespace=server_constants.CSE_SERVICE_NAMESPACE)
    ext_xml = ext.get_extension_xml(ext_dict['id'])
    child = ext_xml.find(f"{{{NSMAP['vcloud']}}}Description")
    description = ''
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
    return (cse_version, vcd_api_version)


def install_cse(config_file_name, skip_template_creation,
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
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param str pks_config_file_name: pks config file name.
    :param bool skip_config_decryption: do not decrypt the config file.
    :param str decryption_password: password to decrypt the config file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises cse_exception.AmqpError: if AMQP exchange could not be created.
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

        # create amqp exchange if it doesn't exist
        amqp = config['amqp']
        _create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                              amqp['vhost'], amqp['ssl'], amqp['username'],
                              amqp['password'],
                              msg_update_callback=msg_update_callback)

        # register cse as an api extension to vCD
        _register_cse_as_extension(
            client=client,
            routing_key=amqp['routing_key'],
            exchange=amqp['exchange'],
            target_vcd_api_version=config['vcd']['api_version'],
            msg_update_callback=msg_update_callback)

        # Since we use CSE extension id as our telemetry instance_id, the
        # validated config won't have the instance_id yet. Now that CSE has
        # been registered as an extension, we should update the telemetry
        # config with the correct instance_id
        if config['service']['telemetry']['enable']:
            store_telemetry_settings(config)

        # register cse def schema on VCD
        _register_def_schema(client, msg_update_callback=msg_update_callback,
                             log_wire=log_wire)

        # register rights to vCD
        # TODO() should also remove rights when unregistering CSE
        _register_right(client,
                        right_name=server_constants.CSE_NATIVE_DEPLOY_RIGHT_NAME, # noqa: E501
                        description=server_constants.CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION, # noqa: E501
                        category=server_constants.CSE_NATIVE_DEPLOY_RIGHT_CATEGORY, # noqa: E501
                        bundle_key=server_constants.CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY, # noqa: E501
                        msg_update_callback=msg_update_callback)
        _register_right(client, right_name=server_constants.CSE_PKS_DEPLOY_RIGHT_NAME, # noqa: E501
                        description=server_constants.CSE_PKS_DEPLOY_RIGHT_DESCRIPTION, # noqa: E501
                        category=server_constants.CSE_PKS_DEPLOY_RIGHT_CATEGORY, # noqa: E501
                        bundle_key=server_constants.CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY, # noqa: E501
                        msg_update_callback=msg_update_callback)

        # set up placement policies for all types of clusters
        _setup_placement_policies(client,
                                  policy_list=shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES, # noqa: E501
                                  msg_update_callback=msg_update_callback,
                                  log_wire=log_wire)

        # set up cse catalog
        org = vcd_utils.get_org(client, org_name=config['broker']['org'])
        vcd_utils.create_and_share_catalog(
            org, config['broker']['catalog'], catalog_desc='CSE templates',
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)

        # install all templates
        _install_all_templates(
            client=client,
            config=config,
            skip_template_creation=skip_template_creation,
            force_create=False,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=retain_temp_vapp,
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

    :raises cse_exception.AmqpError: if AMQP exchange could not be created.
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


def _deregister_cse(client, msg_update_callback=utils.NullPrinter()):
    """Deregister CSE from VCD."""
    ext = api_extension.APIExtension(client)
    ext.delete_extension(name=server_constants.CSE_SERVICE_NAME,
                         namespace=server_constants.CSE_SERVICE_NAMESPACE)
    msg = "Successfully deregistered CSE from VCD"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _register_cse_as_extension(client, routing_key, exchange,
                               target_vcd_api_version,
                               msg_update_callback=utils.NullPrinter()):
    """Register CSE on vCD.

    Throws exception if CSE is already registered.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.client.Client client:
    :param str routing_key:
    :param str exchange:
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    ext = api_extension.APIExtension(client)
    patterns = [
        f'/api/{server_constants.CSE_SERVICE_NAME}',
        f'/api/{server_constants.CSE_SERVICE_NAME}/.*',
        f'/api/{server_constants.PKS_SERVICE_NAME}',
        f'/api/{server_constants.PKS_SERVICE_NAME}/.*',
    ]

    vcd_api_versions = client.get_supported_versions_list()
    if target_vcd_api_version not in vcd_api_versions:
        raise ValueError(f"Target VCD API version '{target_vcd_api_version}' "
                         f" is not in supported versions: {vcd_api_versions}")
    description = _construct_cse_extension_description(target_vcd_api_version)
    msg = None
    try:
        ext.get_extension_info(
            server_constants.CSE_SERVICE_NAME,
            namespace=server_constants.CSE_SERVICE_NAMESPACE)
        msg = f"API extension '{server_constants.CSE_SERVICE_NAME}' already " \
              "exists in vCD. Use `cse upgrade` instead of 'cse install'."
        raise Exception(msg)
    except MissingRecordException:
        ext.add_extension(
            server_constants.CSE_SERVICE_NAME,
            server_constants.CSE_SERVICE_NAMESPACE,
            routing_key,
            exchange,
            patterns,
            description=description)
        msg = f"Registered {server_constants.CSE_SERVICE_NAME} as an API extension in vCD" # noqa: E501

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
        msg = ""
        try:
            schema_svc.get_entity_type(native_entity_type.get_id())
            msg = "Skipping creation of Defined Entity Type. Defined Entity Type already exists." # noqa: E501
        except cse_exception.DefSchemaServiceError:
            # TODO handle this part only if the entity type was not found
            native_entity_type = schema_svc.create_entity_type(native_entity_type)  # noqa: E501
            msg = "Successfully registered defined entity type"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
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
        system_org.add_rights([right_name_in_vcd])
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


def _setup_placement_policies(client, policy_list,
                              msg_update_callback=utils.NullPrinter(),
                              log_wire=False):
    """
    Create placement policies for each cluster type.

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
    pvdc_compute_policy = None
    try:
        try:
            pvdc_compute_policy = cpm.get_pvdc_compute_policy(
                server_constants.CSE_GLOBAL_PVDC_COMPUTE_POLICY_NAME)
            msg = "Skipping creation of global PVDC compute policy. Policy already exists" # noqa: E501
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
        except EntityNotFoundException:
            msg = "Creating global PVDC compute policy"
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
            pvdc_compute_policy = cpm.add_pvdc_compute_policy(
                server_constants.CSE_GLOBAL_PVDC_COMPUTE_POLICY_NAME,
                server_constants.CSE_GLOBAL_PVDC_COMPUTE_POLICY_DESCRIPTION)

        for policy in policy_list:
            try:
                cpm.get_vdc_compute_policy(policy, is_placement_policy=True)
                msg = f"Skipping creation of VDC placement policy '{policy}'. Policy already exists" # noqa: E501
                msg_update_callback.general(msg)
                INSTALL_LOGGER.info(msg)
            except EntityNotFoundException:
                msg = f"Creating placement policy '{policy}'"
                msg_update_callback.general(msg)
                INSTALL_LOGGER.info(msg)
                cpm.add_vdc_compute_policy(
                    policy, pvdc_compute_policy_id=pvdc_compute_policy['id'])
    except cse_exception.GlobalPvdcComputePolicyNotSupported:
        msg = "Global PVDC compute policies are not supported." \
              "Skipping creation of placement policy."
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)


def _install_all_templates(
        client, config, skip_template_creation, force_create, retain_temp_vapp,
        ssh_key, msg_update_callback=utils.NullPrinter()):
    if skip_template_creation:
        msg = "Skipping creation of templates."
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)
    else:
        # read remote template cookbook, download all scripts
        rtm = RemoteTemplateManager(
            remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'], # noqa: E501
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)
        remote_template_cookbook = rtm.get_remote_template_cookbook()

        # create all templates defined in cookbook
        for template in remote_template_cookbook['templates']:
            # TODO tag created templates with placement policies
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
                msg_update_callback=msg_update_callback)


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
        ssh_key, msg_update_callback=utils.NullPrinter()):
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
        if template.get(server_constants.RemoteTemplateKey.KIND) not in shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES: # noqa: E501
            raise ValueError(f"Cluster kind is {template.get(server_constants.RemoteTemplateKey.KIND)}" # noqa: E501
                             f" Expected {shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES}") # noqa: E501
        build_params[templateBuildKey.CSE_PLACEMENT_POLICY] = template.get(server_constants.RemoteTemplateKey.KIND) # noqa: E501
    builder = TemplateBuilder(client, client, build_params, ssh_key=ssh_key,
                              logger=INSTALL_LOGGER,
                              msg_update_callback=msg_update_callback)
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
        # Todo: Record telemetry detail call

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

        try:
            ext_cse_version, ext_vcd_api_version = \
                parse_cse_extension_description(client)
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
        except MissingRecordException:
            msg = "CSE api extension not registered with vCD. Please use " \
                  "`cse install' instead of 'cse upgrade'."
            raise Exception(msg)

        target_vcd_api_version = config['vcd']['api_version']
        target_cse_version = utils.get_installed_cse_version()

        # Handle various upgrade scenarios
        # Post CSE 3.0.0 only the following upgrades should be allowed
        # CSE X.Y.Z -> CSE X+1.0.0, CSE X.Y+1.0, X.Y.Z+1
        # vCD api X -> vCD api X+ (as supported by CSE and pyvcloud)

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
        cse_2_6_0 = semantic_version.Version('2.6.0')
        cse_3_0_0 = semantic_version.Version('3.0.0')
        if ext_cse_version in \
                (server_constants.UNKNOWN_CSE_VERSION, cse_2_6_0, cse_3_0_0):
            if target_vcd_api_version in (vCDApiVersion.VERSION_33.value,
                                          vCDApiVersion.VERSION_34.value):
                _legacy_upgrade_to_33_34(
                    client=client,
                    config=config,
                    ext_vcd_api_version=ext_vcd_api_version,
                    skip_template_creation=skip_template_creation,
                    ssh_key=ssh_key,
                    retain_temp_vapp=retain_temp_vapp,
                    admin_password=admin_password,
                    msg_update_callback=msg_update_callback)
            elif target_vcd_api_version in (vCDApiVersion.VERSION_35.value):
                _upgrade_to_35(
                    client=client,
                    config=config,
                    ext_vcd_api_version=ext_vcd_api_version,
                    skip_template_creation=skip_template_creation,
                    ssh_key=ssh_key,
                    retain_temp_vapp=retain_temp_vapp,
                    admin_password=admin_password,
                    msg_update_callback=msg_update_callback,
                    log_wire=log_wire)
            else:
                raise Exception(update_path_not_valid_msg)
        else:
            raise Exception(update_path_not_valid_msg)

        # Todo: Telemetry - Record successful upgrade

        msg = "Upgraded CSE successfully."
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)
    except Exception:
        msg_update_callback.error(
            "CSE Installation Error. Check CSE install logs")
        INSTALL_LOGGER.error("CSE Installation Error", exc_info=True)
        # Todo: Telemetry - Record failed upgrade
        raise
    finally:
        if client is not None:
            client.logout()


def _update_cse_extension(client, routing_key, exchange,
                          target_vcd_api_version,
                          msg_update_callback=utils.NullPrinter()):
    """."""
    ext = api_extension.APIExtension(client)
    patterns = [
        f'/api/{server_constants.CSE_SERVICE_NAME}',
        f'/api/{server_constants.CSE_SERVICE_NAME}/.*',
        f'/api/{server_constants.PKS_SERVICE_NAME}',
        f'/api/{server_constants.PKS_SERVICE_NAME}/.*',
    ]

    description = _construct_cse_extension_description(target_vcd_api_version)
    msg = None

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
        patterns=patterns,
        namespace=server_constants.CSE_SERVICE_NAMESPACE)

    msg = f"Updated API extension '{server_constants.CSE_SERVICE_NAME}' in vCD"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _legacy_upgrade_to_33_34(client, config, ext_vcd_api_version,
                             skip_template_creation, ssh_key,
                             retain_temp_vapp, admin_password,
                             msg_update_callback=utils.NullPrinter()):
    # create amqp exchange if it doesn't exist
    amqp = config['amqp']
    _create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                          amqp['vhost'], amqp['ssl'], amqp['username'],
                          amqp['password'],
                          msg_update_callback=msg_update_callback)

    # update cse api extension
    _update_cse_extension(
        client=client,
        routing_key=amqp['routing_key'],
        exchange=amqp['exchange'],
        target_vcd_api_version=config['vcd']['api_version'],
        msg_update_callback=msg_update_callback)

    # Recreate all supported templates
    _install_all_templates(
        client=client,
        config=config,
        skip_template_creation=skip_template_creation,
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


def _upgrade_to_35(client, config, ext_vcd_api_version,
                   skip_template_creation, ssh_key, retain_temp_vapp,
                   admin_password, msg_update_callback=utils.NullPrinter(),
                   log_wire=False):
    # Update amqp exchange
    _create_amqp_exchange(
        exchange_name=config['amqp']['exchange'],
        host=config['amqp']['host'],
        port=config['amqp']['port'],
        vhost=config['amqp']['vhost'],
        use_ssl=config['amqp']['ssl'],
        username=config['amqp']['username'],
        password=config['amqp']['password'],
        msg_update_callback=msg_update_callback)

    # Update cse api extension (along with api end points)
    _update_cse_extension(
        client=client,
        routing_key=config['amqp']['routing_key'],
        exchange=config['amqp']['exchange'],
        target_vcd_api_version=config['vcd']['api_version'],
        msg_update_callback=msg_update_callback)

    # Add global placement polcies
    _setup_placement_policies(
        client=client,
        policy_list=shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    # Register def schema
    _register_def_schema(
        client=client,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    # Recreate all supported templates
    _install_all_templates(
        client=client,
        config=config,
        skip_template_creation=skip_template_creation,
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
    _assign_placement_policy_to_vdc_with_existing_clusters(
        client=client,
        cse_clusters=clusters,
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
        log_wire=log_wire)


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
                server_constants.ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME) # noqa: E501
            client.get_task_monitor().wait_for_success(task)

            new_metadata_to_add = {
                server_constants.ClusterMetadataKey.TEMPLATE_NAME: new_template_name, # noqa: E501
                server_constants.ClusterMetadataKey.TEMPLATE_REVISION: 0
            }
            task = vapp.set_multiple_metadata(new_metadata_to_add)
            client.get_task_monitor().wait_for_success(task)

        # This step uses data from the newly updated cse.template.name and
        # cse.template.revision metadata fields as well as github history
        # to add [cse.os, cse.docker.version, cse.kubernetes,
        # cse.kubernetes.version, cse.cni, cse.cni.version] to the clusters.
        vapp.reload()
        metadata_dict = \
            pyvcloud_vcd_utils.metadata_to_dict(vapp.get_metadata())
        template_name = metadata_dict.get(
            server_constants.ClusterMetadataKey.TEMPLATE_NAME)
        template_revision = str(metadata_dict.get(
            server_constants.ClusterMetadataKey.TEMPLATE_REVISION, 0))
        cse_version = metadata_dict.get(
            server_constants.ClusterMetadataKey.CSE_VERSION)

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

        os = tokens[0]
        # old clusters that were converted can have non-existent template name
        # that has 'k8s' string in it instead of 'k8'
        if k8s_data[0] in ('k8', 'k8s'):
            k8s_distribution = 'upstream'
        elif k8s_data[0] in ('tkg', 'tkgp'):
            k8s_distribution = 'TKG+'
        else:
            k8s_distribution = "Unknown Kubernetes distribution"
        cni = cni_data[0]
        cni_version = cni_data[1]
        k8s_version, docker_version = \
            _get_k8s_and_docker_versions_from_history(
                template_name=template_name,
                template_revision=template_revision,
                cse_version=cse_version)

        # Try to determine the above values using template definition
        org_name = config['broker']['org']
        catalog_name = config['broker']['catalog']
        k8_templates = ltm.get_all_k8s_local_template_definition(
            client=client, catalog_name=catalog_name, org_name=org_name)
        for k8_template in k8_templates:
            if (str(k8_template[server_constants.LocalTemplateKey.REVISION]), k8_template[server_constants.LocalTemplateKey.NAME]) == (template_revision, template_name):  # noqa: E501
                if k8_template.get(server_constants.LocalTemplateKey.OS):
                    os = k8_template.get(server_constants.LocalTemplateKey.OS)
                if k8_template.get(server_constants.LocalTemplateKey.KUBERNETES): # noqa: E501
                    k8s_distribution = k8_template.get(server_constants.LocalTemplateKey.KUBERNETES) # noqa: E501
                if k8_template.get(server_constants.LocalTemplateKey.KUBERNETES_VERSION): # noqa: E501
                    k8s_version = k8_template[server_constants.LocalTemplateKey.KUBERNETES_VERSION] # noqa: E501
                if k8_template.get(server_constants.LocalTemplateKey.CNI):
                    cni = k8_template.get(server_constants.LocalTemplateKey.CNI) # noqa: E501
                if k8_template.get(server_constants.LocalTemplateKey.CNI_VERSION): # noqa: E501
                    cni_version = k8_template.get(server_constants.LocalTemplateKey.CNI_VERSION) # noqa: E501
                if k8_template.get(server_constants.LocalTemplateKey.DOCKER_VERSION): # noqa: E501
                    docker_version = k8_template[server_constants.LocalTemplateKey.DOCKER_VERSION] # noqa: E501
                break

        new_metadata = {
            server_constants.ClusterMetadataKey.OS: os,
            server_constants.ClusterMetadataKey.DOCKER_VERSION: docker_version,
            server_constants.ClusterMetadataKey.KUBERNETES: k8s_distribution,
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
        server_constants.ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME)
    if not old_template_name:
        return

    new_template_name = None
    cse_version = metadata_dict.get(
        server_constants.ClusterMetadataKey.CSE_VERSION)
    if 'photon' in old_template_name:
        new_template_name = 'photon-v2'
        if cse_version in ('1.0.0'):
            new_template_name += '_k8-1.8_weave-2.0.5'
        elif cse_version in ('1.1.0', '1.2.0', '1.2.1', '1.2.2', '1.2.3', '1.2.4'): # noqa: E501
            new_template_name += '_k8-1.9_weave-2.3.0'
        elif cse_version in ('1.2.5', '1.2.6', '1.2.7',): # noqa: E501
            new_template_name += '_k8-1.10_weave-2.3.0'
        elif cse_version in ('2.0.0'):
            new_template_name += '_k8-1.12_weave-2.3.0'
        else:
            new_template_name += '_k8-0.0_weave-0.0.0'
    elif 'ubuntu' in old_template_name:
        new_template_name = 'ubuntu-16.04'
        if cse_version in ('1.0.0'):
            new_template_name += '_k8-1.9_weave-2.1.3'
        elif cse_version in ('1.1.0', '1.2.0', '1.2.1', '1.2.2', '1.2.3', '1.2.4', '1.2.5', '1.2.6', '1.2.7'): # noqa: E501
            new_template_name += '_k8-1.10_weave-2.3.0'
        elif cse_version in ('2.0.0'):
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
            if cse_version in ('1.2.7'):
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
                    msg = "Undeploying vm."
                    INSTALL_LOGGER.info(msg)
                    msg_update_callback.info(msg)
                    task = vm.undeploy()
                    client.get_task_monitor().wait_for_success(task)
                    msg = "Successfully undeployed vm"
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
            shared_constants.NATIVE_CLUSTER_RUNTIME_POLICY
    elif 'tkg' in template_name or 'tkgp' in template_name:
        policy_name = \
            shared_constants.TKG_PLUS_CLUSTER_RUNTIME_POLICY
    else:
        raise Exception(f"Unknown kind of template '{template_name}'.")

    return policy_name


def _assign_placement_policy_to_vdc_with_existing_clusters(
        client,
        cse_clusters,
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):
    msg = "Assigning placement compute policy(s) to vDC(s) hosting existing CSE clusters." # noqa: E501
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    msg = "Identifying vDC(s) that are currently hosting CSE clusters."
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    tkg_plus_ovdcs = []
    native_ovdcs = []
    vdc_names = {}
    for cluster in cse_clusters:
        try:
            policy_name = _get_placement_policy_name_from_template_name(
                cluster['template_name'])
        except Exception:
            msg = f"Invalid template '{cluster['template_name']}' for cluster '{cluster['name']}'." # noqa: E501
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)
            continue

        if policy_name == shared_constants.NATIVE_CLUSTER_RUNTIME_POLICY:
            id = cluster['vdc_id']
            native_ovdcs.append(id)
            vdc_names[id] = cluster['vdc_name']
        elif policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_POLICY:
            id = cluster['vdc_id']
            tkg_plus_ovdcs.append(id)
            vdc_names[id] = cluster['vdc_name']

    native_ovdcs = set(native_ovdcs)
    tkg_plus_ovdcs = set(tkg_plus_ovdcs)

    msg = f"Found {len(native_ovdcs)} vDC(s) hosting NATIVE CSE custers " \
          f"and {len(tkg_plus_ovdcs)} vDC(s) hosting TKG PLUS clusters."
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    cpm = \
        compute_policy_manager.ComputePolicyManager(client, log_wire=log_wire)
    native_policy = cpm.get_vdc_compute_policy(
        policy_name=shared_constants.NATIVE_CLUSTER_RUNTIME_POLICY,
        is_placement_policy=True)
    tkg_plus_policy = cpm.get_vdc_compute_policy(
        policy_name=shared_constants.TKG_PLUS_CLUSTER_RUNTIME_POLICY,
        is_placement_policy=True)

    if native_ovdcs:
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
        for vdc_id in tkg_plus_ovdcs:
            cpm.add_compute_policy_to_vdc(
                vdc_id=vdc_id,
                compute_policy_href=tkg_plus_policy['href'])
            msg = "Added compute policy " \
                  f"'{tkg_plus_policy['display_name']}' to vDC " \
                  f"'{vdc_names[vdc_id]}'"
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
            vdc_sizing_policies = cpm.list_vdc_sizing_policies_on_vdc(vdc_id)
            if vdc_sizing_policies:
                for policy in vdc_sizing_policies:
                    msg = f"Processing Policy : '{policy['name']}' on Org VDC : '{vdc_name}'" # noqa: E501
                    msg_update_callback.info(msg)
                    INSTALL_LOGGER.info(msg)

                    all_cse_policy_names.append(policy['name'])
                    task_data = cpm.remove_vdc_compute_policy_from_vdc(
                        ovdc_id=vdc_id,
                        compute_policy_href=policy['href'],
                        force=True)
                    fake_task_object = {'href': task_data['task_href']}
                    client.get_task_monitor().wait_for_status(fake_task_object) # noqa: E501

                    msg = f"Removed Policy : '{policy['name']}' from Org VDC : '{vdc_name}'" # noqa: E501
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

            cpm.delete_vdc_compute_policy(policy_name=policy_name)

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
            def_entity = entity_svc.get_entity(cluster_id)
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

        if policy_name == shared_constants.NATIVE_CLUSTER_RUNTIME_POLICY:
            kind = def_utils.ClusterEntityKind.NATIVE.value
        elif policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_POLICY:
            kind = def_utils.ClusterEntityKind.TANZU_PLUS

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

        cluster_entity = def_models.ClusterEntity(
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
                master_ip=cluster['leader_endpoint'],
                kubernetes=f"{cluster['kubernetes']} {cluster['kubernetes_version']}", # noqa: E501
                cni=f"{cluster['cni']} {cluster['cni_version']}",
                os=cluster['os'],
                docker_version=cluster['docker_version'],
                nodes=def_models.Nodes(
                    master=def_models.Node(
                        name=cluster['master_nodes'][0]['name'],
                        ip=cluster['master_nodes'][0]['ipAddress']),
                    workers=worker_nodes,
                    nfs=nfs_nodes)),
            metadata=def_models.Metadata(
                org_name=cluster['org_name'],
                ovdc_name=cluster['vdc_name'],
                cluster_name=cluster['name']),
            api_version="")

        def_entity = def_models.DefEntity(entity=cluster_entity)
        entity_svc.create_entity(native_entity_type.id, entity=def_entity)
        def_entity = entity_svc.get_native_entity_by_name(cluster['name'])
        def_entity_id = def_entity.id
        def_entity.externalId = cluster['vapp_href']
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
