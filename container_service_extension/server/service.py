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
from typing import Dict, List, Optional

import click
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
import semantic_version

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.common.utils.vsphere_utils import populate_vsphere_list  # noqa: E501
from container_service_extension.config.server_config import ServerConfig
import container_service_extension.exception.exceptions as cse_exception
import container_service_extension.installer.configure_cse as configure_cse
from container_service_extension.installer.templates.template_rule import TemplateRule  # noqa: E501
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import PayloadKey
from container_service_extension.lib.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.lib.telemetry.telemetry_handler import \
    record_user_action_details
import container_service_extension.logging.logger as logger
from container_service_extension.mqi.consumer.consumer import MessageConsumer
from container_service_extension.mqi.mqtt_extension_manager import \
    MQTTExtensionManager
import container_service_extension.rde.constants as def_constants
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.schema_service as def_schema_svc
import container_service_extension.rde.utils as def_utils
from container_service_extension.rde.utils import raise_error_if_def_not_supported  # noqa: E501
import container_service_extension.server.compute_policy_manager \
    as compute_policy_manager
from container_service_extension.server.pks.pks_cache import PksCache
import container_service_extension.server.template_reader as template_reader


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs)
        return cls._instances[cls]


def signal_handler(signal_in, frame):
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


def verify_version_compatibility(
        sysadmin_client: Client,
        should_cse_run_in_legacy_mode: bool,
        is_mqtt_extension: bool):
    ext_description = configure_cse.get_extension_description(
        sysadmin_client,
        is_mqtt_extension
    )
    dikt = configure_cse.parse_cse_extension_description(ext_description)
    ext_cse_version = dikt[server_constants.CSE_VERSION_KEY]
    ext_in_legacy_mode = dikt[server_constants.LEGACY_MODE_KEY]
    ext_rde_in_use = dikt[server_constants.RDE_VERSION_IN_USE_KEY]

    # version data doesn't exist, so installed CSE is <= 2.6.1
    if ext_cse_version == server_constants.UNKNOWN_CSE_VERSION:
        raise cse_exception.VersionCompatibilityError(
            "CSE and VCD API version data not found on VCD. "
            "Please upgrade CSE and retry.")

    error_msg = ''
    cse_version = utils.get_installed_cse_version()
    # Trying to use newer version of CSE without running `cse upgrade`
    if cse_version > ext_cse_version:
        error_msg += \
            f"CSE Server version ({cse_version}) is higher than what was " \
            f"previously registered with VCD ({ext_cse_version}). " \
            "Please upgrade CSE and retry."
    # Trying to use an older version of CSE
    if cse_version < ext_cse_version:
        error_msg += \
            f"CSE Server version ({cse_version}) cannot be lower than what " \
            f"was previously registered with VCD ({ext_cse_version}). " \
            "Please use a newer version of CSE."

    # Trying to run a legacy CSE in non-legacy mode
    if not should_cse_run_in_legacy_mode and ext_in_legacy_mode:
        error_msg += \
            "Installed CSE is configured in legacy mode. Unable to run it " \
            "in non-legacy mode. Please use `cse upgrade` to configure " \
            "CSE to operate in non-legacy mode."

    # Trying to run a non legacy CSE in legacy mode
    if should_cse_run_in_legacy_mode and not ext_in_legacy_mode:
        error_msg += \
            "Installed CSE is configured in non-legacy mode. Unable to run " \
            "it in legacy mode."

    expected_runtime_rde_version = semantic_version.Version(server_utils.get_rde_version_in_use())  # noqa: E501
    if not ext_in_legacy_mode:
        # VCD downgrade?
        if ext_rde_in_use > expected_runtime_rde_version:
            error_msg += \
                "Installed CSE Runtime Defined Entity (RDE) version " \
                f"({ext_rde_in_use}) is higher than the expected RDE " \
                f"version ({expected_runtime_rde_version}). Please " \
                "upgrade VCD to proceed."

        # VCD got upgraded without `cse upgrade` being run.
        if ext_rde_in_use < expected_runtime_rde_version:
            error_msg += \
                "Installed CSE Runtime Defined Entity (RDE) version " \
                f"({ext_rde_in_use}) is lower than the expected RDE " \
                f"version ({expected_runtime_rde_version}). Please " \
                "use `cse upgrade` to upgrade CSE RDE version and " \
                "retry."

    if error_msg:
        raise cse_exception.VersionCompatibilityError(error_msg)


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
        self.config = ServerConfig(config)
        self.pks_config_file = pks_config_file
        self.should_check_config = should_check_config
        self.skip_config_decryption = skip_config_decryption
        self.pks_cache = None
        self._state = ServerState.STOPPED
        self._kubernetesInterface: Optional[common_models.DefInterface] = None
        self._nativeEntityType: Optional[common_models.DefEntityType] = None
        self.consumer = None
        self.consumer_thread = None
        self._consumer_watchdog = None

    def get_service_config(self) -> ServerConfig:
        return self.config

    def get_pks_cache(self) -> PksCache:
        return self.pks_cache

    def is_pks_enabled(self) -> bool:
        return bool(self.pks_cache)

    def active_requests_count(self) -> int:
        # ToDo: (request_count) Add support for PksBroker - VCDA-938
        if self.consumer is None:
            return 0
        else:
            return self.consumer.get_num_active_threads()

    def get_status(self):
        return self._state.value

    def is_running(self) -> bool:
        return self._state == ServerState.RUNNING

    def info(self, get_sysadmin_info=False) -> Dict:
        result = utils.get_cse_info()
        result[shared_constants.CSE_SERVER_API_VERSION] = self.config.get_value_at('service.default_api_version')  # noqa: E501
        result[shared_constants.CSE_SERVER_SUPPORTED_API_VERSIONS] = self.config.get_value_at('service.supported_api_versions')  # noqa: E501
        result[shared_constants.CSE_SERVER_LEGACY_MODE] = self.config.get_value_at('service.legacy_mode')  # noqa: E501
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

    def get_native_cluster_entity_type(self) -> common_models.DefEntityType:
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
            syslog_host = None
            syslog_port = None
            try:
                syslog_host = self.config.get_value_at('service.syslog_host')
                syslog_port = self.config.get_value_at('service.syslog_port')
            except KeyError:
                pass
            if syslog_host:
                logger.configure_loggers_for_syslog(
                    syslog_host=syslog_host,
                    syslog_port=syslog_port
                )
        except Exception as err:
            logger.SERVER_LOGGER.error(f"Syslog server error:{err}")
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client(api_version=None)
            verify_version_compatibility(
                sysadmin_client,
                should_cse_run_in_legacy_mode=self.config.get_value_at('service.legacy_mode'),  # noqa: E501
                is_mqtt_extension=server_utils.should_use_mqtt_protocol(self.config))  # noqa: E501
        except Exception as err:
            logger.SERVER_LOGGER.info(err)
            raise
        finally:
            if sysadmin_client:
                sysadmin_client.logout()

        if server_utils.should_use_mqtt_protocol(self.config):
            # Store/setup MQTT extension, api filter, and token info
            try:
                sysadmin_client = \
                    vcd_utils.get_sys_admin_client(api_version=None)
                mqtt_ext_manager = MQTTExtensionManager(sysadmin_client)
                ext_info = mqtt_ext_manager.get_extension_info(
                    ext_name=server_constants.CSE_SERVICE_NAME,
                    ext_version=server_constants.MQTT_EXTENSION_VERSION,
                    ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
                ext_urn_id = ext_info[server_constants.MQTTExtKey.EXT_URN_ID]
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
                    ext_urn_id=ext_urn_id
                )

                for key, value in ext_info.items():
                    self.config.set_value_at(f"mqtt.{key}", value)
                for key, value in token_info.items():
                    self.config.set_value_at(f"mqtt.{key}", value)
                self.config.set_value_at(
                    f"mqtt.{server_constants.MQTTExtKey.EXT_UUID}", ext_uuid
                )
            except Exception as err:
                msg = f'MQTT extension setup error: {err}'
                logger.SERVER_LOGGER.error(msg)
                raise err
            finally:
                if sysadmin_client:
                    sysadmin_client.logout()

        if not server_utils.is_no_vc_communication_mode(self.config):
            populate_vsphere_list(self.config.get_value_at('vcs'))

        # Load def entity-type and interface
        self._load_def_schema(msg_update_callback=msg_update_callback)

        # Read k8s catalog definition from catalog item metadata and append
        # the same to to server run-time config
        if not server_utils.is_no_vc_communication_mode(self.config):
            native_templates = \
                template_reader.read_native_template_definition_from_catalog(
                    config=self.config,
                    msg_update_callback=msg_update_callback
                )
            self.config.set_value_at('broker.templates', native_templates)
        else:
            msg = "Skipping loading k8s template definition from catalog " \
                  "since `No communication with VCenter` mode is on."
            logger.SERVER_LOGGER.info(msg)
            msg_update_callback.general_no_color(msg)
            self.config.set_value_at('broker.templates', [])

        # Read TKGm catalog definition from catalog item metadata and append
        # the same to to server run-time config

        tkgm_templates = \
            template_reader.read_tkgm_template_definition_from_catalog(
                config=self.config,
                msg_update_callback=msg_update_callback
            )
        self.config.set_value_at('broker.tkgm_templates', tkgm_templates)

        self._load_placement_policy_details(
            msg_update_callback=msg_update_callback
        )

        if self.config.get_value_at('service.legacy_mode'):
            # Read templates rules from config and update template definition
            # in server run-time config
            self._process_template_rules(
                msg_update_callback=msg_update_callback
            )

            # Make sure that all vms in templates are compliant with the
            # compute policy specified in template definition (can be affected
            # by rules).
            self._process_template_compute_policy_compliance(
                msg_update_callback=msg_update_callback
            )
        else:
            msg = "Template rules are not supported by CSE for vCD api " \
                  "version 35.0 or above. Skipping template rule processing."
            msg_update_callback.info(msg)
            logger.SERVER_LOGGER.debug(msg)

        if self.should_check_config:
            # TODO: find a better way to get the raw dictionary from the object
            # this method is also called via CSE server cli,
            # so can't force this method to accept a ServerConfig object
            configure_cse.check_cse_installation(
                self.config._config,
                msg_update_callback=msg_update_callback
            )

        try:
            pks_config = self.config.get_value_at('pks_config')
            if pks_config:
                self.pks_cache = PksCache(
                    pks_servers=pks_config.get('pks_api_servers', []),
                    pks_accounts=pks_config.get('pks_accounts', []),
                    pvdcs=pks_config.get('pvdcs', []),
                    orgs=pks_config.get('orgs', []),
                    nsxt_servers=pks_config.get('nsxt_servers', [])
                )
        except KeyError:
            pass

        num_processors = self.config.get_value_at('service.processors')
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
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(self.skip_config_decryption),  # noqa: E501
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

        :param utils.NullMessagePrinter msg_update_callback:
        """
        sysadmin_client = None
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client(api_version=None)
            logger_wire = logger.NULL_LOGGER
            try:
                if utils.str_to_bool(self.config.get_value_at('service.log_wire')):   # noqa: E501
                    logger_wire = logger.SERVER_CLOUDAPI_WIRE_LOGGER
            except KeyError:
                pass

            cloudapi_client = \
                vcd_utils.get_cloudapi_client_from_vcd_client(
                    client=sysadmin_client,
                    logger_debug=logger.SERVER_LOGGER,
                    logger_wire=logger_wire
                )
            raise_error_if_def_not_supported(cloudapi_client)

            server_rde_version = server_utils.get_rde_version_in_use()
            msg_update_callback.general(f"Using RDE version: {server_rde_version}")  # noqa: E501

            schema_svc = def_schema_svc.DefSchemaService(cloudapi_client)
            def_metadata_dict: dict = def_utils.get_rde_metadata(server_rde_version)  # noqa: E501
            entity_type: common_models.DefEntityType = \
                def_metadata_dict[def_constants.RDEMetadataKey.ENTITY_TYPE]  # noqa: E501
            interfaces: List[common_models.DefInterface] = \
                def_metadata_dict[def_constants.RDEMetadataKey.INTERFACES]  # noqa: E501

            for interface in interfaces:
                # TODO change _kubernetesInterface to an array once additional
                # interface for CSE is added.
                self._kubernetesInterface = \
                    schema_svc.get_interface(interface.get_id())

            self._nativeEntityType = \
                schema_svc.get_entity_type(entity_type.get_id())

            msg = f"Successfully loaded defined entity schema " \
                  f"{entity_type.get_id()} to global context"
            msg_update_callback.general(msg)
            logger.SERVER_LOGGER.debug(msg)
        except cse_exception.DefNotSupportedException:
            msg = "Skipping initialization of defined entity type" \
                  " and defined entity interface"
            msg_update_callback.info(msg)
            logger.SERVER_LOGGER.debug(msg)
        except cse_exception.DefSchemaServiceError as e:
            msg = f"Error while loading defined entity schema: {e.error_message}"  # noqa: E501
            msg_update_callback.error(msg)
            logger.SERVER_LOGGER.debug(msg)
            raise
        except Exception as e:
            msg = f"Failed to load defined entity schema to global context: {str(e)}"  # noqa: E501
            msg_update_callback.error(msg)
            logger.SERVER_LOGGER.error(msg)
            raise
        finally:
            if sysadmin_client:
                sysadmin_client.logout()

    def _load_placement_policy_details(
            self, msg_update_callback=utils.NullPrinter()):
        msg = "Loading kubernetes runtime placement policies."
        logger.SERVER_LOGGER.info(msg)
        msg_update_callback.general(msg)
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client(api_version=None)
            if sysadmin_client.get_vcd_api_version() < compute_policy_manager.GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION:  # noqa: E501
                msg = "Placement policies for kubernetes runtimes not " \
                      " supported in api version " \
                      f"{sysadmin_client.get_api_version()}"  # noqa: E501
                logger.SERVER_LOGGER.debug(msg)
                msg_update_callback.info(msg)
                return

            self.config.set_value_at('placement_policy_hrefs', {})
            cpm = compute_policy_manager.ComputePolicyManager(
                sysadmin_client,
                log_wire=self.config.get_value_at('service.log_wire')
            )
            for runtime_policy in shared_constants.CLUSTER_RUNTIME_PLACEMENT_POLICIES:  # noqa: E501
                k8_runtime = shared_constants.RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP[runtime_policy]  # noqa: E501
                try:
                    placement_policy_href = \
                        compute_policy_manager.get_cse_vdc_compute_policy(
                            cpm,
                            runtime_policy,
                            is_placement_policy=True
                        )['href']
                    self.config.set_value_at(
                        f'placement_policy_hrefs.{k8_runtime}',
                        placement_policy_href
                    )
                except EntityNotFoundException:
                    pass
        except Exception as e:
            msg = f"Failed to load placement policies to server runtime configuration: {str(e)}"  # noqa: E501
            msg_update_callback.error(msg)
            logger.SERVER_LOGGER.error(msg)
            raise

    def _process_template_rules(self, msg_update_callback=utils.NullPrinter()):
        try:
            rules = self.config.get_value_at('template_rules')
            if not rules:
                return
        except KeyError:
            return

        templates = self.config.get_value_at('broker.templates')

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
                                                    msg_update_callback=utils.NullPrinter()):  # noqa: E501
        msg = "Processing compute policy for k8s templates."
        logger.SERVER_LOGGER.info(msg)
        msg_update_callback.general_no_color(msg)

        org_name = self.config.get_value_at('broker.org')
        catalog_name = self.config.get_value_at('broker.catalog')
        sysadmin_client = None
        try:
            sysadmin_client = vcd_utils.get_sys_admin_client(api_version=None)
            cpm = compute_policy_manager.ComputePolicyManager(
                sysadmin_client,
                log_wire=self.config.get_value_at('service.log_wire')
            )

            for template in self.config.get_value_at('broker.templates'):
                policy_name = template[server_constants.LegacyLocalTemplateKey.COMPUTE_POLICY.value]  # noqa: E501
                catalog_item_name = template[server_constants.LegacyLocalTemplateKey.CATALOG_ITEM_NAME.value]  # noqa: E501
                # if policy name is not empty, stamp it on the template
                if policy_name:
                    try:
                        policy = \
                            compute_policy_manager.get_cse_vdc_compute_policy(
                                cpm, policy_name)  # noqa: E501
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
