# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from container_service_extension.common.constants.server_constants import CSE_SERVICE_NAMESPACE  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.server.abstract_broker as abstract_broker


def secure(required_rights=None):
    """Secure methods against unauthorized access using this decorator.

    Only compatible with methods in AbstractBroker-derived classes.

    :param list required_rights: a list of rights (as str). The right name
        shouldn't be namespaced.

    :return: a method reference to the decorating method.

    :rtype: method
    """
    if required_rights is None:
        required_rights = []

    def decorator_secure(func):
        @functools.wraps(func)
        def decorator_wrapper(*args, **kwargs):
            server_config = server_utils.get_server_runtime_config()

            if (server_config['service']['enforce_authorization']
                    and required_rights is not None
                    and len(required_rights) > 0):
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

            return func(*args, **kwargs)
        return decorator_wrapper
    return decorator_secure
