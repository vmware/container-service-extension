# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pyvcloud_utils import get_sys_admin_client
from container_service_extension.pyvcloud_utils import get_user_rights
from container_service_extension.server_constants import CSE_SERVICE_NAMESPACE
from container_service_extension.utils import get_server_runtime_config


def _is_authorized(sys_admin_client, user_session, required_rights):
    """Verify if a given user role has all the required rights or not.

    :param pyvcloud.vcd.client.Client sys_admin_client: the sys admin cilent
        that will be used to query vCD about the rights and roles of the
        concerned user.
    :param lxml.objectify.ObjectifiedElement user_session:
    :param list required_rights: a list of str representing the rights that
        we want the user to have.

    :return: True, if the user has all the required rights, else False.

    :rtype: bool
    """
    if required_rights is None or len(required_rights) == 0:
        return True

    user_rights = get_user_rights(sys_admin_client, user_session)

    missing_rights = []
    for right in required_rights:
        qualified_right_name = '{' + CSE_SERVICE_NAMESPACE + '}:' + right
        if qualified_right_name not in user_rights:
            missing_rights.append(qualified_right_name)

    if len(missing_rights) == 0:
        return True

    LOGGER.debug(f"Authorization failed for user: {user_session.get('user')}."
                 f" Missing rights:{missing_rights}.")
    return False


def secure(required_rights=[]):
    """Secure methods against unauthorized access using this decorator.

    Is compatible with methods in classes that derive from abstract_broker.

    :param list required_rights: a list of rights (as str). The right name
        shouldn't be qualified with by namespace.

    :return: a method reference to the decorating method.

    :rtype: method
    """
    def decorator_secure(func):
        @functools.wraps(func)
        def decorator_wrapper(*args, **kwargs):
            sys_admin_client = None
            try:
                is_authorized = True
                server_config = get_server_runtime_config()
                if server_config['service']['enforce_authorization']:
                    sys_admin_client = get_sys_admin_client()
                    broker_instance = args[0]  # self
                    user_session = broker_instance.client_session
                    is_authorized = _is_authorized(sys_admin_client,
                                                   user_session,
                                                   required_rights)
                if is_authorized:
                    return func(*args, **kwargs)
                else:
                    raise Exception(
                        'Access Forbidden. Missing required rights.')
            finally:
                if sys_admin_client is not None:
                    sys_admin_client.logout()
        return decorator_wrapper
    return decorator_secure
