import container_service_extension.utils as utils


def template_list(request_dict, tenant_auth_token):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = utils.get_server_runtime_config()
    templates = []
    for t in config['broker']['templates']:
        templates.append({
            'name': t['name'],
            'is_default': t['name'] == config['broker']['default_template'],
            'catalog': config['broker']['catalog'],
            'catalog_item': t['catalog_item'],
            'description': t['description']
        })
    return templates
