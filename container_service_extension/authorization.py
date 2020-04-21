# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

import pyvcloud.vcd.client as vcd_client

import container_service_extension.abstract_broker as abstract_broker
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.server_constants import CSE_SERVICE_NAMESPACE
import container_service_extension.utils as utils


def secure(required_rights=[], sysadmin_client: vcd_client.Client = None):
    """Secure methods against unauthorized access using this decorator.

    Only compatible with methods in AbstractBroker-derived classes.

    :param list required_rights: a list of rights (as str). The right name
        shouldn't be namespaced.

    :return: a method reference to the decorating method.

    :rtype: method
    """
    def decorator_secure(func):
        @functools.wraps(func)
        def decorator_wrapper(*args, **kwargs):
            nonlocal sysadmin_client
            server_config = utils.get_server_runtime_config()
            # only logout if this function needs to create sysadmin
            logout = not bool(sysadmin_client)

            if (server_config['service']['enforce_authorization']
                    and required_rights is not None
                    and len(required_rights) > 0):
                try:
                    if sysadmin_client is None:
                        sysadmin_client = vcd_utils.get_sys_admin_client()
                    # dev guard: should never occur in production
                    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
                    class_instance: abstract_broker.AbstractBroker = args[0]
                    user_rights = class_instance.context.user.rights

                    missing_rights = []
                    for right_name in required_rights:
                        namespaced_name = f'{{{CSE_SERVICE_NAMESPACE}}}' \
                                          f':{right_name}'
                        if namespaced_name not in user_rights:
                            missing_rights.append(namespaced_name)

                    if len(missing_rights) > 0:
                        LOGGER.debug(f"Authorization failed for user "
                                     f"'{class_instance.context.user.name}'. "
                                     f"Missing required rights: "
                                     f"{missing_rights}")
                        raise Exception(f'Access forbidden. Missing required '
                                        f'rights: {missing_rights}')
                finally:
                    if logout and sysadmin_client is not None:
                        sysadmin_client.logout()

            return func(*args, **kwargs)
        return decorator_wrapper
    return decorator_secure
