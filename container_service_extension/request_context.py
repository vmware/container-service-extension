import enum

import pyvcloud.vcd.client as vcd_client

import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.user_context as user_context


class RequestContext:
    def __init__(self, auth_token, is_jwt=True):
        self._auth_token: str = auth_token
        self._is_jwt: bool = is_jwt

        # vCD API client from user auth token
        self._client: vcd_client.Client = None

        self._sysadmin_client: vcd_client.Client = None

        # User contest
        self._user: user_context.UserContext = None

        # Request cache; keys defined in CacheKey enum
        self.cache = {}

    @property
    def client(self):
        if self._client is None:
            self._client = vcd_utils.connect_vcd_user_via_token(
                tenant_auth_token=self._auth_token,
                is_jwt_token=self._is_jwt)
        return self._client

    @property
    def user(self):
        if self._user is None:
            self._user = user_context.UserContext(self.client)
        return self._user

    @property
    def sysadmin_client(self):
        if self._sysadmin_client is None:
            self._sysadmin_client = vcd_utils.get_sys_admin_client()
        return self._sysadmin_client

    def end(self):
        self.user.end()
        try:
            self._sysadmin_client.logout()
        except Exception:
            pass
        try:
            self.client.logout()
        except Exception:
            pass


@enum.unique
class CacheKey(str, enum.Enum):
    TargetOrgName = 'target_org_name'
    TargetOvdcName = 'target_ovdc_name'
    TargetClusterName = 'target_cluster_name'
