# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501


@record_user_action_telemetry(cse_operation=CseOperation.TEMPLATE_LIST_CLIENT_SIDE)  # noqa: E501
def template_list(request_data, op_ctx):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = server_utils.get_server_runtime_config()
    templates = []
    default_template_name = config['broker']['default_template_name']
    default_template_revision = str(config['broker']['default_template_revision'])  # noqa: E501

    for t in config['broker']['templates']:
        template_name = t[LocalTemplateKey.NAME]
        template_revision = str(t[LocalTemplateKey.REVISION])
        is_default = (template_name, template_revision) == (default_template_name, default_template_revision)  # noqa: E501

        templates.append({
            'catalog': config['broker']['catalog'],
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'cni': t[LocalTemplateKey.CNI],
            'cni_version': t[LocalTemplateKey.CNI_VERSION],
            'deprecated': t[LocalTemplateKey.DEPRECATED],
            'description': t[LocalTemplateKey.DESCRIPTION].replace("\\n", ", "),  # noqa: E501
            'docker_version': t[LocalTemplateKey.DOCKER_VERSION],
            'is_default': 'Yes' if is_default else 'No',
            'kind': t[LocalTemplateKey.KIND],
            'kubernetes': t[LocalTemplateKey.KUBERNETES],
            'kubernetes_version': t[LocalTemplateKey.KUBERNETES_VERSION],
            'name': template_name,
            'os': t[LocalTemplateKey.OS],
            'revision': template_revision
        })

    return sorted(templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501
