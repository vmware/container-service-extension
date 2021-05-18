# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from typing import Dict, Optional

import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.logging.logger as logger
import container_service_extension.security.context.user_context as user_context  # noqa: E501


class OperationContext:
    def __init__(self, auth_token: str, is_jwt: bool = True, request_id: Optional[str] = None, mqtt_publisher=None):  # noqa: E501
        self._auth_token: str = auth_token
        self._is_jwt: bool = is_jwt
        # Request ID; may be None if OperationContext is initialized outside of
        # request_dispatcher.py
        self.request_id: Optional[str] = request_id

        # map for storing user's context at different api versions
        # `None` key, maps to the client at the highest api version supported
        # by the vCD and pyvcloud
        self._user_context_map: Dict[Optional[str], user_context.UserContext] = {}  # noqa: E501

        # map for storing sys admin user's context at different api versions
        # `None` key maps to the client at the highest api version supported
        # by the vCD and pyvcloud
        self._sysadmin_user_context_map: Dict[Optional[str], user_context.UserContext] = {}  # noqa: E501

        # async operations should call end() when they are finished
        self.is_async: bool = False

        self.mqtt_publisher = mqtt_publisher

    @property
    def client(self):
        return self.user.client

    @property
    def cloudapi_client(self):
        return self.user.cloud_api_client

    @property
    def sysadmin_client(self):
        return self.sysadmin_user.client

    @property
    def sysadmin_cloudapi_client(self):
        return self.sysadmin_user.cloud_api_client

    @property
    def user(self):
        api_version = None  # marker for default api version
        return self.get_user_context(api_version)

    @property
    def sysadmin_user(self):
        api_version = None  # marker for default api version
        return self.get_sysadmin_user_context(api_version)

    def get_client(self, api_version: Optional[str]):
        return self.get_user_context(api_version).client

    def get_cloudapi_client(self, api_version: Optional[str]):
        return self.get_user_context(api_version).cloud_api_client

    def get_sysadmin_client(self, api_version: Optional[str]):
        return self.get_sysadmin_user_context(api_version).client

    def get_sysadmin_cloudapi_client(self, api_version: Optional[str]):
        return self.get_sysadmin_user_context(api_version).cloud_api_client

    def get_user_context(self, api_version: Optional[str]):
        if api_version not in self._user_context_map:
            self._update_user_context_map(api_version=api_version)
        return self._user_context_map[api_version]

    def get_sysadmin_user_context(self, api_version: Optional[str]):
        if api_version not in self._sysadmin_user_context_map:
            self._update_sysadmin_user_context_map(api_version=api_version)
        return self._sysadmin_user_context_map[api_version]

    def _update_user_context_map(self, api_version: Optional[str]):
        _client = vcd_utils.connect_vcd_user_via_token(
            tenant_auth_token=self._auth_token,
            is_jwt_token=self._is_jwt,
            api_version=api_version)

        log_wire = server_utils.get_server_runtime_config() \
            .get('service', {}).get('log_wire', False)  # noqa: E501
        logger_wire = logger.NULL_LOGGER
        if log_wire:
            logger_wire = logger.SERVER_CLOUDAPI_WIRE_LOGGER
        _cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
            _client,
            logger.SERVER_LOGGER,
            logger_wire)

        _user_context = user_context.UserContext(
            client=_client, cloud_api_client=_cloudapi_client)
        self._user_context_map[api_version] = _user_context

    def _update_sysadmin_user_context_map(self, api_version: Optional[str]):
        _sysadmin_client = vcd_utils.get_sys_admin_client(
            api_version=api_version)

        log_wire = server_utils.get_server_runtime_config() \
            .get('service', {}).get('log_wire', False)
        logger_wire = logger.NULL_LOGGER
        if log_wire:
            logger_wire = logger.SERVER_CLOUDAPI_WIRE_LOGGER
        _sysadmin_cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                _sysadmin_client,
                logger.SERVER_LOGGER,
                logger_wire)

        _sysadmin_user_context = user_context.UserContext(
            client=_sysadmin_client,
            cloud_api_client=_sysadmin_cloudapi_client)
        self._sysadmin_user_context_map[api_version] = _sysadmin_user_context

    def end(self):
        for api_version, sysadmin_user_context in \
                self._sysadmin_user_context_map.items():
            try:
                sysadmin_user_context.client.logout()
            except Exception:
                if not api_version:
                    api_version = "Default api version"
                msg = f"Failed to logout user: {sysadmin_user_context.name}" \
                    f"at api_version: {api_version}."
                logger.SERVER_LOGGER.debug(msg)
        self._user_context_map.clear()
        self._sysadmin_user_context_map.clear()
