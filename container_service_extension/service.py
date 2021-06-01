# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique
import signal
import sys
import threading
from threading import Thread
import time
import traceback
from typing import Optional

import click
from pyvcloud.vcd.client import ApiVersion as vCDApiVersion
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import OperationNotSupportedException

import container_service_extension.compute_policy_manager \
    as compute_policy_manager
import container_service_extension.configure_cse as configure_cse
from container_service_extension.consumer.consumer import MessageConsumer
import container_service_extension.def_.models as def_models
import container_service_extension.def_.schema_service as def_schema_svc
import container_service_extension.def_.utils as def_utils
from container_service_extension.def_.utils import raise_error_if_def_not_supported  # noqa: E501
import container_service_extension.exceptions as cse_exception
import container_service_extension.local_template_manager as ltm
import container_service_extension.logger as logger
from container_service_extension.mqtt_extension_manager import \
    MQTTExtensionManager
from container_service_extension.pks_cache import PksCache
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.server_constants as server_constants
from container_service_extension.server_constants import MQTTExtKey
import container_service_extension.shared_constants as shared_constants
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.template_rule import TemplateRule
import container_service_extension.utils as utils
from container_service_extension.vsphere_utils import populate_vsphere_list


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs)
        return cls._instances[cls]


def signal_handler(signal, frame):
    print('\nCtrl+C detected, exiting')
    raise KeyboardInterrupt()


def consumer_thread_run(c):
    try:
        logger.SERVER_LOGGER.info(f"About to start consumer_thread {c}.")
        c.run()
    except Exception as e:
        click.echo(f"Exception in MessageConsumer thread. "
                   f"About to stop thread due to: {e}")
        logger.SERVER_LOGGER.error(traceback.format_exc())
        c.stop()


def watchdog_thread_run(service_obj, num_processors):
    logger.SERVER_LOGGER.info("Starting watchdog thread")
    while True:
        service_state = service_obj.get_status()
        if service_state == ServerState.STOPPED.value:
            break

        if service_state == ServerState.RUNNING.value and \
                service_obj.consumer_thread is not None and \
                not service_obj.consumer_thread.is_alive():
            service_obj.consumer = MessageConsumer(service_obj.config,
                                                   num_processors)
            consumer_thread = Thread(name=server_constants.MESSAGE_CONSUMER_THREAD,  # noqa: E501
                                     target=consumer_thread_run,
                                     args=(service_obj.consumer, ))
            consumer_thread.daemon = True
            consumer_thread.start()
            service_obj.consumer_thread = consumer_thread

            msg = 'Watchdog has restarted consumer thread'
            click.echo(msg)
            logger.SERVER_LOGGER.info(msg)
        time.sleep(60)


def verify_version_compatibility(sysadmin_client: Client,
                                 target_vcd_api_version, is_mqtt_extension):
    cse_version = utils.get_installed_cse_version()
    ext_cse_version, ext_vcd_api_version = \
        configure_cse.parse_cse_extension_description(
            sysadmin_client, is_mqtt_extension)
    if cse_version == server_constants.UNKNOWN_CSE_VERSION or \
            ext_vcd_api_version == server_constants.UNKNOWN_VCD_API_VERSION:
        # version data doesn't exist, so CSE <= 2.6.1 was installed
        raise cse_exception.VersionCompatibilityError(
            "CSE and VCD API version data not found on VCD. "
            "Upgrade CSE to update version data.")

    version_error_msg = ''
    if cse_version > ext_cse_version:
        version_error_msg += \
            f"CSE Server version ({cse_version}) is higher than what was " \
            f"previously registered with VCD ({ext_cse_version}). " \
            f"Upgrade CSE to update CSE version on VCD."
    if cse_version < ext_cse_version:
        version_error_msg += \
            f"CSE Server version ({cse_version}) cannot be lower than what " \
            f"was previously registered with VCD ({ext_cse_version})."

    if target_vcd_api_version > ext_vcd_api_version:
        version_error_msg += \
            f"Target VCD API version ({target_vcd_api_version}) is higher " \
            f"than what was previously registered by CSE " \
            f"({ext_vcd_api_version}). Upgrade CSE to update " \
            f"registered VCD API version."
    if target_vcd_api_version < ext_vcd_api_version:
        version_error_msg += \
            f"Target VCD API version ({target_vcd_api_version}) cannot be " \
            f"lower than what was previously registered by " \
            f"CSE ({ext_vcd_api_version})."

    if version_error_msg:
        raise cse_exception.VersionCompatibilityError(version_error_msg)


@unique
class ServerState(Enum):
    RUNNING = 'Running'
    DISABLED = 'Disabled'
    STOPPING = 'Shutting down'
    STOPPED = 'Stopped'


# NOTE: CSE 3.0 behavior when `enable_tkg_plus` is set to true in the config:
# cse install/upgrade will:
# 1. create appropriate TKG+ policy
# 2. Tag new/old templates with the corresponding policy
# 3. publish TKG+ policy to OVDC
# cse template install will:
# 1. tag the newly created template with TKG+ policy
# 2. If the policy is not found error will be raised
# cse run will
# 1. read all templates from catalog including the ones that have 'kind' set
#   to TKG+
# ovdc handler will:
# 1. allow enabling/disabling ovdcs for TKG+
#
# If `enable_tkg_plus` flag is set to false in the config:
# cse install/upgrade will:
# 1. not create TKG+ policy
# 2. raise error if a TKG+ template is specified in the templates.yaml
# 3. raise error if a TKG+ cluster is encountered
# cse template install will
# 1. raise error if TKG+ template is given as an input
# cse run will
# 1. Skip reading all TKG+ templates
# OVDC handler will
# 1. reject all TKG+ related OVDC updates
# 2. Skip showing TKG+ in the output for list and get
class Service(object, metaclass=Singleton):
    def __init__(self, config_file=None, config=None, pks_config_file=None,
                 should_check_config=True,
                 skip_config_decryption=False):
        self.config_file = config_file
        self.config = config
        self.pks_config_file = pks_config_file
        self.should_check_config = should_check_config
        self.skip_config_decryption = skip_config_decryption
        self.pks_cache = None
        self._state = ServerState.STOPPED
        self._kubernetesInterface: Optional[def_models.DefInterface] = None
        self._nativeEntityType: Optional[def_models.DefEntityType] = None
        self.consumer = None
        self.consumer_thread = None
        self._consumer_watchdog = None

    def get_service_config(self):
        return self.config

    def get_pks_cache(self):
        return self.pks_cache

    def is_pks_enabled(self):
        return bool(self.pks_cache)

    def active_requests_count(self):
        # TODO(request_count) Add support for PksBroker - VCDA-938
        if self.consumer is None:
            return 0
        else:
            return self.consumer.get_num_active_threads()

    def get_status(self):
        return self._state.value

    def is_running(self):
        return self._state == ServerState.RUNNING

    def info(self, get_sysadmin_info=False):
        result = utils.get_cse_info()
        result[shared_constants.CSE_SERVER_API_VERSION] = utils.get_server_api_version()  # noqa: E501
        if get_sysadmin_info:
            result['all_consumer_threads'] = 0 if self.consumer is None else \
                self.consumer.get_num_total_threads()
            result['all_threads'] = threading.activeCount()
            result['requests_in_progress'] = self.active_requests_count()
            result['config_file'] = self.config_file
            result['status'] = self.get_status()
        else:
            del result['python']
        return result

    def get_kubernetes_interface(self) -> def_models.DefInterface:
        """Get the built-in kubernetes interface from vCD."""
        return self._kubernetesInterface

    def get_native_cluster_entity_type(self) -> def_models.DefEntityType:
        return self._nativeEntityType

    def update_status(self, server_action: shared_constants.ServerAction):
        def graceful_shutdown():
            message = 'Shutting down CSE'
            n = self.active_requests_count()
            if n > 0:
                message += f" CSE will finish processing {n} requests."
            self._state = ServerState.STOPPING
            return message

        if self._state == ServerState.RUNNING:
            if server_action == shared_constants.ServerAction.ENABLE:
                return 'CSE is already enabled and running.'
            if server_action == shared_constants.ServerAction.DISABLE:
                self._state = ServerState.DISABLED
                return 'CSE has been disabled.'
            if server_action == shared_constants.ServerAction.STOP:
                raise cse_exception.BadRequestError(
                    error_message='CSE must be disabled before '
                                  'it can be stopped.')
            raise cse_exception.BadRequestError(
                error_message=f"Invalid server action: '{server_action}'")
        if self._state == ServerState.DISABLED:
            if server_action == shared_constants.ServerAction.ENABLE:
                self._state = ServerState.RUNNING
                return 'CSE has been enabled and is running.'
            if server_action == shared_constants.ServerAction.DISABLE:
                return 'CSE is already disabled.'
            if server_action == shared_constants.ServerAction.STOP:
                return graceful_shutdown()
        if self._state == ServerState.STOPPING:
            if server_action == shared_constants.ServerAction.ENABLE:
                raise cse_exception.BadRequestError(
                    error_message='Cannot enable CSE while it is being'
                                  'stopped.')
            if server_action == shared_constants.ServerAction.DISABLE:
                raise cse_exception.BadRequestError(
                    error_message='Cannot disable CSE while it is being'
                                  ' stopped.')
            if server_action == shared_constants.ServerAction.STOP:
                return graceful_shutdown()

        raise cse_exception.CseServerError(f"Invalid server state: '{self._state}'")  # noqa: E501

    def run(self, msg_update_callback=utils.NullPrinter()):

        sysadmin_client = None
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client()
            verify_version_compatibility(sysadmin_client,
                                         self.config['vcd']['api_version'],
                                         utils.should_use_mqtt_protocol(self.config))  # noqa: E501
        except Exception as err:
            logger.SERVER_LOGGER.info(err)
            raise
        finally:
            if sysadmin_client:
                sysadmin_client.logout()

        if utils.should_use_mqtt_protocol(self.config):
            # Store/setup MQTT extension, api filter, and token info
            try:
                sysadmin_client = vcd_utils.get_sys_admin_client()
                mqtt_ext_manager = MQTTExtensionManager(sysadmin_client)
                ext_info = mqtt_ext_manager.get_extension_info(
                    ext_name=server_constants.CSE_SERVICE_NAME,
                    ext_version=server_constants.MQTT_EXTENSION_VERSION,
                    ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
                ext_urn_id = ext_info[MQTTExtKey.EXT_URN_ID]
                ext_uuid = mqtt_ext_manager.get_extension_uuid(ext_urn_id)
                api_filters_status = mqtt_ext_manager.check_api_filters_setup(
                    ext_uuid, configure_cse.API_FILTER_PATTERNS)
                if not api_filters_status:
                    msg = 'MQTT Api filter is not set up'
                    logger.SERVER_LOGGER.error(msg)
                    raise cse_exception.MQTTExtensionError(msg)

                token_info = mqtt_ext_manager.setup_extension_token(
                    token_name=server_constants.MQTT_TOKEN_NAME,
                    ext_name=server_constants.CSE_SERVICE_NAME,
                    ext_version=server_constants.MQTT_EXTENSION_VERSION,
                    ext_vendor=server_constants.MQTT_EXTENSION_VENDOR,
                    ext_urn_id=ext_urn_id)

                self.config['mqtt'].update(ext_info)
                self.config['mqtt'].update(token_info)
                self.config['mqtt'][MQTTExtKey.EXT_UUID] = ext_uuid
            except Exception as err:
                msg = f'MQTT extension setup error: {err}'
                logger.SERVER_LOGGER.error(msg)
                raise err
            finally:
                if sysadmin_client:
                    sysadmin_client.logout()

        populate_vsphere_list(self.config['vcs'])

        # Load def entity-type and interface
        self._load_def_schema(msg_update_callback=msg_update_callback)

        # Read k8s catalog definition from catalog item metadata and append
        # the same to to server run-time config
        self._load_template_definition_from_catalog(
            msg_update_callback=msg_update_callback)

        self._load_placement_policy_details(
            msg_update_callback=msg_update_callback)

        if float(self.config['vcd']['api_version']) < float(vCDApiVersion.VERSION_35.value): # noqa: E501
            # Read templates rules from config and update template definition
            # in server run-time config
            self._process_template_rules(
                msg_update_callback=msg_update_callback)

            # Make sure that all vms in templates are compliant with the
            # compute policy specified in template definition (can be affected
            # by rules).
            self._process_template_compute_policy_compliance(
                msg_update_callback=msg_update_callback)
        else:
            msg = "Template rules are not supported by CSE for vCD api " \
                  "version 35.0 or above. Skipping template rule processing."
            msg_update_callback.info(msg)
            logger.SERVER_LOGGER.debug(msg)

        if self.should_check_config:
            configure_cse.check_cse_installation(
                self.config,
                msg_update_callback=msg_update_callback)

        if self.config.get('pks_config'):
            pks_config = self.config.get('pks_config')
            self.pks_cache = PksCache(
                pks_servers=pks_config.get('pks_api_servers', []),
                pks_accounts=pks_config.get('pks_accounts', []),
                pvdcs=pks_config.get('pvdcs', []),
                orgs=pks_config.get('orgs', []),
                nsxt_servers=pks_config.get('nsxt_servers', []))

        num_processors = self.config['service']['processors']
        name = server_constants.MESSAGE_CONSUMER_THREAD
        try:
            self.consumer = MessageConsumer(self.config, num_processors)
            consumer_thread = Thread(name=name, target=consumer_thread_run,
                                     args=(self.consumer, ))
            consumer_thread.daemon = True
            consumer_thread.start()
            self.consumer_thread = consumer_thread
            msg = f"Started thread '{name}' ({consumer_thread.ident})"
            msg_update_callback.general(msg)
            logger.SERVER_LOGGER.info(msg)
        except KeyboardInterrupt:
            if self.consumer:
                self.consumer.stop()
            interrupt_msg = f"\nKeyboard interrupt when starting thread " \
                            f"'{name}'"
            logger.SERVER_LOGGER.debug(interrupt_msg)
            raise Exception(interrupt_msg)
        except Exception:
            if self.consumer:
                self.consumer.stop()
            logger.SERVER_LOGGER.error(traceback.format_exc())

        # Updating state to Running before starting watchdog because watchdog
        # exits when server is not Running
        self._state = ServerState.RUNNING

        # Start consumer watchdog
        name = server_constants.WATCHDOG_THREAD
        consumer_watchdog = Thread(name=name,
                                   target=watchdog_thread_run,
                                   args=(self, num_processors))
        consumer_watchdog.daemon = True
        consumer_watchdog.start()
        self._consumer_watchdog = consumer_watchdog
        msg = f"Started thread '{name}' ({consumer_watchdog.ident})"
        msg_update_callback.general(msg)
        logger.SERVER_LOGGER.info(msg)

        message = f"Container Service Extension for vCloud Director" \
                  f"\nServer running using config file: {self.config_file}" \
                  f"\nLog files: {logger.SERVER_INFO_LOG_FILEPATH}, " \
                  f"{logger.SERVER_DEBUG_LOG_FILEPATH}" \
                  f"\nwaiting for requests (ctrl+c to close)"

        signal.signal(signal.SIGINT, signal_handler)
        msg_update_callback.general_no_color(message)
        logger.SERVER_LOGGER.info(message)

        # Record telemetry on user action and details of operation.
        cse_params = {
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(self.skip_config_decryption), # noqa: E501
            PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(self.pks_config_file),  # noqa: E501
            PayloadKey.WAS_INSTALLATION_CHECK_SKIPPED: bool(self.should_check_config)  # noqa: E501
        }
        record_user_action_details(cse_operation=CseOperation.SERVICE_RUN,
                                   cse_params=cse_params)
        record_user_action(cse_operation=CseOperation.SERVICE_RUN)

        while True:
            try:
                time.sleep(1)
                if self._state == ServerState.STOPPING and \
                        self.active_requests_count() == 0:
                    break
            except KeyboardInterrupt:
                break
            except Exception:
                msg_update_callback.general_no_color(
                    traceback.format_exc())
                logger.SERVER_LOGGER.error(traceback.format_exc())
                sys.exit(1)

        logger.SERVER_LOGGER.info("Stop detected")
        logger.SERVER_LOGGER.info("Closing connections...")
        self._state = ServerState.STOPPING
        try:
            self.consumer.stop()
        except Exception:
            logger.SERVER_LOGGER.error(traceback.format_exc())

        self._state = ServerState.STOPPED
        logger.SERVER_LOGGER.info("Done")

    def _load_def_schema(self, msg_update_callback=utils.NullPrinter()):
        """Load cluster interface and cluster entity type to global context.

        If defined entity framework is supported by vCD api version, load
        defined entity interface and defined entity type registered during
        server install

        :param utils.ConsoleMessagePrinter msg_update_callback:
        """
        sysadmin_client = None
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client()
            logger_wire = logger.NULL_LOGGER
            if utils.str_to_bool(utils.str_to_bool(self.config['service'].get('log_wire', False))): # noqa: E501
                logger_wire = logger.SERVER_CLOUDAPI_WIRE_LOGGER

            cloudapi_client = \
                vcd_utils.get_cloudapi_client_from_vcd_client(sysadmin_client,
                                                              logger.SERVER_LOGGER, # noqa: E501
                                                              logger_wire)
            raise_error_if_def_not_supported(cloudapi_client)
            schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
            defKey = def_utils.DefKey
            keys_map = def_utils.MAP_API_VERSION_TO_KEYS[float(sysadmin_client.get_api_version())] # noqa: E501
            interface_id = def_utils.generate_interface_id(vendor=keys_map[defKey.INTERFACE_VENDOR], # noqa: E501
                                                           nss=keys_map[defKey.INTERFACE_NSS], # noqa: E501
                                                           version=keys_map[defKey.INTERFACE_VERSION]) # noqa: E501
            entity_type_id = def_utils.generate_entity_type_id(vendor=keys_map[defKey.ENTITY_TYPE_VENDOR], # noqa: E501
                                                               nss=keys_map[defKey.ENTITY_TYPE_NSS], # noqa: E501
                                                               version=keys_map[defKey.ENTITY_TYPE_VERSION]) # noqa: E501
            self._kubernetesInterface = schema_svc.get_interface(interface_id)
            self._nativeEntityType = schema_svc.get_entity_type(entity_type_id)
            msg = "Successfully loaded defined entity schema to global context"
            msg_update_callback.general(msg)
            logger.SERVER_LOGGER.debug(msg)
        except cse_exception.DefNotSupportedException:
            msg = "Skipping initialization of defined entity type" \
                  " and defined entity interface"
            msg_update_callback.info(msg)
            logger.SERVER_LOGGER.debug(msg)
        except cse_exception.DefSchemaServiceError as e:
            msg = f"Error while loading defined entity schema: {e.minor_error_code}"  # noqa: E501
            msg_update_callback.error(msg)
            logger.SERVER_LOGGER.debug(msg)
            raise
        except Exception as e:
            msg = f"Failed to load defined entity schema to global context: {str(e)}" # noqa: E501
            msg_update_callback.error(msg)
            logger.SERVER_LOGGER.error(msg)
            raise
        finally:
            if sysadmin_client:
                sysadmin_client.logout()

    def _load_placement_policy_details(self,
                                       msg_update_callback=utils.NullPrinter()):  # noqa: E501
        msg = "Loading kubernetes runtime placement policies."
        logger.SERVER_LOGGER.info(msg)
        msg_update_callback.general(msg)
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client()
            if float(sysadmin_client.get_api_version()) < compute_policy_manager.GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION:  # noqa: E501
                msg = "Placement policies for kubernetes runtimes not " \
                      " supported in api version " \
                      f"{sysadmin_client.get_api_version()}"  # noqa: E501
                logger.SERVER_LOGGER.debug(msg)
                msg_update_callback.info(msg)
                return
            placement_policy_name_to_href = {}
            cpm = compute_policy_manager.ComputePolicyManager(sysadmin_client,
                                                              log_wire=self.config['service'].get('log_wire')) # noqa: E501
            for runtime_policy in shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES:  # noqa: E501
                k8_runtime = shared_constants.RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP[runtime_policy]  # noqa: E501
                try:
                    placement_policy_name_to_href[k8_runtime] = \
                        compute_policy_manager.get_cse_vdc_compute_policy(
                            cpm,
                            runtime_policy,
                            is_placement_policy=True)['href']
                except EntityNotFoundException:
                    pass
            self.config['placement_policy_hrefs'] = placement_policy_name_to_href  # noqa: E501
        except Exception as e:
            msg = f"Failed to load placement policies to server runtime configuration: {str(e)}" # noqa: E501
            msg_update_callback.error(msg)
            logger.SERVER_LOGGER.error(msg)
            raise

    def _load_template_definition_from_catalog(
            self, msg_update_callback=utils.NullPrinter()):
        # NOTE: If `enable_tkg_plus` in the config file is set to false,
        # CSE server will skip loading the TKG+ template this will prevent
        # users from performing TKG+ related operations.
        msg = "Loading k8s template definition from catalog"
        logger.SERVER_LOGGER.info(msg)
        msg_update_callback.general_no_color(msg)

        client = None
        try:
            log_filename = None
            log_wire = \
                utils.str_to_bool(self.config['service'].get('log_wire'))
            if log_wire:
                log_filename = logger.SERVER_DEBUG_WIRELOG_FILEPATH

            client = Client(self.config['vcd']['host'],
                            api_version=self.config['vcd']['api_version'],
                            verify_ssl_certs=self.config['vcd']['verify'],
                            log_file=log_filename,
                            log_requests=log_wire,
                            log_headers=log_wire,
                            log_bodies=log_wire)
            credentials = BasicLoginCredentials(self.config['vcd']['username'],
                                                server_constants.SYSTEM_ORG_NAME,  # noqa: E501
                                                self.config['vcd']['password'])
            client.set_credentials(credentials)

            is_tkg_plus_enabled = utils.is_tkg_plus_enabled(self.config)
            is_tkgm_enabled = utils.is_tkgm_enabled(self.config)
            org_name = self.config['broker']['org']
            catalog_name = self.config['broker']['catalog']
            k8_templates = ltm.get_all_k8s_local_template_definition(
                client=client, catalog_name=catalog_name, org_name=org_name,
                logger_debug=logger.SERVER_LOGGER)

            if not k8_templates:
                msg = "No valid K8 templates were found in catalog " \
                      f"'{catalog_name}'. Unable to start CSE server."
                msg_update_callback.error(msg)
                logger.SERVER_LOGGER.error(msg)
                sys.exit(1)

            # Check that default k8s template exists in vCD at the correct
            # revision
            default_template_name = \
                self.config['broker']['default_template_name']
            default_template_revision = \
                str(self.config['broker']['default_template_revision'])
            found_default_template = False
            for template in k8_templates:
                api_version = float(client.get_api_version())
                if api_version >= float(vCDApiVersion.VERSION_35.value):
                    if template[server_constants.LocalTemplateKey.KIND] == \
                            shared_constants.ClusterEntityKind.TKG_PLUS.value and \
                            not is_tkg_plus_enabled:
                        # TKG+ is not enabled on CSE config. Skip the template and
                        # log the relevant information.
                        msg = "Skipping loading template data for " \
                              f"'{template[server_constants.LocalTemplateKey.NAME]}' as " \
                              "TKG+ is not enabled"  # noqa: E501
                        logger.SERVER_LOGGER.debug(msg)
                        k8_templates.remove(template)
                        continue
                    if template[server_constants.LocalTemplateKey.KIND] == \
                            shared_constants.ClusterEntityKind.TKG_M.value and \
                            not is_tkgm_enabled:
                        # TKGm is not enabled on CSE config. Skip the template and
                        # log the relevant information.
                        msg = "Skipping loading template data for " \
                              f"'{template[server_constants.LocalTemplateKey.NAME]}' as " \
                              "TKGm is not enabled"  # noqa: E501
                        logger.SERVER_LOGGER.debug(msg)
                        k8_templates.remove(template)
                        continue
                if str(template[server_constants.LocalTemplateKey.REVISION]) == default_template_revision and \
                        template[server_constants.LocalTemplateKey.NAME] == default_template_name: # noqa: E501
                    found_default_template = True

                msg = f"Found K8 template '{template['name']}' at revision " \
                      f"{template['revision']} in catalog '{catalog_name}'"
                msg_update_callback.general(msg)
                logger.SERVER_LOGGER.info(msg)

            if not found_default_template:
                msg = f"Default template {default_template_name} with " \
                      f"revision {default_template_revision} not found." \
                      " Unable to start CSE server."
                msg_update_callback.error(msg)
                logger.SERVER_LOGGER.error(msg)
                sys.exit(1)

            self.config['broker']['templates'] = k8_templates
        finally:
            if client:
                client.logout()

    def _process_template_rules(self, msg_update_callback=utils.NullPrinter()):
        if 'template_rules' not in self.config:
            return
        rules = self.config['template_rules']
        if not rules:
            return

        templates = self.config['broker']['templates']

        # process rules
        msg = "Processing template rules."
        logger.SERVER_LOGGER.debug(msg)
        msg_update_callback.general_no_color(msg)

        for rule_def in rules:
            rule = TemplateRule(
                name=rule_def.get('name'), target=rule_def.get('target'),
                action=rule_def.get('action'), logger=logger.SERVER_LOGGER,
                msg_update_callback=msg_update_callback)

            msg = f"Processing rule : {rule}."
            logger.SERVER_LOGGER.debug(msg)
            msg_update_callback.general_no_color(msg)

            # Since the patching is in-place, the changes will reflect back on
            # the dictionary holding the server runtime configuration.
            rule.apply(templates)

            msg = f"Finished processing rule : '{rule.name}'"
            logger.SERVER_LOGGER.debug(msg)
            msg_update_callback.general(msg)

    def _process_template_compute_policy_compliance(self,
                                                    msg_update_callback=utils.NullPrinter()): # noqa: E501
        msg = "Processing compute policy for k8s templates."
        logger.SERVER_LOGGER.info(msg)
        msg_update_callback.general_no_color(msg)

        org_name = self.config['broker']['org']
        catalog_name = self.config['broker']['catalog']
        sysadmin_client = None
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client()
            cpm = compute_policy_manager.ComputePolicyManager(sysadmin_client,
                                                              log_wire=self.config['service'].get('log_wire')) # noqa: E501

            for template in self.config['broker']['templates']:
                policy_name = template[server_constants.LocalTemplateKey.COMPUTE_POLICY]  # noqa: E501
                catalog_item_name = template[server_constants.LocalTemplateKey.CATALOG_ITEM_NAME] # noqa: E501
                # if policy name is not empty, stamp it on the template
                if policy_name:
                    try:
                        policy = \
                            compute_policy_manager.get_cse_vdc_compute_policy(
                                cpm, policy_name) # noqa: E501
                    except EntityNotFoundException:
                        # create the policy if it does not exist
                        msg = f"Creating missing compute policy " \
                              f"'{policy_name}'."
                        msg_update_callback.info(msg)
                        logger.SERVER_LOGGER.debug(msg)
                        policy = \
                            compute_policy_manager.add_cse_vdc_compute_policy(
                                cpm,
                                policy_name)

                    msg = f"Assigning compute policy '{policy_name}' to " \
                          f"template '{catalog_item_name}'."
                    msg_update_callback.general(msg)
                    logger.SERVER_LOGGER.debug(msg)
                    cpm.assign_vdc_sizing_policy_to_vapp_template_vms(
                        compute_policy_href=policy['href'],
                        org_name=org_name,
                        catalog_name=catalog_name,
                        catalog_item_name=catalog_item_name)
                else:
                    # empty policy name means we should remove policy from
                    # template
                    msg = f"Removing compute policy from template " \
                          f"'{catalog_item_name}'."
                    msg_update_callback.general(msg)
                    logger.SERVER_LOGGER.debug(msg)

                    cpm.remove_all_vdc_compute_policies_from_vapp_template_vms(
                        org_name=org_name,
                        catalog_name=catalog_name,
                        catalog_item_name=catalog_item_name)
        except OperationNotSupportedException:
            msg = "Compute policy not supported by vCD. Skipping " \
                  "assigning/removing it to/from templates."
            msg_update_callback.info(msg)
            logger.SERVER_LOGGER.debug(msg)
        finally:
            if sysadmin_client is not None:
                sysadmin_client.logout()
