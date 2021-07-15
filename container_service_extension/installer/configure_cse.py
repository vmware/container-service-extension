# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import json
from typing import Dict, List, Union

import pika
import pyvcloud.vcd.api_extension as api_extension
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
import requests
import semantic_version

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.common.utils.vsphere_utils import populate_vsphere_list  # noqa: E501
import container_service_extension.exception.exceptions as cse_exception
from container_service_extension.installer.right_bundle_manager import RightBundleManager  # noqa: E501
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
from container_service_extension.installer.templates.remote_template_manager import RemoteTemplateManager  # noqa: E501
import container_service_extension.installer.templates.template_builder as template_builder  # noqa: E501
from container_service_extension.lib.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.lib.nsxt.nsxt_client import NSXTClient
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import OperationStatus
from container_service_extension.lib.telemetry.constants import PayloadKey
from container_service_extension.lib.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.lib.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.lib.telemetry.telemetry_utils import \
    store_telemetry_settings
from container_service_extension.logging.logger import INSTALL_LOGGER
from container_service_extension.logging.logger import INSTALL_WIRELOG_FILEPATH
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.logging.logger import SERVER_CLI_LOGGER
from container_service_extension.logging.logger import SERVER_CLI_WIRELOG_FILEPATH  # noqa: E501
from container_service_extension.logging.logger import SERVER_CLOUDAPI_WIRE_LOGGER  # noqa: E501
from container_service_extension.logging.logger import SERVER_NSXT_WIRE_LOGGER
from container_service_extension.mqi.mqtt_extension_manager import \
    MQTTExtensionManager
from container_service_extension.rde.behaviors.behavior_model import Behavior, BehaviorAclEntry  # noqa: E501
from container_service_extension.rde.behaviors.behavior_service import BehaviorService  # noqa: E501
import container_service_extension.rde.common.entity_service as def_entity_svc
import container_service_extension.rde.constants as def_constants
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.models.rde_2_0_0 as rde_2_x
from container_service_extension.rde.models.rde_factory import get_rde_model
import container_service_extension.rde.schema_service as def_schema_svc
import container_service_extension.rde.utils as def_utils
import container_service_extension.server.compute_policy_manager as compute_policy_manager  # noqa: E501
from container_service_extension.server.vcdbroker import get_all_clusters as get_all_cse_clusters  # noqa: E501


API_FILTER_PATTERNS = [
    f'/api/{ shared_constants.CSE_URL_FRAGMENT}',
    f'/api/{ shared_constants.CSE_URL_FRAGMENT}/.*',
    f'/api/{ shared_constants.PKS_URL_FRAGMENT}',
    f'/api/{ shared_constants.PKS_URL_FRAGMENT}/.*',
]

LEGACY_MODE = False


def check_cse_installation(config, msg_update_callback=utils.NullPrinter()):
    """Ensure that CSE is installed on vCD according to the config file.

    Checks,
        1. AMQP exchange exists
        2. CSE is registered with vCD,
        3. CSE K8 catalog exists

    :param dict config: config yaml file as a dictionary
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501

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

        # Since the config param has been read from file by
        # get_validated_config method, we can safely use the
        # default_api_version key, it will be set to the highest api
        # version supported by VCD and CSE.
        client = Client(config['vcd']['host'],
                        api_version=config['service']['default_api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            shared_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)

        if server_utils.should_use_mqtt_protocol(config):
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


def get_extension_description(sys_admin_client, is_mqtt_extension):
    """Retrieve CSE extension description.

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

    return description


def parse_cse_extension_description(description: str):
    """Parse CSE extension description.

    :param str description:
    """
    # The description on the extension can be in one of the following formats
    # For 3.0.x it will be a single line of text with comma separated
    # values for cse_version and api_version
    # 3.1.x and above it will be a json object with arbitrary key
    # value pairs. But cse_version will be a mandatory key, and
    # unless we remove the support for running CSE in legacy mode
    # the key legacy_mode is also mandatory
    try:
        result = json.loads(description)
        result[server_constants.CSE_VERSION_KEY] = \
            semantic_version.Version(result[server_constants.CSE_VERSION_KEY])
        result[server_constants.RDE_VERSION_IN_USE_KEY] = \
            semantic_version.Version(result[server_constants.RDE_VERSION_IN_USE_KEY])  # noqa: E501
    except json.decoder.JSONDecodeError:
        cse_version = server_constants.UNKNOWN_CSE_VERSION
        legacy_mode = True
        rde_version = semantic_version.Version("0.0.0")
        tokens = description.split(",")
        if len(tokens) == 2:
            cse_tokens = tokens[0].split("-")
            if len(cse_tokens) == 2:
                cse_version = semantic_version.Version(cse_tokens[1])
            vcd_api_tokens = tokens[1].split("-")
            if len(vcd_api_tokens) == 2:
                vcd_api_version = vcd_api_tokens[1]
                if float(vcd_api_version) >= 35.0:
                    legacy_mode = False
        result = {
            server_constants.CSE_VERSION_KEY: cse_version,
            server_constants.LEGACY_MODE_KEY: legacy_mode,
            server_constants.RDE_VERSION_IN_USE_KEY: rde_version
        }
    return result


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
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501

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

    # Set global legacy_mode flag
    global LEGACY_MODE
    LEGACY_MODE = config['service']['legacy_mode']

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

        # Since the config param has been read from file by
        # get_validated_config method, we can safely use the
        # default_api_version key, it will be set to the highest api
        # version supported by VCD and CSE.
        client = Client(config['vcd']['host'],
                        api_version=config['service']['default_api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            shared_constants.SYSTEM_ORG_NAME,
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
        is_tkg_plus_enabled = server_utils.is_tkg_plus_enabled(config=config)  # noqa: E501
        _setup_placement_policies(
            client=client,
            policy_list=shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES,
            is_tkg_plus_enabled=is_tkg_plus_enabled,
            msg_update_callback=msg_update_callback,
            log_wire=log_wire)

        # set up cse catalog
        org = vcd_utils.get_org(client, org_name=config['broker']['org'])
        vcd_utils.create_and_share_catalog(
            org, config['broker']['catalog'], catalog_desc='CSE templates',
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)

        if skip_template_creation:
            msg = """Skipping creation of templates.
Please note, CSE server startup needs at least one valid template.
Please create CSE K8s template(s) using the command `cse template install`."""
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
        if server_utils.should_use_mqtt_protocol(config):
            description = \
                _construct_cse_extension_description(
                    config['service']['rde_version_in_use']
                )
            _register_cse_as_mqtt_extension(
                client,
                description=description,
                msg_update_callback=msg_update_callback)  # noqa: E501
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
                rde_version_in_use=config['service']['rde_version_in_use'],
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
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501
    """
    populate_vsphere_list(config['vcs'])

    msg = f"Installing template '{template_name}' at revision " \
          f"'{template_revision}' on vCloud Director using config file " \
          f"'{config_file_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)
    global LEGACY_MODE
    LEGACY_MODE = config['service']['legacy_mode']

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

        # Since the config param has been read from file by
        # get_validated_config method, we can safely use the
        # default_api_version key, it will be set to the highest api
        # version supported by VCD and CSE.
        client = Client(config['vcd']['host'],
                        api_version=config['service']['default_api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            shared_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # Handle missing extension
        existing_ext_type = _get_existing_extension_type(client)
        if existing_ext_type == server_constants.ExtensionType.NONE:
            msg = "CSE installation not found. Please install CSE first " \
                "using`cse install'."
            raise Exception(msg)

        is_mqtt_extension = existing_ext_type == server_constants.ExtensionType.MQTT  # noqa: E501
        ext_description = get_extension_description(
            client,
            is_mqtt_extension=is_mqtt_extension
        )
        dikt = parse_cse_extension_description(ext_description)
        ext_in_legacy_mode = dikt[server_constants.LEGACY_MODE_KEY]

        if ext_in_legacy_mode != LEGACY_MODE:
            msg = "CSE extension found installed in " \
                f"{'legacy' if ext_in_legacy_mode else 'non-legacy'} mode." \
                "Configuration file specifies otherwise. Unable to install " \
                "templates."
            raise Exception(msg)

        # read remote template cookbook
        rtm = RemoteTemplateManager(
            remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'],  # noqa: E501
            legacy_mode=LEGACY_MODE,
            logger=INSTALL_LOGGER, msg_update_callback=msg_update_callback)

        rtm.get_filtered_remote_template_cookbook()
        remote_template_keys = server_utils.get_template_descriptor_keys(
            rtm.cookbook_version)

        found_template = False
        for template in rtm.filtered_cookbook['templates']:
            template_name_matched = template_name in (template[remote_template_keys.NAME], '*')  # noqa: E501
            template_revision_matched = \
                str(template_revision) in (str(template[remote_template_keys.REVISION]), '*')  # noqa: E501
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
                    is_tkg_plus_enabled=server_utils.is_tkg_plus_enabled(config),  # noqa: E501
                    msg_update_callback=msg_update_callback)

        if not LEGACY_MODE and template_name != "*" and not found_template:
            # Do not raise template unsupported exception
            #   if template name is "*"
            # Raise TemplateUnsupportedException if -
            # if template_revision is *, check if a template with name
            #   template_name is in unfiltered cookbook
            # if (template_name, template_revision) is in unfiltered cookbook
            for template in rtm.unfiltered_cookbook['templates']:
                template_name_matched = template[remote_template_keys.NAME] == template_name  # noqa: E501
                template_revision_matched = template_revision in (str(template[remote_template_keys.REVISION]), '*')  # noqa: E501
                if template_name_matched and template_revision_matched:
                    msg = f"Template '{template_name}' at revision " \
                          f"'{template_revision}' is not supported by " \
                          f"CSE {server_utils.get_installed_cse_version()}"
                    INSTALL_LOGGER.debug(msg)
                    msg_update_callback.general(msg)
                    raise Exception(msg)
        if not found_template:
            msg = f"Template '{template_name}' at revision " \
                  f"'{template_revision}' not found in " \
                  f"remote template cookbook."
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


# For CSE 3.1 the following configuration can be the starting states
# CSE 3.0.x, api v33.0
# CSE 3.0.x, api v34.0
# CSE 3.0.x, api v35.0
# api v33.0 and v34.0 will map to legacy_mode = True
#
# The target configurations can be
# CSE 3.1, vCD 10.1, legacy_mode = True
# CSE 3.1, vCD 10.2, legacy_mode = True
# CSE 3.1, vCD 10.2, legacy_mode = False --> leads to RDE 1.0.0
# CSE 3.1, vCD 10.3, legacy_mode = True
# CSE 3.1, vCD 10.3, legacy_mode = False --> leads to RDE 2.0.0
#
# Upgrades from any other CSE version is not allowed
# Upgrade from legacy_mode = False to True is not allowed
# Downgrade of CSE version is not allowed
# Changing message bus from MQTT to AMQP is not allowed
def upgrade_cse(config_file_name, config, skip_template_creation,
                ssh_key, retain_temp_vapp,
                msg_update_callback=utils.NullPrinter()):
    """Handle logistics for upgrading CSE to 3.1.

    Handles decision making for configuring AMQP exchange/settings,
    defined entity schema registration for CSE running in non legacy mode,
    extension registration, catalog setup and template creation, removing old
    CSE sizing based compute policies, assigning the new placement compute
    policy to concerned org VDCs, and create DEF entity for existing clusters.

    :param str config_file_name: config file name.
    :param dict config: content of the CSE config file.
    :param bool skip_template_creation: If True, skip creating the templates.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param bool retain_temp_vapp: if True, temporary vApp will not destroyed,
        so the user can ssh into and debug the vm.
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501
    """
    populate_vsphere_list(config['vcs'])

    msg = f"Upgrading CSE on vCloud Director using config file " \
          f"'{config_file_name}'"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    # Set global LEGACY_MODE value
    global LEGACY_MODE
    LEGACY_MODE = config['service']['legacy_mode']

    client = None
    try:
        log_filename = None
        log_wire = utils.str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = INSTALL_WIRELOG_FILEPATH

        # Since the config param has been read from file by
        # get_validated_config method, we can safely use the
        # default_api_version key, it will be set to the highest api
        # version supported by VCD and CSE.
        client = Client(config['vcd']['host'],
                        api_version=config['service']['default_api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            shared_constants.SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        msg_update_callback.general(msg)
        INSTALL_LOGGER.info(msg)

        # Handle missing extension and upgrading from MQTT -> AMQP extension
        existing_ext_type = _get_existing_extension_type(client)
        is_source_extension_mqtt = existing_ext_type == server_constants.ExtensionType.MQTT  # noqa: E501
        if existing_ext_type == server_constants.ExtensionType.NONE:
            msg = "No existing extension.  Please use `cse install' instead " \
                "of 'cse upgrade'."
            raise Exception(msg)
        elif is_source_extension_mqtt and not server_utils.should_use_mqtt_protocol(config):  # noqa: E501
            # Upgrading from MQTT to AMQP extension
            msg = "Upgrading from MQTT extension to AMQP extension is not " \
                  "supported"
            raise Exception(msg)

        ext_description = get_extension_description(
            client,
            is_mqtt_extension=is_source_extension_mqtt
        )
        dikt = parse_cse_extension_description(ext_description)
        ext_cse_version = dikt[server_constants.CSE_VERSION_KEY]
        ext_in_legacy_mode = dikt[server_constants.LEGACY_MODE_KEY]
        # ext_rde_in_use = dikt[server_constants.RDE_VERSION_IN_USE_KEY]

        if ext_cse_version == server_constants.UNKNOWN_CSE_VERSION:
            msg = "Found CSE api extension registered with vCD, but " \
                  "couldn't determine version of CSE used previously. " \
                  "Unable to upgrade to CSE 3.1. Please first upgrade " \
                  "CSE to 3.0."
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)
        else:
            msg = "Found CSE api extension registered by CSE " \
                  f"'{ext_cse_version}' in " \
                  f"{'legacy' if ext_in_legacy_mode else 'non-legacy'} mode."
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)

        target_cse_version = server_utils.get_installed_cse_version()

        # ToDo: Record `legacy mode` flag instead of api versions
        # ToDo: Record 'rde version' in use flag
        telemetry_data = {
            PayloadKey.SOURCE_CSE_VERSION: str(ext_cse_version),
            PayloadKey.SOURCE_VCD_API_VERSION: "",
            PayloadKey.TARGET_CSE_VERSION: str(target_cse_version),
            PayloadKey.TARGET_VCD_API_VERSION: "",
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
        # It should be noted that if CSE X.Y.Z is upgradable to CSE X'.Y'.Z',
        # then CSE X.Y.Z+ should also be allowed to upgrade to CSE X'.Y'.Z'
        # irrespective of when these patches were released.

        target_cse_running_in_legacy_mode = LEGACY_MODE
        source_cse_running_in_legacy_mode = ext_in_legacy_mode

        # CSE version info in extension description is only applicable for
        # CSE 3.0.0+ versions.
        allowed_source_cse_versions = \
            semantic_version.SimpleSpec('>=3.0.0,<=3.1.0')
        valid_source_cse_installation = \
            allowed_source_cse_versions.match(ext_cse_version)

        upgrade_path_not_valid_msg = \
            f"CSE upgrade path (CSE '{ext_cse_version}'," \
            f"legacy_mode:{source_cse_running_in_legacy_mode}) -> "\
            f"(CSE '{target_cse_version}', " \
            f"legacy_mode:{target_cse_running_in_legacy_mode}) " \
            "is not supported."

        # Downgrade not supported
        if target_cse_version < ext_cse_version:
            raise Exception(upgrade_path_not_valid_msg)

        # Invalid source CSE installation
        if not valid_source_cse_installation:
            raise Exception(upgrade_path_not_valid_msg)

        # Non legacy -> Legacy mode not allowed
        if source_cse_running_in_legacy_mode != target_cse_running_in_legacy_mode and target_cse_running_in_legacy_mode:  # noqa: E501
            raise Exception(upgrade_path_not_valid_msg)

        # Upgrading from CSE 3.0.3 (non legacy) to CSE 3.1.0 should be
        # blocked, if TKGm compute policy is found in the system.
        cse_installation_with_tkgm_support = \
            semantic_version.SimpleSpec('>=3.0.3,<3.1.0')
        if cse_installation_with_tkgm_support.match(ext_cse_version) and \
                not source_cse_running_in_legacy_mode:
            cpm = compute_policy_manager.ComputePolicyManager(
                client, log_wire=log_wire
            )
            try:
                compute_policy_manager.get_cse_vdc_compute_policy(
                    cpm,
                    shared_constants.TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME,
                    is_placement_policy=True
                )
                found_tkgm_policy = True
            except EntityNotFoundException:
                found_tkgm_policy = False

            if found_tkgm_policy:
                upgrade_path_not_valid_msg += " TKGm runtime detected."
                raise Exception(upgrade_path_not_valid_msg)

        # Convert the existing AMQP extension to MQTT extension if
        # upgrading to non legacy mode. This will ensure that when
        # the existing legacy clusters are being processed, RDE creation
        # won't fail due to missing CSE exchange/channel.
        if not is_source_extension_mqtt and \
                not target_cse_running_in_legacy_mode:
            _deregister_cse_amqp_extension(client=client)
            _register_cse_as_mqtt_extension(
                client,
                description=ext_description,
                msg_update_callback=msg_update_callback)

        if source_cse_running_in_legacy_mode and target_cse_running_in_legacy_mode:  # noqa: E501
            _upgrade_to_cse_3_1_legacy(
                client=client,
                config=config,
                skip_template_creation=skip_template_creation,
                retain_temp_vapp=retain_temp_vapp,
                ssh_key=ssh_key,
                msg_update_callback=msg_update_callback)
        else:
            _upgrade_to_cse_3_1_non_legacy(
                client=client,
                config=config,
                skip_template_creation=skip_template_creation,
                retain_temp_vapp=retain_temp_vapp,
                ssh_key=ssh_key,
                msg_update_callback=msg_update_callback,
                log_wire=log_wire)

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


def configure_nsxt_for_cse(nsxt_servers,
                           log_wire=False,
                           msg_update_callback=utils.NullPrinter()):
    """Configure NSXT-T server for CSE.

    :param dict nsxt_servers: nsxt_server details
    :param Logger log_wire:
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501
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
                ncp_boundary_firewall_section_anchor_id=nsxt_server.get('distributed_firewall_section_anchor_id'))  # noqa: E501
    except Exception:
        msg_update_callback.error(
            "NSXT Configuration Error. Check CSE install logs")
        INSTALL_LOGGER.error("NSXT Configuration Error", exc_info=True)
        raise


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
                  f"{ server_constants.MQTT_API_FILTER_PATTERN}"
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


def _construct_cse_extension_description(
        rde_version_in_use: Union[semantic_version.Version, str]) -> str:
    cse_version = server_utils.get_installed_cse_version()
    global LEGACY_MODE
    if not rde_version_in_use:
        rde_version_in_use = semantic_version.Version("0.0.0")
    dikt = {
        server_constants.CSE_VERSION_KEY: str(cse_version),
        server_constants.LEGACY_MODE_KEY: LEGACY_MODE,
        server_constants.RDE_VERSION_IN_USE_KEY: str(rde_version_in_use)
    }

    description = json.dumps(dikt)
    return description


def _get_existing_extension_type(client):
    """Get the existing extension type.

    Only one extension type will be returned because having two extensions
        is prevented in install_cse.

    ::param Client client: client used to install cse server components

    :return: the current extension type: ExtensionType.MQTT, AMQP, or NONE
    :rtype: str
    """
    global LEGACY_MODE
    # If CSE is not installed in LEGACY_MODE check for MQTT extension
    if not LEGACY_MODE:
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


def _register_cse_as_mqtt_extension(client,
                                    description,
                                    msg_update_callback=utils.NullPrinter()):
    """Install the MQTT extension and api filter.

    :param Client client: client used to install cse server components
    :param str description:
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501

    :raises requests.exceptions.HTTPError: if the MQTT extension and api filter
        were not set up correctly
    """
    mqtt_ext_manager = MQTTExtensionManager(client)
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


def _register_cse_as_amqp_extension(client, routing_key, exchange,
                                    rde_version_in_use=None,
                                    msg_update_callback=utils.NullPrinter()):
    """Register CSE on vCD.

    :param pyvcloud.vcd.client.Client client:
    :param str routing_key:
    :param str exchange:
    :param semantic_version.Version rde_version_in_use:
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501
    """
    description = _construct_cse_extension_description(rde_version_in_use)

    # No need to check for existing extension because the calling function
    # (install_cse) already handles checking for an existing extension
    ext = api_extension.APIExtension(client)
    ext.add_extension(
        server_constants.CSE_SERVICE_NAME,
        server_constants.CSE_SERVICE_NAMESPACE,
        routing_key,
        exchange,
        API_FILTER_PATTERNS,
        description=description)

    msg = f"Registered { server_constants.CSE_SERVICE_NAME} as an API extension in vCD"  # noqa: E501
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


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
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501

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
    msg = f"Deleted MQTT extension '{ server_constants.CSE_SERVICE_NAME}'"
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


def _update_cse_mqtt_extension(client,
                               rde_version_in_use,
                               msg_update_callback=utils.NullPrinter()):
    """Update description and remove and add api filters."""
    mqtt_ext_manager = MQTTExtensionManager(client)

    description = _construct_cse_extension_description(rde_version_in_use)
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

    msg = f"Updated MQTT extension '{ server_constants.CSE_SERVICE_NAME}'"
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _update_cse_amqp_extension(client, routing_key, exchange,
                               rde_version_in_use=None,
                               msg_update_callback=utils.NullPrinter()):
    """."""
    ext = api_extension.APIExtension(client)

    description = _construct_cse_extension_description(rde_version_in_use)

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


def _update_user_role_with_right_bundle(
        right_bundle_name,
        client: Client,
        msg_update_callback=utils.NullPrinter(),
        logger_debug=NULL_LOGGER,
        log_wire=False):
    """Add defined entity rights to user's role.

    This method should only be called on valid configurations.
        In order to call this function, caller has to make sure that the
        contextual defined entity is already created inside VCD and
        corresponding right-bundle exists in VCD.
    The defined entity right bundle is created by VCD at the time of defined
        entity creation, dynamically. Hence, it doesn't exist before-hand
        (when user initiated the operation).

    :param str right_bundle_name:
    :param pyvcloud.vcd.client.Client client:
    :param core_utils.ConsoleMessagePrinter msg_update_callback:
    :param bool log_wire:
    """
    # Only a user from System Org can execute this function
    vcd_utils.raise_error_if_user_not_from_system_org(client)

    # Determine role name for the user
    role_name = vcd_utils.get_user_role_name(client)

    # Given that this user is sysadmin, Org must be System
    # If its not, we should receive an exception during one of the below
    # operations
    system_org = Org(client, resource=client.get_org())

    # Using the Org, determine Role object (using Role-name we identified)
    role_record = system_org.get_role_record(role_name)
    role_record_read_only = utils.str_to_bool(role_record.get("isReadOnly"))
    if role_record_read_only:
        msg = "User has predefined non editable role. Not adding native entitlement rights."  # noqa: E501
        msg_update_callback.general(msg)
        return

    # Determine the rights necessary from rights bundle
    # It is assumed that user already has "View Rights Bundle" Right
    rbm = RightBundleManager(client, log_wire, msg_update_callback)
    native_def_rights = \
        rbm.get_rights_for_right_bundle(right_bundle_name)

    # Get rights as a list of right-name strings
    rights = []
    for right_record in native_def_rights.get("values"):
        rights.append(right_record["name"])

    try:
        # Add rights to the Role
        role_obj = Role(client, resource=system_org.get_role_resource(role_name))  # noqa: E501
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


def _register_def_schema(client: Client,
                         config=None,
                         msg_update_callback=utils.NullPrinter(),
                         log_wire=False):
    """Register RDE constructs.

    This is supported only for VCD API version >=35.
    Based on the RDE version in use, it will register the required RDE
    constructs to VCD.

    :param pyvcloud.vcd.client.Client client:
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501
    :param bool log_wire: wire logging enabled
    """
    if config is None:
        config = {}
    msg = "Registering Runtime defined entity schema"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)
    logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER if log_wire else NULL_LOGGER
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client, logger_debug=INSTALL_LOGGER, logger_wire=logger_wire)
    # TODO update CSE install to create client from max_vcd_api_version
    try:
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        rde_version: str = str(config['service']['rde_version_in_use'])
        msg_update_callback.general(f"Using RDE version: {str(rde_version)}")
        # Obtain RDE metadata needed to initialize CSE
        rde_metadata: dict = def_utils.get_rde_metadata(rde_version)

        # Register Interface(s)
        interfaces: List[common_models.DefInterface] = \
            rde_metadata[def_constants.RDEMetadataKey.INTERFACES]
        _register_interfaces(cloudapi_client, interfaces, msg_update_callback)

        # Register Behavior(s)
        behavior_metadata: Dict[str, List[Behavior]] = rde_metadata.get(
            def_constants.RDEMetadataKey.INTERFACE_TO_BEHAVIORS_MAP, {})
        _register_behaviors(cloudapi_client, behavior_metadata, msg_update_callback)  # noqa: E501

        # Register Native EntityType
        entity_type: common_models.DefEntityType = \
            rde_metadata[def_constants.RDEMetadataKey.ENTITY_TYPE]
        _register_native_entity_type(cloudapi_client, entity_type,
                                     msg_update_callback)  # noqa: E501

        # Override Behavior(s)
        override_behavior_metadata: Dict[str, List[Behavior]] = \
            rde_metadata.get(def_constants.RDEMetadataKey.ENTITY_TYPE_TO_OVERRIDABLE_BEHAVIORS_MAP, {})  # noqa: E501
        _override_behaviors(cloudapi_client, override_behavior_metadata, msg_update_callback)  # noqa: E501

        # Set ACL(s) for all the behavior(s)
        behavior_acl_metadata: Dict[str, List[BehaviorAclEntry]] = \
            rde_metadata.get(def_constants.RDEMetadataKey.BEHAVIOR_TO_ACL_MAP, {})  # noqa: E501
        _set_acls_on_behaviors(cloudapi_client, behavior_acl_metadata, msg_update_callback)  # noqa: E501

        # Update user's role with right bundle associated with native defined
        # entity
        _update_user_role_with_right_bundle(
            def_constants.DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE,
            client=client,
            msg_update_callback=msg_update_callback,
            logger_debug=INSTALL_LOGGER,
            log_wire=log_wire
        )
        # Given that Rights for the current user have been updated, CSE
        # should logout the user and login again.
        # This will make sure that SecurityContext object in VCD is
        # recreated and newly added rights are effective for the user.
        client.logout()
        credentials = BasicLoginCredentials(
            config['vcd']['username'],
            shared_constants.SYSTEM_ORG_NAME,
            config['vcd']['password']
        )
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
        msg = f"Error occurred while registering defined entity schema: {str(e)}"  # noqa: E501
        msg_update_callback.error(msg)
        INSTALL_LOGGER.error(msg)
        raise e


def _set_acls_on_behaviors(cloudapi_client,
                           map_entitytypeid_to_behavior_acls: Dict[str, List[BehaviorAclEntry]],  # noqa: E501
                           msg_update_callback=utils.NullPrinter()):
    behavior_svc = BehaviorService(cloudapi_client=cloudapi_client)
    for entity_type_id, behavior_acls in map_entitytypeid_to_behavior_acls.items():  # noqa: E501
        msg = f"Setting ACLs on behaviors of the entity type '{entity_type_id}'"  # noqa: E501
        try:
            behavior_svc.update_behavior_acls_on_entity_type(entity_type_id, behavior_acls)  # noqa: E501
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
        except cse_exception.BehaviorServiceError as e:
            msg = f"Failed to set ACLs on behaviors of the entity type '{entity_type_id}'"  # noqa: E501
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)
            raise e


def _override_behaviors(cloudapi_client,
                        map_entitytypeid_to_behaviors: Dict[str, List[Behavior]],  # noqa: E501
                        msg_update_callback=utils.NullPrinter()):
    behavior_svc = BehaviorService(cloudapi_client=cloudapi_client)
    for entity_type_id, behaviors in map_entitytypeid_to_behaviors.items():
        for behavior in behaviors:
            try:
                current_behavior: Behavior = behavior_svc.get_behavior_on_entity_type_by_id(behavior.ref, entity_type_id)  # noqa: E501
                if current_behavior.execution.type == behavior.execution.type:
                    msg = f"Skipping behavior overriding for '{behavior.id}' on entity type '{entity_type_id}'"  # noqa: E501
                    msg_update_callback.general(msg)
                    INSTALL_LOGGER.info(msg)
                else:
                    behavior_svc.override_behavior_on_entity_type(behavior, entity_type_id)  # noqa: E501
                    msg = f"Overriding behavior '{behavior.id}' on entity type '{entity_type_id}'"  # noqa: E501
                    msg_update_callback.general(msg)
                    INSTALL_LOGGER.info(msg)
            except cse_exception.BehaviorServiceError as e:
                msg = f"Overriding behavior '{behavior.id}' on entity type '{entity_type_id}' failed with error {str(e)}"  # noqa: E501
                msg_update_callback.error(msg)
                INSTALL_LOGGER.error(msg)
                raise e


def _register_behaviors(cloudapi_client,
                        map_interfaceid_to_behaviors: Dict[str, List[Behavior]],  # noqa: E501
                        msg_update_callback=utils.NullPrinter()):
    behavior_svc = BehaviorService(cloudapi_client=cloudapi_client)
    for interface_id, behaviors in map_interfaceid_to_behaviors.items():
        for behavior in behaviors:
            try:
                behavior_svc.get_behavior_on_interface_by_id(behavior.id, interface_id)  # noqa: E501
                msg = f"Skipping creation of behavior '{behavior.id}' on " \
                      f"interface '{interface_id}'.Behavior already found."
                msg_update_callback.general(msg.rstrip())
                INSTALL_LOGGER.info(msg)
            except cse_exception.BehaviorServiceError:
                behavior_svc.create_behavior_on_interface(behavior, interface_id)  # noqa: E501
                msg = f"Successfully registered the behavior " \
                      f"'{behavior.id}' on interface '{interface_id}'."
                msg_update_callback.general(msg)
                INSTALL_LOGGER.info(msg)


def _register_native_entity_type(cloudapi_client,
                                 entity_type: common_models.DefEntityType,
                                 msg_update_callback=utils.NullPrinter()):
    schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
    try:
        schema_svc.get_entity_type(entity_type.id)
        msg = f"Skipping creation of Native Entity Type '{entity_type.id}'. Native Entity Type already exists."  # noqa: E501
    except cse_exception.DefSchemaServiceError:
        # TODO handle this part only if the entity type was not found
        native_entity_type = schema_svc.create_entity_type(entity_type)
        msg = f"Successfully registered Native entity type '{native_entity_type.id}'\n"  # noqa: E501
        entity_svc = def_entity_svc.DefEntityService(cloudapi_client)
        entity_svc.create_acl_for_entity(
            native_entity_type.get_id(),
            grant_type=server_constants.AclGrantType.MembershipACLGrant,
            access_level_id=server_constants.AclAccessLevelId.AccessLevelReadWrite,  # noqa: E501
            member_id=server_constants.AclMemberId.SystemOrgId)
        msg += "Successfully " \
               "added ReadWrite ACL for native defined entity to System Org"  # noqa: E501
    msg_update_callback.general(msg)
    INSTALL_LOGGER.info(msg)


def _register_interfaces(cloudapi_client,
                         interfaces: List[common_models.DefInterface],
                         msg_update_callback):
    schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
    for interface in interfaces:
        try:
            schema_svc.get_interface(interface.id)
            if interface.id == common_models.K8Interface.VCD_INTERFACE.value.id:  # noqa: E501
                msg = f"Built in kubernetes interface '{interface.id}' found."  # noqa: E501
            else:
                msg = f"Skipping creation of interface '{interface.id}'." \
                      " Interface already exists."  # noqa: E501
            msg_update_callback.general(msg)
            INSTALL_LOGGER.info(msg)
        except cse_exception.DefSchemaServiceError:
            # If built-in interface is missing, raise an Exception.
            if interface.id == common_models.K8Interface.VCD_INTERFACE.value.id:  # noqa: E501
                msg = f"Built in interface '{interface.name}' not present."  # noqa: E501
                msg_update_callback.error(msg)
                INSTALL_LOGGER.error(msg)
                raise
            # Create other interfaces if not present
            schema_svc.create_interface(interface)
            msg = f"Successfully registered interface '{interface.name}'."
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
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object.  # noqa: E501

    :raises BadRequestException: if a right with given name already
        exists in vCD.
    """
    ext = api_extension.APIExtension(client)
    # Since the client is a sys admin, org will hold a reference to System org
    system_org = Org(client, resource=client.get_org())
    try:
        right_name_in_vcd = f"{{{ server_constants.CSE_SERVICE_NAME}}}:{right_name}"  # noqa: E501
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
        system_org.add_rights(tuple(right_name_in_vcd))
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
            msg = "Skipping creation of global PVDC compute policy. Policy already exists"  # noqa: E501
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
            try:
                compute_policy_manager.get_cse_vdc_compute_policy(
                    cpm,
                    policy_name,
                    is_placement_policy=True)
                msg = f"Skipping creation of VDC placement policy '{policy_name}'. Policy already exists"  # noqa: E501
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


def _construct_catalog_item_name_to_template_definition_map(cookbook: dict) -> dict:  # noqa: E501
    """Get a dictionary which maps catalog item name to template description.

    :param dict cookbook: template cookbook
    :return: dictionary with catalog item name as key and template description
        as value
    :rtype: dict
    """
    remote_template_keys = \
        server_utils.get_template_descriptor_keys(semantic_version.Version(cookbook['version']))  # noqa: E501
    catalog_item_name_to_template_description = {}
    for template in cookbook['templates']:
        # For CSE 3.1, we can safely assume that all the catalog item names are
        # present in template metadata as CSE 3.1 can only be upgraded from
        # CSE 3.0
        catalog_item_name = ltm.get_revisioned_template_name(
            template[remote_template_keys.NAME],
            template[remote_template_keys.REVISION])
        catalog_item_name_to_template_description[catalog_item_name] = template
    return catalog_item_name_to_template_description


def _update_metadata_of_templates(
        client: Client,
        templates_to_process: list,
        catalog_org_name: str,
        catalog_name: str,
        msg_update_callback=utils.NullPrinter()):
    """Update template metadata to include new metadata keys.

    Metadata update will happen when CSE is configured in non-legacy mode only
    for supported templates.

    :param vcdClient.Client client:
    :param list templates_to_process: list of dict, each dict represents the
        template definition as per the remote template repo.
    :param str catalog_org_name:
    :param str catalog_name:
    :param core_utils.ConsoleMessagePrinter msg_update_callback:
    """
    # load global LEGACY_MODE value
    global LEGACY_MODE

    # Skip updating metadata if CSE is configured in legacy mode.
    if LEGACY_MODE:
        msg = "Skipping template metadata update as " \
              "CSE is configured in legacy mode."
        INSTALL_LOGGER.debug(msg)
        msg_update_callback.general(msg)
        return

    # List of keys for the new template metadata. This includes
    # min_cse_version and max_cse_version
    new_metadata_key_list = [k for k in server_constants.LocalTemplateKey]
    for template in templates_to_process:
        catalog_item_name = \
            template[server_constants.LocalTemplateKey.CATALOG_ITEM_NAME]
        template_name = \
            template[server_constants.RemoteTemplateKeyV2.NAME]
        template_revision = \
            template[server_constants.RemoteTemplateKeyV2.REVISION]

        # New keys to be added (min_cse_version and max_cse_version)
        # will already be in template representation.
        # Update template metadata.
        ltm.save_metadata(
            client,
            catalog_org_name,
            catalog_name,
            catalog_item_name,
            template,
            metadata_key_list=new_metadata_key_list
        )
        msg = f"Successfully updated metadata " \
              f"of local template : {template_name} revision " \
              f"{template_revision}."
        INSTALL_LOGGER.debug(msg)
        msg_update_callback.general(msg)


def _assign_placement_policies_to_existing_templates(client: Client,
                                                     config: dict,
                                                     all_templates: list,
                                                     is_tkg_plus_enabled: bool,
                                                     log_wire: bool = False,
                                                     msg_update_callback=utils.NullPrinter()):  # noqa: E501
    # NOTE: In CSE 3.0 if `enable_tkg_plus` flag in the config is set to false,
    # And there is an existing TKG+ template, throw an exception on the console
    # and fail the upgrade.
    msg = "Assigning placement policies to existing templates."
    INSTALL_LOGGER.debug(msg)
    msg_update_callback.info(msg)

    catalog_name = config['broker']['catalog']
    org_name = config['broker']['org']

    for template in all_templates:
        kind = template.get(server_constants.LocalTemplateKey.KIND)
        template_name = template[server_constants.LocalTemplateKey.NAME]
        template_revision = template[server_constants.LocalTemplateKey.REVISION]  # noqa: E501
        catalog_item_name = ltm.get_revisioned_template_name(
            template_name,
            template_revision
        )
        msg = f"Processing template {template_name} revision {template_revision}"  # noqa: E501
        INSTALL_LOGGER.debug(msg)
        msg_update_callback.info(msg)
        if not kind:
            # skip processing the template if kind value is not present
            msg = f"Skipping processing of template {template_name} revision {template_revision}. Template kind not found"  # noqa: E501
            INSTALL_LOGGER.debug(msg)
            msg_update_callback.info(msg)
            continue
        if kind == shared_constants.ClusterEntityKind.TKG_PLUS.value and \
                not is_tkg_plus_enabled:
            msg = "Found a TKG+ template." \
                  " However TKG+ is not enabled on CSE. " \
                  "Please enable TKG+ for CSE via config file and re-run " \
                  "`cse upgrade` to process these vDC(s)."
            INSTALL_LOGGER.error(msg)
            raise cse_exception.CseUpgradeError(msg)
        placement_policy_name = \
            shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP[kind]
        template_builder.assign_placement_policy_to_template(
            client,
            placement_policy_name,
            catalog_name,
            catalog_item_name,
            org_name,
            logger=INSTALL_LOGGER,
            log_wire=log_wire,
            msg_update_callback=msg_update_callback)


def _process_existing_templates(
        client: Client, config: dict,
        is_tkg_plus_enabled: bool,
        log_wire: bool = False,
        msg_update_callback=utils.NullPrinter()):
    """Process existing templates and make them compatible with CSE 3.1.0.

    Read existing templates in catalog, compare them with what is available
    in remote template repo, if a match is found update the metadata on
    the template and re-download the script files.

    Read metadata of existing templates, get the value for the 'kind' metadata,
    assign the respective placement policy to the template.

    :param vcdClient.Client client:
    :param dict config: content of the CSE config file.
    :param bool is_tkg_plus_enabled:
    :param bool log_wire:
    :param core_utils.ConsoleMessagePrinter msg_update_callback:
    """
    # Load global LEGACY_MODE variable
    global LEGACY_MODE

    if LEGACY_MODE:
        msg = "Template won't be processed as " \
              "CSE is configured in legacy mode."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)
        return
    else:
        msg = "Processing existing templates."
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

    catalog_org_name = config['broker']['org']
    catalog_name = config['broker']['catalog']
    # Here we are trying to load all existing templates
    # The templates might be created by CSE 3.0 or CSE 3.1
    # To be on safe side, we are reading them as v1.0.0 template
    # hence legacy_mode is set to True, this will ignore the keys
    # max_cse_version and min_cse_version
    # Also we are ignoring the "compute_policy" key since the key
    # won't be present on templates created by CSE 3.1
    all_local_templates = \
        ltm.get_all_k8s_local_template_definition(
            client,
            catalog_name=catalog_name,
            org_name=catalog_org_name,
            ignore_metadata_keys=[server_constants.LegacyLocalTemplateKey.COMPUTE_POLICY],  # noqa: E501
            legacy_mode=True,
            logger_debug=INSTALL_LOGGER
        )

    cookbook_url = config['broker']['remote_template_cookbook_url']
    rtm = RemoteTemplateManager(
        remote_template_cookbook_url=cookbook_url,
        legacy_mode=False,
        logger=INSTALL_LOGGER,
        msg_update_callback=msg_update_callback
    )
    # NOTE: get_remote_template_cookbook() will load only
    # the template descriptors supported by the target CSE version.
    rtm.get_filtered_remote_template_cookbook()

    catalog_item_to_template_definition_map = \
        _construct_catalog_item_name_to_template_definition_map(
            rtm.filtered_cookbook)

    templates_to_process = []
    for template in all_local_templates:
        # Since CSE 3.1 can only be upgraded from CSE 3.0, we can safely assume
        # that all the templates have catalog_item_name in their metadata
        catalog_item_name = \
            template[server_constants.LegacyLocalTemplateKey.CATALOG_ITEM_NAME]
        template_name = \
            template[server_constants.LegacyLocalTemplateKey.NAME]
        template_revision = \
            template[server_constants.LegacyLocalTemplateKey.REVISION]

        if catalog_item_name in catalog_item_to_template_definition_map:
            template_definition = catalog_item_to_template_definition_map[catalog_item_name].copy()  # noqa: E501
            # Add extra info that should be stamped on template
            template_definition[server_constants.LocalTemplateKey.CATALOG_ITEM_NAME] = catalog_item_name  # noqa: E501
            template_definition[server_constants.LocalTemplateKey.COOKBOOK_VERSION] = str(rtm.cookbook_version)  # noqa: E501
            templates_to_process.append(template_definition)
            msg = f"Template {template_name} revision {template_revision} " \
                  "will be processed."
        else:
            # Template not supported in the target CSE version.
            # Do not update template metadata
            msg = f"Template {template_name} revision {template_revision} " \
                  "will not be processed."
        INSTALL_LOGGER.debug(msg)
        msg_update_callback.general(msg)

    # Update metadata with min_cse_version and max_cse_version for all
    # templates supported in the target CSE version
    _update_metadata_of_templates(
        client=client,
        templates_to_process=templates_to_process,
        catalog_org_name=catalog_org_name,
        catalog_name=catalog_name,
        msg_update_callback=msg_update_callback
    )

    # Download scripts of processed templates
    for template in templates_to_process:
        rtm.download_template_scripts(
            template_name=template[server_constants.RemoteTemplateKeyV2.NAME],
            revision=template[server_constants.RemoteTemplateKeyV2.REVISION],
            force_overwrite=True
        )

    # Once the templates are fixed, load them normally.
    all_templates = \
        ltm.get_all_k8s_local_template_definition(
            client,
            catalog_name=catalog_name,
            org_name=catalog_org_name,
            legacy_mode=False,
            logger_debug=INSTALL_LOGGER
        )

    _assign_placement_policies_to_existing_templates(
        client,
        config,
        all_templates,
        is_tkg_plus_enabled,
        log_wire=log_wire,
        msg_update_callback=msg_update_callback)


def _install_all_templates(
        client, config, force_create, retain_temp_vapp,
        ssh_key, msg_update_callback=utils.NullPrinter()):
    global LEGACY_MODE
    # read remote template cookbook, download all scripts
    rtm = RemoteTemplateManager(
        remote_template_cookbook_url=config['broker']['remote_template_cookbook_url'],  # noqa: E501
        legacy_mode=LEGACY_MODE,
        logger=INSTALL_LOGGER,
        msg_update_callback=msg_update_callback)
    remote_template_cookbook = rtm.get_filtered_remote_template_cookbook()

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
            is_tkg_plus_enabled=server_utils.is_tkg_plus_enabled(config),
            msg_update_callback=msg_update_callback)


def _install_single_template(
        client, remote_template_manager, template, org_name,
        vdc_name, catalog_name, network_name, ip_allocation_mode,
        storage_profile, force_update, retain_temp_vapp,
        ssh_key, is_tkg_plus_enabled=False,
        msg_update_callback=utils.NullPrinter()):
    global LEGACY_MODE
    # NOTE: For CSE 3.0+, if the template is a TKG+ template
    # and `enable_tkg_plus` is set to false,
    # An error should be thrown and template installation should be skipped.
    if not LEGACY_MODE and not is_tkg_plus_enabled and \
            template[server_constants.LocalTemplateKey.KIND] == \
            shared_constants.ClusterEntityKind.TKG_PLUS.value:
        msg = "Found a TKG+ template." \
              " However TKG+ is not enabled on CSE. " \
              "Please enable TKG+ for CSE via config file and re-run " \
              "`cse upgrade` to process these vDC(s)."
        INSTALL_LOGGER.error(msg)
        msg_update_callback.error(msg)
        raise Exception(msg)
    localTemplateKey = server_constants.LocalTemplateKey
    remote_template_keys = server_utils.get_template_descriptor_keys(
        remote_template_manager.cookbook_version)
    if LEGACY_MODE:
        # if legacy_mode, make use of LegacyLocalTemplateKey which
        # doesn't contain min_cse_version and max_cse_version.
        localTemplateKey = server_constants.LegacyLocalTemplateKey
    templateBuildKey = server_constants.TemplateBuildKey
    remote_template_manager.download_template_scripts(
        template_name=template[remote_template_keys.NAME],
        revision=template[remote_template_keys.REVISION],
        force_overwrite=force_update)
    catalog_item_name = ltm.get_revisioned_template_name(
        template[remote_template_keys.NAME],
        template[remote_template_keys.REVISION])

    # remote template data is a super set of local template data, barring
    # the key 'catalog_item_name' and 'cookbook_version' (if CSE is running in
    #  non-legacy mode)
    template_data = dict(template)
    template_data[localTemplateKey.CATALOG_ITEM_NAME] = catalog_item_name
    if not LEGACY_MODE:
        template_data[localTemplateKey.COOKBOOK_VERSION] = \
            remote_template_manager.cookbook_version
    template_metadata_keys = [k for k in localTemplateKey]

    missing_keys = [k for k in template_metadata_keys
                    if k not in template_data]
    if len(missing_keys) > 0:
        raise ValueError(f"Invalid template data. Missing keys: {missing_keys}")  # noqa: E501

    temp_vm_name = (
        f"{template[remote_template_keys.OS].replace('.', '')}-"
        f"k8s{template[remote_template_keys.KUBERNETES_VERSION].replace('.', '')}-"  # noqa: E501
        f"{template[remote_template_keys.CNI]}"
        f"{template[remote_template_keys.CNI_VERSION].replace('.', '')}-vm"
    )
    build_params = {
        templateBuildKey.TEMPLATE_NAME: template[remote_template_keys.NAME],
        templateBuildKey.TEMPLATE_REVISION: template[remote_template_keys.REVISION],  # noqa: E501
        templateBuildKey.SOURCE_OVA_NAME: template[remote_template_keys.SOURCE_OVA_NAME],  # noqa: E501
        templateBuildKey.SOURCE_OVA_HREF: template[remote_template_keys.SOURCE_OVA_HREF],  # noqa: E501
        templateBuildKey.SOURCE_OVA_SHA256: template[remote_template_keys.SOURCE_OVA_SHA256],  # noqa: E501
        templateBuildKey.ORG_NAME: org_name,
        templateBuildKey.VDC_NAME: vdc_name,
        templateBuildKey.CATALOG_NAME: catalog_name,
        templateBuildKey.CATALOG_ITEM_NAME: catalog_item_name,
        templateBuildKey.CATALOG_ITEM_DESCRIPTION: template[remote_template_keys.DESCRIPTION],  # noqa: E501
        templateBuildKey.TEMP_VAPP_NAME: template[remote_template_keys.NAME] + '_temp',  # noqa: E501
        templateBuildKey.TEMP_VM_NAME: temp_vm_name,
        templateBuildKey.CPU: template[remote_template_keys.CPU],
        templateBuildKey.MEMORY: template[remote_template_keys.MEMORY],
        templateBuildKey.NETWORK_NAME: network_name,
        templateBuildKey.IP_ALLOCATION_MODE: ip_allocation_mode,
        templateBuildKey.STORAGE_PROFILE: storage_profile,
        templateBuildKey.REMOTE_COOKBOOK_VERSION: remote_template_manager.cookbook_version  # noqa: E501
    }
    if not LEGACY_MODE:  # noqa: E501
        if template.get(
                remote_template_keys.KIND) not in shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP:  # noqa: E501
            raise ValueError(f"Cluster kind is {template.get(remote_template_keys.KIND)}"  # noqa: E501
                             f" Expected { shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP.keys()}")  # noqa: E501
        build_params[templateBuildKey.CSE_PLACEMENT_POLICY] = \
            shared_constants.RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP[template.get(remote_template_keys.KIND)]  # noqa: E501
    builder = template_builder.TemplateBuilder(client, client, build_params,
                                               ssh_key=ssh_key,
                                               logger=INSTALL_LOGGER,
                                               msg_update_callback=msg_update_callback)  # noqa: E501
    builder.build(force_recreate=force_update,
                  retain_temp_vapp=retain_temp_vapp)

    ltm.save_metadata(client, org_name, catalog_name, catalog_item_name,
                      template_data, metadata_key_list=template_metadata_keys)


def _upgrade_to_cse_3_1_non_legacy(client, config,
                                   skip_template_creation, retain_temp_vapp,
                                   ssh_key,
                                   msg_update_callback=utils.NullPrinter(),
                                   log_wire=False):
    """Handle upgrade when VCD supports RDE.

    :raises: MultipleRecordsException: (when using mqtt) if more than one
        service with the given name and namespace are found when trying to
        delete the amqp-based extension.
    :raises requests.exceptions.HTTPError: (when using MQTT) if the MQTT
        components were not installed correctly
    """
    is_tkg_plus_enabled = server_utils.is_tkg_plus_enabled(config=config)

    # Add global placement policies
    _setup_placement_policies(
        client=client,
        policy_list=shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES,
        is_tkg_plus_enabled=is_tkg_plus_enabled,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    # IMPORTANT: This statement decides if the upgrade is for legacy or non
    # legacy cluster. This check should be done always before registering def
    # schema. This statement should not be moved around otherwise.
    def_entity_type_registered = _is_def_entity_type_registered(client=client)

    # Register def schema
    _register_def_schema(
        client=client,
        config=config,
        msg_update_callback=msg_update_callback,
        log_wire=log_wire)

    if skip_template_creation:
        msg = """Skipping creation of templates.
Please note, CSE server startup needs at least one valid template.
Please create CSE K8s template(s) using the command `cse template install`."""
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)
        _process_existing_templates(
            client=client,
            config=config,
            is_tkg_plus_enabled=is_tkg_plus_enabled,
            log_wire=utils.str_to_bool(config['service'].get('log_wire')),
            msg_update_callback=msg_update_callback)
    else:
        # Recreate all supported templates
        _install_all_templates(
            client=client,
            config=config,
            force_create=True,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=ssh_key,
            msg_update_callback=msg_update_callback)

    msg = "Loading all CSE clusters for processing..."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.info(msg)
    clusters = get_all_cse_clusters(client=client, fetch_details=True)

    # Add new vdc (placement) compute policy to ovdc with existing CSE clusters
    _assign_placement_policy_to_vdc_and_right_bundle_to_org(
        client=client,
        cse_clusters=clusters,
        is_tkg_plus_enabled=is_tkg_plus_enabled,
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

    # TODO: Restore the old idempotent way of processing clusters
    # Look at each cluster, try to get the corresponding RDE using
    # cluster id, if RDE retrieval fails, process the cluster as legacy
    # else process it as RDE 1.0.0/2.0.0 cluster accordingly
    if def_entity_type_registered:
        _process_non_legacy_clusters(
            client=client,
            config=config,
            cse_clusters=clusters,
            msg_update_callback=msg_update_callback,
            log_wire=log_wire)
    else:
        _process_legacy_clusters(
            client=client,
            config=config,
            cse_clusters=clusters,
            is_tkg_plus_enabled=is_tkg_plus_enabled,
            msg_update_callback=msg_update_callback,
            log_wire=log_wire)

    # Print list of users categorized by org, who currently owns CSE clusters
    # and will need DEF entity rights.
    _print_users_in_need_of_def_rights(
        cse_clusters=clusters, msg_update_callback=msg_update_callback)

    # Stamp the updated description on the CSE MQTT extension object
    # to declare that the current CSE has been upgraded to latest
    # CSE version, and all clusters/templates/compute policies have
    # been processed.
    _update_cse_mqtt_extension(
        client,
        rde_version_in_use=config['service']['rde_version_in_use'],
        msg_update_callback=msg_update_callback)


def _upgrade_to_cse_3_1_legacy(
        client, config, skip_template_creation, retain_temp_vapp, ssh_key,
        msg_update_callback=utils.NullPrinter()):
    """Handle upgrade when no support from VCD for RDE.

    :raises cse_exception.AmqpError: (when using AMQP) if AMQP exchange
        could not be created.
    """
    if skip_template_creation:
        # TODO : Template scripts file might be directly under ~/.cse-scripts
        # they need to be moved under ~/.cse-scripts/1.0.0
        msg = """Skipping creation of new templates and special processing of existing templates.
Please note, CSE server startup needs at least one valid template.
Please create CSE K8s template(s) using the command `cse template install`."""  # noqa: E501
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)
    else:
        # Recreate all supported templates
        _install_all_templates(
            client=client,
            config=config,
            force_create=True,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=ssh_key,
            msg_update_callback=msg_update_callback)

    # Update amqp exchange (idempotent)
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
        rde_version_in_use=semantic_version.Version("0.0.0"),
        msg_update_callback=msg_update_callback)


def _get_placement_policy_name_from_template_name(template_name):
    if 'k8' in template_name:
        policy_name = \
            shared_constants.NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME
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
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):
    """Assign placement policies to VDCs and right bundles to Orgs with existing clusters."""  # noqa: E501
    # NOTE: For CSE 3.0, if `enable_tkg_plus` flag in the config is set to
    # false,
    # Throw an error on the console and do not publish TKG+ placement policy to
    # the VDC
    msg = "Assigning placement compute policy(s) to vDC(s) hosting existing CSE clusters."  # noqa: E501
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    msg = "Identifying vDC(s) that are currently hosting CSE clusters."
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    tkg_plus_ovdcs = []
    native_ovdcs = []
    vdc_names = {}
    org_ids = set()
    for cluster in cse_clusters:
        try:
            policy_name = _get_placement_policy_name_from_template_name(
                cluster['template_name'])
        except Exception:
            msg = f"Invalid template '{cluster['template_name']}' for cluster '{cluster['name']}'."  # noqa: E501
            msg_update_callback.error(msg)
            INSTALL_LOGGER.error(msg)
            continue

        if policy_name == shared_constants.NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            vdc_id = cluster['vdc_id']
            native_ovdcs.append(vdc_id)
            vdc_names[vdc_id] = cluster['vdc_name']
        elif policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            vdc_id = cluster['vdc_id']
            tkg_plus_ovdcs.append(vdc_id)
            vdc_names[vdc_id] = cluster['vdc_name']
        org_id = cluster['org_href'].split('/')[-1]
        org_ids.add(org_id)

    native_ovdcs = set(native_ovdcs)
    tkg_plus_ovdcs = set(tkg_plus_ovdcs)

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

        if is_tkg_plus_enabled:
            tkg_plus_policy = \
                compute_policy_manager.get_cse_vdc_compute_policy(
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

    if len(org_ids) > 0:
        msg = "Publishing CSE native cluster right bundles to orgs where " \
              "clusters are deployed"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)
        try:
            rbm = RightBundleManager(client, log_wire=log_wire, logger_debug=INSTALL_LOGGER)  # noqa: E501
            cse_right_bundle = rbm.get_right_bundle_by_name(
                def_constants.DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE)
            rbm.publish_cse_right_bundle_to_tenants(
                right_bundle_id=cse_right_bundle['id'],
                org_ids=list(org_ids))
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

            vdc = vcd_utils.get_vdc(client, vdc_name=vdc_name, org_name=org_name)  # noqa: E501
            vdc_id = pyvcloud_vcd_utils.extract_id(vdc.get_resource().get('id'))  # noqa: E501
            vdc_sizing_policies = compute_policy_manager.list_cse_sizing_policies_on_vdc(cpm, vdc_id)  # noqa: E501
            if vdc_sizing_policies:
                for policy in vdc_sizing_policies:
                    msg = f"Processing Policy : '{policy['display_name']}' on Org VDC : '{vdc_name}'"  # noqa: E501
                    msg_update_callback.info(msg)
                    INSTALL_LOGGER.info(msg)

                    all_cse_policy_names.append(policy['display_name'])
                    task_data = cpm.remove_vdc_compute_policy_from_vdc(
                        ovdc_id=vdc_id,
                        compute_policy_href=policy['href'],
                        force=True)
                    fake_task_object = {'href': task_data['task_href']}
                    client.get_task_monitor().wait_for_status(fake_task_object)  # noqa: E501

                    msg = f"Removed Policy : '{policy['display_name']}' from Org VDC : '{vdc_name}'"  # noqa: E501
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


def _process_non_legacy_clusters(
        client,
        config,
        cse_clusters,
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):

    msg = "Processing existing CSE k8s clusters"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER if log_wire else NULL_LOGGER
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client,
        logger_debug=INSTALL_LOGGER,
        logger_wire=logger_wire)

    entity_svc = def_entity_svc.DefEntityService(cloudapi_client)
    schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)

    # TODO: get proper site information
    site = config['vcd']['host']
    runtime_rde_version: str = str(config['service']['rde_version_in_use'])
    rde_metadata: dict = def_utils.get_rde_metadata(runtime_rde_version)
    entity_type_metadata = rde_metadata[def_constants.RDEMetadataKey.ENTITY_TYPE]  # noqa: E501
    target_entity_type = schema_svc.get_entity_type(entity_type_metadata.get_id())  # noqa: E501

    for cluster in cse_clusters:
        msg = f"Processing cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

        cluster_id = cluster['cluster_id']
        try:
            def_entity = entity_svc.get_entity(cluster_id)
            source_rde_version = def_entity.entityType.split(":")[-1]
            if semantic_version.Version(source_rde_version) < semantic_version.Version(runtime_rde_version):  # noqa: E501
                msg = f"Updating {def_entity.name} RDE from {source_rde_version} to {runtime_rde_version}"  # noqa: E501
                INSTALL_LOGGER.info(msg)
                msg_update_callback.info(msg)
                _upgrade_cluster_rde(
                    client=client,
                    cluster=cluster,
                    rde_to_upgrade=def_entity,
                    runtime_rde_version=runtime_rde_version,
                    target_entity_type=target_entity_type,
                    entity_svc=entity_svc,
                    site=site,
                    msg_update_callback=msg_update_callback
                )
            else:
                msg = f"Skipping cluster '{cluster['name']}' " \
                      f"since it has already been processed."
                INSTALL_LOGGER.info(msg)
                msg_update_callback.info(msg)
                continue
        except Exception as err:
            INSTALL_LOGGER.error(str(err), exc_info=True)
            msg_update_callback.error(f"Failed to upgrade cluster '{cluster['name']}'")  # noqa: E501

    msg = "Finished processing all clusters."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.general(msg)

    # Remove old entity types
    msg = "Removing old native entity types"
    INSTALL_LOGGER.info(msg)
    msg_update_callback.general(msg)
    try:
        native_entity_types = _get_native_def_entity_types(client)
        for entity_type in native_entity_types:
            if entity_type.id != target_entity_type.id:
                msg = f"Deleting entity type: {entity_type.id}"
                INSTALL_LOGGER.info(msg)
                msg_update_callback.general(msg)
                schema_svc.delete_entity_type(entity_type.id)
    except Exception as err:
        INSTALL_LOGGER.debug(str(err))
        msg_update_callback.error("Failed to delete old entity types")


def _process_legacy_clusters(
        client,
        config,
        cse_clusters,
        is_tkg_plus_enabled,
        msg_update_callback=utils.NullPrinter(),
        log_wire=False):
    msg = "Processing CSE k8s clusters"
    msg_update_callback.info(msg)
    INSTALL_LOGGER.info(msg)

    logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER if log_wire else NULL_LOGGER
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client,
        logger_debug=INSTALL_LOGGER,
        logger_wire=logger_wire)

    entity_svc = def_entity_svc.DefEntityService(cloudapi_client)
    schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)

    # TODO: get proper site information
    site = config['vcd']['host']
    runtime_rde_version: str = str(config['service']['rde_version_in_use'])
    rde_metadata: dict = def_utils.get_rde_metadata(runtime_rde_version)
    entity_type_metadata = rde_metadata[def_constants.RDEMetadataKey.ENTITY_TYPE]  # noqa: E501
    target_entity_type = schema_svc.get_entity_type(entity_type_metadata.get_id())  # noqa: E501

    for cluster in cse_clusters:
        msg = f"Processing cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.info(msg)

        try:
            policy_name = _get_placement_policy_name_from_template_name(
                cluster['template_name'])
        except Exception:
            msg = f"Invalid template '{cluster['template_name']}' for cluster '{cluster['name']}'."  # noqa: E501
            msg_update_callback.info(msg)
            INSTALL_LOGGER.info(msg)
            continue

        if policy_name == \
                shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME and \
                not is_tkg_plus_enabled:
            msg = "Found a TKG+ cluster." \
                  " However TKG+ is not enabled on CSE. " \
                  "Please enable TKG+ for CSE via config file and re-run" \
                  "`cse upgrade` to process these clusters"
            INSTALL_LOGGER.error(msg)
            raise cse_exception.CseUpgradeError(msg)

        kind = shared_constants.ClusterEntityKind.NATIVE.value
        if policy_name == shared_constants.TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME:  # noqa: E501
            kind = shared_constants.ClusterEntityKind.TKG_PLUS.value

        _create_cluster_rde(
            client, cluster,
            kind, runtime_rde_version,
            target_entity_type, entity_svc,
            site, msg_update_callback=msg_update_callback
        )

        msg = f"Finished processing cluster '{cluster['name']}'"
        INSTALL_LOGGER.info(msg)
        msg_update_callback.general(msg)

    msg = "Finished processing all clusters."
    INSTALL_LOGGER.info(msg)
    msg_update_callback.general(msg)


def _create_cluster_rde(client, cluster, kind, runtime_rde_version,
                        target_entity_type, entity_svc,
                        site, msg_update_callback=utils.NullPrinter()):
    TargetNativeEntity = get_rde_model(runtime_rde_version)
    cluster_entity = TargetNativeEntity.from_cluster_data(cluster=cluster, kind=kind)  # noqa: E501
    org_resource = vcd_utils.get_org(client, org_name=cluster['org_name'])
    org_id = org_resource.href.split('/')[-1]
    def_entity = common_models.DefEntity(entity=cluster_entity, entityType=target_entity_type.id)  # noqa: E501
    entity_svc.create_entity(
        target_entity_type.id,
        entity=def_entity,
        tenant_org_context=org_id,
        delete_status_from_payload=False
    )

    def_entity = entity_svc.get_native_rde_by_name_and_rde_version(cluster['name'], runtime_rde_version)  # noqa: E501
    def_entity_id = def_entity.id

    # TODO: Need to find a better approach to avoid conditional logic for
    #   filling missing properties.
    if semantic_version.Version(runtime_rde_version).major == \
            semantic_version.Version(def_constants.RDEVersion.RDE_2_0_0).major:
        # Update with the correct cluster id
        native_entity_2_x: rde_2_x.NativeEntity = def_entity.entity
        native_entity_2_x.status.uid = def_entity_id
        native_entity_2_x.status.cloud_properties.site = site
        native_entity_2_x.metadata.site = site

    def_entity.externalId = cluster['vapp_href']

    # update ownership of the entity
    try:
        user = client.get_user_in_org(user_name=cluster['owner_name'], org_href=cluster['org_href'])  # noqa: E501
        user_urn = user.get('id')
        org_member_urn = user_urn.replace(":user:", ":orgMember:")

        org_href = cluster['org_href']
        org_id = org_href.split("/")[-1]
        org_urn = f"urn:vcloud:org:{org_id}"

        def_entity.owner = common_models.Owner(
            name=cluster['owner_name'],
            id=org_member_urn)
        def_entity.org = common_models.Org(
            name=cluster['org_name'],
            id=org_urn)
    except Exception as err:
        INSTALL_LOGGER.debug(str(err))
        msg = f"Unable to determine current owner of cluster '{cluster['name']}'. Unable to process ownership."  # noqa: E501
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


def _upgrade_cluster_rde(client, cluster, rde_to_upgrade,
                         runtime_rde_version, target_entity_type,
                         entity_svc, site=None, msg_update_callback=utils.NullPrinter()):  # noqa: E501
    TargetNativeEntity = get_rde_model(runtime_rde_version)
    new_native_entity = TargetNativeEntity.from_native_entity(rde_to_upgrade.entity)  # noqa: E501

    # Adding missing fields in RDE 2.0
    # TODO: Need to find a better approach to avoid conditional logic for
    # filling missing properties.
    if semantic_version.Version(runtime_rde_version).major == \
            semantic_version.Version(def_constants.RDEVersion.RDE_2_0_0).major:
        # RDE upgrade possible only from RDE 1.0 or RDE 2.x
        native_entity_2_x: rde_2_x.NativeEntity = new_native_entity
        native_entity_2_x.status.uid = rde_to_upgrade.id
        native_entity_2_x.status.cloud_properties.site = site
        native_entity_2_x.metadata.site = site

        # This heavily relies on the fact that the source RDE is v1.0.0
        try:
            vapp_href = rde_to_upgrade.externalId
            vapp = VApp(client, href=vapp_href)
            control_plane_ip = vapp.get_primary_ip(
                vm_name=rde_to_upgrade.entity.status.nodes.control_plane.name)
            if rde_to_upgrade.entity.status.exposed:
                native_entity_2_x.status.nodes.control_plane.ip = \
                    control_plane_ip
        except Exception as err:
            INSTALL_LOGGER.error(str(err), exc_info=True)

    upgraded_rde: common_models.DefEntity = \
        entity_svc.upgrade_entity(
            rde_to_upgrade.id,
            new_native_entity,
            target_entity_type.id
        )

    # Update cluster metadata with new cluster id. This step is still needed
    # because the format of the entity ID has changed to omit version string.
    tags = {
        server_constants.ClusterMetadataKey.CLUSTER_ID: upgraded_rde.id,
        server_constants.ClusterMetadataKey.CSE_VERSION: server_utils.get_installed_cse_version()  # noqa: E501
    }
    vapp = VApp(client, href=cluster['vapp_href'])
    task = vapp.set_multiple_metadata(tags)
    client.get_task_monitor().wait_for_status(task)
    msg = f"Updated vApp metadata with cluster id of cluster '{cluster['name']}'."  # noqa : E501
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
          "to access them in CSE 3.1"
    org_users_msg = ""
    for org_name, user_list in org_user_dict.items():
        org_users_msg += f"\nOrg : {org_name} -> Users : {', '.join(set(user_list))}"  # noqa: E501

    if org_users_msg:
        msg = msg + org_users_msg
        msg_update_callback.info(msg)
        INSTALL_LOGGER.info(msg)


def _is_def_entity_type_registered(client):
    """Check the presence of native entity type of any version.

    :param client:
    :return: True if present else False
    :rtype: bool
    """
    try:
        return True if len(_get_native_def_entity_types(client)) > 0 else False  # noqa: E501
    except cse_exception.DefNotSupportedException:
        return False


def _get_native_def_entity_types(client):
    """Get list of native entity types.

    :param client:
    :return: list of native entity types
    :rtype: list
    """
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client,
        logger_debug=INSTALL_LOGGER
    )
    schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
    return [entity_type for entity_type in schema_svc.list_entity_types()
            if entity_type.nss == def_constants.Nss.NATIVE_CLUSTER.value]
