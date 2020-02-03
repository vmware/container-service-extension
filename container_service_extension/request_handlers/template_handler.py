# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.server_constants import LocalTemplateKey
import container_service_extension.utils as utils


def template_list(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = utils.get_server_runtime_config()
    templates = []
    for t in config['broker']['templates']:
        is_default = (t[LocalTemplateKey.NAME], str(t[LocalTemplateKey.REVISION])) == (config['broker']['default_template_name'], str(config['broker']['default_template_revision'])) # noqa: E501
        templates.append({
            'name': t[LocalTemplateKey.NAME],
            'revision': t[LocalTemplateKey.REVISION],
            'is_default': 'Yes' if is_default else 'No',
            'catalog': config['broker']['catalog'],
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'description': t[LocalTemplateKey.DESCRIPTION].replace("\\n", ", ")
        })

    return sorted(templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501
