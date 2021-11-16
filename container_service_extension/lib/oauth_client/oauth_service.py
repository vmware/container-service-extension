# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import logging
from urllib.parse import urlparse

import pyvcloud.vcd.client as vcd_client

from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
from container_service_extension.lib.cloudapi import cloudapi_client
import container_service_extension.lib.oauth_client.oauth_constants as oauth_constants  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER


class MachineTokenService(cloudapi_client.CloudApiClient):
    """API client for /oauth endpoint."""

    def __init__(self,
                 vcd_api_client: vcd_client.Client,
                 oauth_client_name: str,
                 logger_debug: logging.Logger = NULL_LOGGER,
                 logger_wire: logging.Logger = NULL_LOGGER):

        self.vcd_api_client: vcd_client.Client = vcd_api_client
        cloudapi_url = vcd_api_client.get_cloudapi_uri()

        super().__init__(
            base_url=cloudapi_url,
            token=vcd_api_client.get_access_token(),
            api_version=vcd_api_client.get_api_version(),
            logger_debug=logger_debug,
            logger_wire=logger_wire,
            verify_ssl=vcd_api_client._verify_ssl_certs,
            is_sys_admin=vcd_api_client.is_sysadmin())

        self.oauth_client_name = oauth_client_name

        # cloudapi_url will be of the format https://vcd-host/cloudapi
        # since /oauth endpoint is not associated with /cloudapi or /api,
        # we need to format the cloudapi_url so that only https://vcd-host
        # part is retained
        url_host = urlparse(cloudapi_url)
        self._host_url = f"{url_host.scheme}://{url_host.netloc}"

        self.oauth_client_id = None
        self.refresh_token = None

    def _get_register_oauth_client_url(self):
        register_client_url = \
            f"{self._host_url}{oauth_constants.BASE_OAUTH_ENDPOINT_FRAGMENT}"
        # /oauth endpoint is tenanted. which means, system administrators can
        # access the endpoint using /oauth/provider/register while tenant users
        # can access the endpoint using /oauth/tenant/{orgId}/register
        if self.vcd_api_client.is_sysadmin():
            register_client_url += \
                f"{oauth_constants.OAUTH_PROVIDER_URL_FRAGMENT}" \
                f"{oauth_constants.REGISTER_CLIENT_ENDPOINT_FRAGMENT}"
        else:
            logged_in_org = self.vcd_api_client.get_org()
            org_name = logged_in_org.get('name')
            register_client_url += \
                f"{oauth_constants.OAUTH_TENANT_URL_FRAGMENT}/{org_name}" \
                f"{oauth_constants.REGISTER_CLIENT_ENDPOINT_FRAGMENT}"
        return register_client_url

    def _get_oauth_token_url(self):
        oauth_token_url = \
            f"{self._host_url}{oauth_constants.BASE_OAUTH_ENDPOINT_FRAGMENT}"
        # /oauth endpoint is tenanted. which means, system administrators can
        # access the endpoint using /oauth/provider/token while tenant users
        # can access the endpoint using /oauth/tenant/{orgId}/token
        if self.vcd_api_client.is_sysadmin():
            oauth_token_url += \
                f"{oauth_constants.OAUTH_PROVIDER_URL_FRAGMENT}" \
                f"{oauth_constants.OAUTH_TOKEN_ENDPOINT_FRAGMENT}"
        else:
            logged_in_org = self.vcd_api_client.get_org()
            org_name = logged_in_org.get('name')
            oauth_token_url += \
                f"{oauth_constants.OAUTH_TENANT_URL_FRAGMENT}/" \
                f"{org_name}{oauth_constants.OAUTH_TOKEN_ENDPOINT_FRAGMENT}"
        return oauth_token_url

    def register_oauth_client(self):
        """Register an oauth client to get machine user tokens."""
        register_oauth_client_url = self._get_register_oauth_client_url()
        response = self.do_request(
            method=RequestMethod.POST,
            resource_url_absolute_path=register_oauth_client_url,
            payload={"client_name": self.oauth_client_name},
            content_type="application/json")

        if not response:
            raise Exception(f"Obtained an empty response from {register_oauth_client_url}")  # noqa: E501
        self.oauth_client_id = response['client_id']  # noqa: E501

        return response

    def create_refresh_token(self):
        """Create a refresh token using client_id and jwt token.

        This method can only be executed once per client.
        """
        payload = {
            oauth_constants.OauthPayloadKey.GRANT_TYPE.value: oauth_constants.GrantType.JWT_BEARER.value,  # noqa: E501
            oauth_constants.OauthPayloadKey.CLIENT_ID.value: self.oauth_client_id,  # noqa: E501
            oauth_constants.OauthPayloadKey.ASSERTION.value: self.vcd_api_client.get_access_token()  # noqa: E501
        }
        oauth_token_url = self._get_oauth_token_url()
        response = self.do_request(
            method=RequestMethod.POST,
            resource_url_absolute_path=oauth_token_url,
            content_type="application/x-www-form-urlencoded",
            payload=payload)

        if not response:
            raise Exception(f"Obtained an empty response from {oauth_token_url}")  # noqa: E501

        self.refresh_token = response[oauth_constants.OauthPayloadKey.REFRESH_TOKEN.value]  # noqa: E501
        return response

    def create_access_token(self):
        """Create access token using refresh token."""
        if not self.refresh_token:
            raise Exception("Unable to find refresh token")

        payload = {
            oauth_constants.OauthPayloadKey.GRANT_TYPE.value: oauth_constants.GrantType.REFRESH_TOKEN.value,  # noqa: E501
            oauth_constants.OauthPayloadKey.REFRESH_TOKEN.value: self.refresh_token  # noqa: E501
        }
        oauth_token_url = self._get_oauth_token_url()
        response = self.do_request(
            method=RequestMethod.POST,
            resource_url_absolute_path=oauth_token_url,
            content_type="application/x-www-form-urlencoded",
            payload=payload)

        if not response:
            raise Exception(f"Obtained an empty response from {oauth_token_url}")  # noqa: E501

        return response['access_token']
