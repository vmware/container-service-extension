import lxml.objectify as lxml
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.role as vcd_role

import container_service_extension.cloudapi.cloudapi_client as cloudApiClient
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.utils as utils


ORG_ADMIN_RIGHTS = [
    'General: Administrator Control',
    'General: Administrator View'
]


class UserContext:
    def __init__(self, client: vcd_client.Client,
                 cloudapi_client: cloudApiClient.CloudApiClient):
        self.client: vcd_client.Client = client
        self._cloudapi_client: cloudApiClient.CloudApiClient = cloudapi_client
        self._session: lxml.ObjectifiedElement = None
        self._name: str = None
        self._id: str = None
        self._org_name: str = None
        self._org_href: str = None
        self._role: str = None
        self._rights: [str] = None

        self._sysadmin_client: vcd_client.Client = None
        self._sysadmin_cloudapi_client: cloudApiClient.CloudApiClient = None
        self._is_sys_admin: bool = None

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
    def is_sys_admin(self):
        if self._is_sys_admin is None:
            self._is_sys_admin = self.client.is_sysadmin()
        return self._is_sys_admin

    @property
    def org_name(self):
        if self._org_name is None:
            self._org_name = self.session.get('org')
        return self._org_name

    @property
    def org_href(self):
        if self._org_href is None:
            # href of the org that the user belongs to
            self._org_href = self.client._get_wk_endpoint(
                vcd_client._WellKnownEndpoint.LOGGED_IN_ORG)
        return self._org_href

    @property
    def role(self):
        if self._role is None:
            self._role = self.session.get('roles')
        return self._role

    @property
    def rights(self):
        if self._rights is None:
            # Query is restricted to system administrator
            org = vcd_org.Org(self.sysadmin_client, href=self.org_href)
            role = vcd_role.Role(self.sysadmin_client,
                                 resource=org.get_role_resource(self.role))

            self._rights = []
            for right_dict in role.list_rights():
                right_name = right_dict.get('name')
                if right_name is not None:
                    self._rights.append(right_name)

        return self._rights

    @property
    def has_org_admin_rights(self):
        return all(right in self.rights for right in ORG_ADMIN_RIGHTS)

    @property
    def sysadmin_client(self):
        if self._sysadmin_client is None:
            self._sysadmin_client = vcd_utils.get_sys_admin_client()
        return self._sysadmin_client

    @property
    def sysadmin_cloudapi_client(self):
        if self._sysadmin_cloudapi_client is None:
            log_wire = utils.get_server_runtime_config() \
                            .get('service', {}).get('log_wire', False)
            logger_wire = logger.NULL_LOGGER
            if log_wire:
                logger_wire = logger.SERVER_CLOUDAPI_WIRE_LOGGER
            self._sysadmin_cloudapi_client = \
                vcd_utils.get_cloudapi_client_from_vcd_client(
                    self.sysadmin_client,
                    logger.SERVER_LOGGER,
                    logger_wire)
        return self._sysadmin_cloudapi_client

    def end(self):
        try:
            self._sysadmin_client.logout()
        except Exception:
            pass
        finally:
            self._sysadmin_client = None
            self._cloudapi_client = None
