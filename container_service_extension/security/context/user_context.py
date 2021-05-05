# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from typing import List, Optional

import lxml.objectify as lxml
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.role as vcd_role

import container_service_extension.lib.cloudapi.cloudapi_client as cloudapi_client  # noqa: E501
import container_service_extension.logging.logger as logger

ORG_ADMIN_RIGHTS = [
    'General: Administrator Control',
    'General: Administrator View'
]


class UserContext:
    def __init__(self, client: vcd_client.Client,
                 cloud_api_client: cloudapi_client.CloudApiClient):
        self.client: vcd_client.Client = client
        self.cloud_api_client: cloudapi_client.CloudApiClient = \
            cloud_api_client
        self._session: Optional[lxml.ObjectifiedElement] = None
        self._name: Optional[str] = None
        self._id: Optional[str] = None
        self._org_name: Optional[str] = None
        self._org_href: Optional[str] = None
        self._role: Optional[str] = None
        self._rights: Optional[List[str]] = None

    @property
    def session(self):
        if self._session is None:
            self._session = self.client.get_vcloud_session()
        return self._session

    @property
    def name(self):
        """User name from vCD session."""
        if self._name is None:
            self._name = self.session.get('user')
        return self._name

    @property
    def id(self):
        """User ID from vCD session."""
        if self._id is None:
            self._id = self.session.get('userId')
        return self._id

    @property
    def org_name(self):
        if self._org_name is None:
            self._org_name = self.session.get('org')
        return self._org_name

    @property
    def org_href(self):
        if self._org_href is None:
            self._org_href = self.client.get_org().get('href')
        return self._org_href

    @property
    def role(self):
        if self._role is None:
            self._role = self.session.get('roles')
        return self._role

    @property
    def rights(self):
        # If the user is unable to fetch the list of rights, then they
        # can't be sys admin or org admin. And anyone other than those
        # two shouldn't be able to see their own set of rights.
        if self._rights is None:
            try:
                org = vcd_org.Org(self.client, href=self.org_href)
                role = vcd_role.Role(self.client,
                                     resource=org.get_role_resource(self.role))

                self._rights = []
                for right_dict in role.list_rights():
                    right_name = right_dict.get('name')
                    if right_name is not None:
                        self._rights.append(right_name)
            # maybe replace with Forbidden exception?
            except Exception:
                msg = f"Unable to fetch right records for User: {self.name}"
                logger.SERVER_LOGGER.debug(msg, exc_info=True)

        return self._rights

    @property
    def has_org_admin_rights(self):
        return all(right in self.rights for right in ORG_ADMIN_RIGHTS)
