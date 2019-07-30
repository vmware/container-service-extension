from container_service_extension.server_constants import LocalTemplateKey
import container_service_extension.utils as utils


def template_list(request_dict, tenant_auth_token):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = utils.get_server_runtime_config()
    templates = []
    for t in config['broker']['templates']:
        templates.append({
            'name': t[LocalTemplateKey.NAME],
            'is_default': t[LocalTemplateKey.NAME] == config['broker']['default_template_name'] and t[LocalTemplateKey.REVISION] == config['broker']['default_template_revision'], # noqa: E501
            'catalog': config['broker']['catalog'],
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'description': t[LocalTemplateKey.DESCRIPTION]
        })
    return templates
