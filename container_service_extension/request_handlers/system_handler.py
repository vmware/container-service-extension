import container_service_extension.service as service


def system_info(request_dict, tenant_auth_token):
    return service.Service().info(tenant_auth_token)


def system_update(request_dict, tenant_auth_token):
    return {'message': service.Service().update_status(tenant_auth_token, request_dict)}
