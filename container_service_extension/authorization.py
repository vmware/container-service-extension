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


def _get_user_rights(sys_admin_client, user_session):
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
    user_rights = _get_user_rights(sys_admin_client, user_session)

    missing_rights = []
    for right in required_rights:
        qualified_right_name = '{' + CSE_SERVICE_NAMESPACE + '}:' + right
        if qualified_right_name not in user_rights:
            missing_rights.append(qualified_right_name)

    if len(missing_rights) == 0:
        return True

    LOGGER.debug(f"Authorization failed for user: {user_session.get('name')}."
                 f" Missing rights:{missing_rights}.")
    return False


def secure(required_rights=[]):
    """."""
    def decorator_secure(func):
        @functools.wraps(func)
        def decorator_wrapper(*args, **kwargs):
            broker_instance = args[0]  # self
            user_session = broker_instance.get_tenant_client_session()
            sys_admin_client = broker_instance.get_sys_admin_client()
            if _is_authorized(sys_admin_client, user_session, required_rights):
                return func(*args, **kwargs)
            else:
                raise Exception('Access Forbidden. Missing required rights.')
        return decorator_wrapper
    return decorator_secure
