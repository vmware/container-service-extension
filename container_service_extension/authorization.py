# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.role import Role

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.server_constants import CSE_SERVICE_NAMESPACE
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import get_vcd_sys_admin_client


def _get_user_rights(sys_admin_client, user_session):
    """Return rights associated with the role of an user.

    :param pyvcloud.vcd.client.Client sys_admin_client: the sys admin cilent
        that will be used to query vCD about the rights and roles of the
        concerned user.
    :param lxml.objectify.ObjectifiedElement user_session:

    :return: the list of rights contained in the role of the user
        (corresponding to the user_session).

    :rtype: list of str
    """
    user_org_link = find_link(resource=user_session,
                              rel=RelationType.DOWN,
                              media_type=EntityType.ORG.value)
    user_org_href = user_org_link.href
    org = Org(sys_admin_client, href=user_org_href)
    user_role_name = user_session.get('roles')
    role = Role(sys_admin_client,
                resource=org.get_role_resource(user_role_name))

    user_rights = []
    user_rights_as_list_of_dict = role.list_rights()
    for right_dict in user_rights_as_list_of_dict:
        user_rights.append(right_dict.get('name'))
    return user_rights


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

    user_rights = _get_user_rights(sys_admin_client, user_session)

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
    """Decorator to secure methods against unauthorized access.

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
                    sys_admin_client = get_vcd_sys_admin_client()
                    broker_instance = args[0]  # self
                    user_session = broker_instance.get_tenant_client_session()
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
