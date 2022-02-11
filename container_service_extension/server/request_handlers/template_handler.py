# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
from container_service_extension.common.constants.server_constants import TKGmTemplateKey  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
from container_service_extension.logging import logger
from container_service_extension.server import template_reader


@record_user_action_telemetry(cse_operation=CseOperation.TEMPLATE_LIST_CLIENT_SIDE)  # noqa: E501
def template_list(request_data, op_ctx):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = server_utils.get_server_runtime_config()
    templates = []

    for t in config.get_value_at('broker.templates'):
        template_name = t[LocalTemplateKey.NAME]
        template_revision = str(t[LocalTemplateKey.REVISION])

        templates.append({
            'catalog': config.get_value_at('broker.catalog'),
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'cni': t[LocalTemplateKey.CNI],
            'cni_version': t[LocalTemplateKey.CNI_VERSION],
            'deprecated': t[LocalTemplateKey.DEPRECATED],
            'description': t[LocalTemplateKey.DESCRIPTION].replace("\\n", ", "),  # noqa: E501
            'docker_version': t[LocalTemplateKey.DOCKER_VERSION],
            'is_default': 'No',
            'kind': t[LocalTemplateKey.KIND],
            'kubernetes': t[LocalTemplateKey.KUBERNETES],
            'kubernetes_version': t[LocalTemplateKey.KUBERNETES_VERSION],
            'name': template_name,
            'os': t[LocalTemplateKey.OS],
            'revision': template_revision
        })

    return sorted(templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501


@record_user_action_telemetry(cse_operation=CseOperation.TEMPLATE_LIST_CLIENT_SIDE)  # noqa: E501
def tkgm_template_list(request_data, op_ctx):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = server_utils.get_server_runtime_config()
    tkgm_templates = []

    for t in config.get_value_at('broker.tkgm_templates'):
        tkgm_templates.append({
            'catalog': config.get_value_at('broker.catalog'),
            'catalog_item': t[TKGmTemplateKey.NAME],
            'cni': t[TKGmTemplateKey.CNI],
            'cni_version': t[TKGmTemplateKey.CNI_VERSION],
            'cse_version': t[TKGmTemplateKey.CSE_VERSION],
            'deprecated': None,
            'description': None,
            'docker_version': None,
            'container_runtime': t[TKGmTemplateKey.CONTAINER_RUNTIME],
            'container_runtime_version': t[TKGmTemplateKey.CONTAINER_RUNTIME_VERSION],  # noqa: E501
            'is_default': False,
            'kind': t[TKGmTemplateKey.KIND],
            'kubernetes': t[TKGmTemplateKey.KUBERNETES],
            'kubernetes_version': t[TKGmTemplateKey.KUBERNETES_VERSION],
            'name': t[TKGmTemplateKey.NAME],
            'os': f"{t[TKGmTemplateKey.OS]}-{t[TKGmTemplateKey.OS_VERSION]}",
            'revision': int(t[TKGmTemplateKey.REVISION])
        })

    return sorted(tkgm_templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501


def reload_templates(request_data, op_ctx):
    """."""
    server_config = server_utils.get_server_runtime_config()
    if not server_utils.is_no_vc_communication_mode():
        native_templates = \
            template_reader.read_native_template_definition_from_catalog(
                config=server_config
            )
        server_config.set_value_at('broker.templates', native_templates)
    else:
        msg = "Skipping loading k8s template definition from catalog " \
              "since `No communication with VCenter` mode is on."
        logger.SERVER_LOGGER.info(msg)
        server_config.set_value_at('broker.templates', [])

    tkgm_templates = \
        template_reader.read_tkgm_template_definition_from_catalog(
            config=server_config
        )
    server_config.set_value_at('broker.tkgm_templates', tkgm_templates)

    return_dict = {
        "message": "Successfully reloaded native and TKG templates into memory."
    }
    return return_dict
