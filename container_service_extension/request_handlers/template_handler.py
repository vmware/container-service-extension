# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
import container_service_extension.utils as utils


@record_user_action_telemetry(cse_operation=CseOperation.TEMPLATE_LIST_CLIENT_SIDE)  # noqa: E501
def template_list(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = utils.get_server_runtime_config()
    templates = []
    for t in config['broker']['templates']:
        template_name = t[LocalTemplateKey.NAME]
        template_revision = str(t[LocalTemplateKey.REVISION])
        default_template_name = config['broker']['default_template_name']
        default_template_revision = str(config['broker']['default_template_revision'])  # noqa: E501
        is_default = (template_name, template_revision) == (default_template_name, default_template_revision)  # noqa: E501

        templates.append({
            'name': template_name,
            'revision': template_revision,
            'is_default': 'Yes' if is_default else 'No',
            'catalog': config['broker']['catalog'],
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'description': t[LocalTemplateKey.DESCRIPTION].replace("\\n", ", ")
        })

    return sorted(templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501
