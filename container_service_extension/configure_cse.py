# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pika
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org

from container_service_extension.config_validator import get_validated_config
from container_service_extension.exceptions import AmqpError
from container_service_extension.local_template_manager import \
    set_metadata_on_catalog_item
from container_service_extension.logger import configure_install_logger
from container_service_extension.logger import INSTALL_LOG_FILEPATH
from container_service_extension.logger import INSTALL_LOGGER as LOGGER
from container_service_extension.logger import INSTALL_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.nsxt.nsxt_client import NSXTClient
from container_service_extension.pyvcloud_utils import catalog_exists
from container_service_extension.pyvcloud_utils import create_and_share_catalog
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.remote_template_manager import \
    get_revisioned_template_name
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
from container_service_extension.server_constants import \
    CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY, CSE_NATIVE_DEPLOY_RIGHT_CATEGORY, \
    CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION, CSE_NATIVE_DEPLOY_RIGHT_NAME, \
    CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY, CSE_PKS_DEPLOY_RIGHT_CATEGORY, \
    CSE_PKS_DEPLOY_RIGHT_DESCRIPTION, CSE_PKS_DEPLOY_RIGHT_NAME, \
    CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, EXCHANGE_TYPE, \
    SYSTEM_ORG_NAME # noqa: H301
from container_service_extension.template_builder import TemplateBuilder
from container_service_extension.utils import ConsoleMessagePrinter
from container_service_extension.vsphere_utils import populate_vsphere_list


def check_cse_installation(config, msg_update_callback=None):
    """Ensure that CSE is installed on vCD according to the config file.

    Checks,
        1. AMQP exchange exists
        2. CSE is registered with vCD,
        3. CSE K8 catalog exists

    :param dict config: config yaml file as a dictionary
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises Exception: if CSE is not registered to vCD as an extension, or if
        specified catalog does not exist, or if specified template(s) do not
        exist.
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
        org_name = config['broker']['org']
        org = get_org(client, org_name=org_name)
        catalog_name = config['broker']['catalog']
        if catalog_exists(org, catalog_name):
            if msg_update_callback:
                msg_update_callback.general(f"Found catalog '{catalog_name}'")
        else:
            msg = f"Catalog '{catalog_name}' not found"
            if msg_update_callback:
                msg_update_callback.error(msg)
            err_msgs.append(msg)
    finally:
        if client:
            client.logout()

    if err_msgs:
        raise Exception(err_msgs)
    if msg_update_callback:
        msg_update_callback.general("CSE installation is valid")


def install_cse(ctx, config_file_name='config.yaml',
                skip_create_templates=True, update=False,
                retain_temp_vapp=False, ssh_key=None,
                msg_update_callback=None):
    """Handle logistics for CSE installation.

    Handles decision making for configuring AMQP exchange/settings,
    extension registration, catalog setup, and template creation.

    :param click.core.Context ctx:
    :param str config_file_name: config file name.
    :param bool skip_create_templates: If True, skip creating the templates.
    :param bool update: if True and templates already exist in vCD,
        overwrites existing templates.
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    configure_install_logger()

    config = get_validated_config(config_file_name,
                                  msg_update_callback=msg_update_callback)
    populate_vsphere_list(config['vcs'])

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
                        log_file=INSTALL_WIRELOG_FILEPATH,
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
        _create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                              amqp['vhost'], amqp['ssl'], amqp['username'],
                              amqp['password'],
                              msg_update_callback=msg_update_callback)

        # register or update cse on vCD
        _register_cse(client, amqp['routing_key'], amqp['exchange'],
                      msg_update_callback=msg_update_callback)

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

        org_name = config['broker']['org']
        catalog_name = config['broker']['catalog']

        # set up cse catalog
        org = get_org(client, org_name=org_name)
        create_and_share_catalog(
            org, catalog_name, catalog_desc='CSE templates',
            msg_update_callback=msg_update_callback)

        if skip_create_templates:
            msg = "Skipping creation of templates."
            if msg_update_callback:
                msg_update_callback.info(msg)
            LOGGER.warning(msg)
        else:
            # read remote template cookbook, download all scripts
            rtm = RemoteTemplateManager(
                remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'], # noqa: E501
                logger=LOGGER, msg_update_callback=ConsoleMessagePrinter())
            remote_template_cookbook = rtm.get_remote_template_cookbook()

            # create all templates mentioned in cookbook
            for template in remote_template_cookbook['templates']:
                rtm.download_template_scripts(template_name=template['name'],
                                              revision=template['revision'],
                                              force_overwrite=update)
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
                    'ip_allocation_mode': config['broker']['ip_allocation_mode'], # noqa: E501
                    'storage_profile': config['broker']['storage_profile']
                }
                builder = TemplateBuilder(
                    client, client, build_params, ssh_key=ssh_key,
                    logger=LOGGER, msg_update_callback=ConsoleMessagePrinter())
                builder.build(force_recreate=update,
                              retain_temp_vapp=retain_temp_vapp)

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


def _create_amqp_exchange(exchange_name, host, port, vhost, use_ssl,
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


def _register_cse(client, routing_key, exchange, msg_update_callback=None):
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


def _register_right(client, right_name, description, category, bundle_key,
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
        # Registering a right via api extension end point, auto assigns it to
        # System org.
        msg = f"Registering Right: {right_name} in vCD"
        if msg_update_callback:
            msg_update_callback.general(msg)
        LOGGER.info(msg)
        ext.add_service_right(
            right_name, CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, description,
            category, bundle_key)
