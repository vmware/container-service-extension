# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from pyvcloud.vcd.client import BasicLoginCredentials, Client

import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.config.server_config import ServerConfig
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
import container_service_extension.installer.templates.tkgm_template_manager as ttm  # noqa: E501
from container_service_extension.logging import logger


def read_native_template_definition_from_catalog(
        config: ServerConfig,
        msg_update_callback=utils.NullPrinter()
):
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
            utils.str_to_bool(config.get_value_at('service.log_wire'))
        if log_wire:
            log_filename = logger.SERVER_DEBUG_WIRELOG_FILEPATH

        client = Client(
            uri=config.get_value_at('vcd.host'),
            api_version=config.get_value_at('service.default_api_version'),  # noqa: E501
            verify_ssl_certs=config.get_value_at('vcd.verify'),
            log_file=log_filename,
            log_requests=log_wire,
            log_headers=log_wire,
            log_bodies=log_wire
        )
        credentials = BasicLoginCredentials(
            config.get_value_at('vcd.username'),
            shared_constants.SYSTEM_ORG_NAME,
            config.get_value_at('vcd.password')
        )
        client.set_credentials(credentials)

        legacy_mode = config.get_value_at('service.legacy_mode')
        org_name = config.get_value_at('broker.org')
        catalog_name = config.get_value_at('broker.catalog')

        k8_templates = ltm.get_valid_k8s_local_template_definition(
            client=client, catalog_name=catalog_name, org_name=org_name,
            legacy_mode=legacy_mode,
            is_tkg_plus_enabled=server_utils.is_tkg_plus_enabled(config),
            logger_debug=logger.SERVER_LOGGER,
            msg_update_callback=msg_update_callback)

        return k8_templates
    finally:
        if client:
            client.logout()


def read_tkgm_template_definition_from_catalog(
        config: ServerConfig,
        msg_update_callback=utils.NullPrinter()
):
    msg = "Loading TKGm template definition from catalog"
    logger.SERVER_LOGGER.info(msg)
    msg_update_callback.general_no_color(msg)

    client = None
    try:
        log_filename = None
        log_wire = utils.str_to_bool(
            config.get_value_at('service.log_wire')
        )
        if log_wire:
            log_filename = logger.SERVER_DEBUG_WIRELOG_FILEPATH

        client = Client(
            uri=config.get_value_at('vcd.host'),
            api_version=config.get_value_at('service.default_api_version'),  # noqa: E501
            verify_ssl_certs=config.get_value_at('vcd.verify'),
            log_file=log_filename,
            log_requests=log_wire,
            log_headers=log_wire,
            log_bodies=log_wire
        )
        credentials = BasicLoginCredentials(
            config.get_value_at('vcd.username'),
            shared_constants.SYSTEM_ORG_NAME,
            config.get_value_at('vcd.password')
        )
        client.set_credentials(credentials)

        org_name = config.get_value_at('broker.org')
        catalog_name = config.get_value_at('broker.catalog')

        tkgm_templates = ttm.read_all_tkgm_template(
            client=client,
            org_name=org_name,
            catalog_name=catalog_name,
            logger=logger.SERVER_LOGGER,
            msg_update_callback=msg_update_callback
        )

        return tkgm_templates
    finally:
        if client:
            client.logout()
