import container_service_extension.service as service


def system_info(request_dict, tenant_auth_token):
    """Request handler for system info operation.

    :return: Dictionary with system info data.
    """
    return service.Service().info(tenant_auth_token)


def system_update(request_dict, tenant_auth_token):
    """Request handler for system update operation.

    :return: Dictionary with system update status.
    """
    return {
        'message': service.Service().update_status(tenant_auth_token,
                                                   request_dict)
    }
