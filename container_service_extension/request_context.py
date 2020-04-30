import enum

import pyvcloud.vcd.client as vcd_client

import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.user_context as user_context


class RequestContext:
    def __init__(self, auth_token, is_jwt=True, request_id=None):
        self._auth_token: str = auth_token
        self._is_jwt: bool = is_jwt

        # vCD API client from user auth token
        self._client: vcd_client.Client = None

        # User context
        self._user: user_context.UserContext = None

        # async operations should call end() when they are finished
        self.is_async: bool = False

        # Request cache; keys defined in CacheKey enum
        self.cache = {}

        # Request ID; may be None if RequestContext is initialized outside of
        # request_processor.py
        self.request_id: str = request_id

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
        return self.user.sysadmin_client

    def end(self):
        self.user.end()


@enum.unique
class CacheKey(str, enum.Enum):
    pass
