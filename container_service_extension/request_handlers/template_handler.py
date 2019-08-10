from container_service_extension.server_constants import LocalTemplateKey
import container_service_extension.utils as utils


def template_list(request_data, tenant_auth_token):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = utils.get_server_runtime_config()
    templates = []
    for t in config['broker']['templates']:
        templates.append({
            'name': t[LocalTemplateKey.NAME],
            'revision': t[LocalTemplateKey.REVISION],
            'is_default': t[LocalTemplateKey.NAME] == config['broker']['default_template_name'] and str(t[LocalTemplateKey.REVISION]) == str(config['broker']['default_template_revision']), # noqa: E501
            'catalog': config['broker']['catalog'],
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'description': t[LocalTemplateKey.DESCRIPTION].replace("\\n", ", ")
        })
    return templates
