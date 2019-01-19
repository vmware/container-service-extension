# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.org import Org

from container_service_extension.exceptions import AccessForbiddenException
from container_service_extension.logger import SERVER_LOGGER as LOGGER


def _get_user_rights(sys_admin_client, user_session):
    user_org_link = find_link(resource=user_session,
                              rel=RelationType.DOWN.value,
                              media_type=EntityType.ORG.value)
    user_org_href = user_org_link.get('href')
    org = Org(sys_admin_client, href=user_org_href)
    user_role = user_session.get('roles')
    role = org.get_role_resource(user_role)
    return role.list_rights()


def _is_authorized(sys_admin_client, user_session, required_rights):
    user_rights = _get_user_rights(sys_admin_client, user_session)
    missing_rights = []
    for right in required_rights:
        if right not in user_rights:
            missing_rights.add(right)

    if len(missing_rights) == 0:
        return True

    LOGGER.debug(f"Authorization failed for user: {user_session.get('name')}."
                 " Missing rights:{missing_rights}.")
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
                raise AccessForbiddenException()
        return decorator_wrapper
    return decorator_secure
