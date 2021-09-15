# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import logging
from urllib.parse import urlparse

import pyvcloud.vcd.client as vcd_client

from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
from container_service_extension.lib.cloudapi import cloudapi_client
from container_service_extension.logging.logger import NULL_LOGGER

OAUTH_PROVIDER_URL_FRAGMENT = "/provider"
OAUTH_TENANT_URL_FRAGMENT = "/tenant"
BASE_OAUTH_ENDPOINT_FRAGMENT = "/oauth"
REGISTER_CLIENT_ENDPOINT_FRAGMENT = "/register"
OAUTH_TOKEN_ENDPOINT_FRAGMENT = "/token"
GRANT_TYPE_JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
GRANT_TYPE_REFRESH_TOKEN = "refresh_token"


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
            is_jwt_token=True,
            api_version=None,
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
            f"{self._host_url}{BASE_OAUTH_ENDPOINT_FRAGMENT}"
        # /oauth endpoint is tenanted. which means, system administrators can
        # access the endpoint using /oauth/provider/register while tenant users
        # can access the endpoint using /oauth/tenant/{orgId}/register
        if self.vcd_api_client.is_sysadmin():
            register_client_url += \
                f"{OAUTH_PROVIDER_URL_FRAGMENT}{REGISTER_CLIENT_ENDPOINT_FRAGMENT}"  # noqa: E501
        else:
            logged_in_org = self.vcd_api_client.get_org()
            org_name = logged_in_org.get('name')
            register_client_url += \
                f"{OAUTH_TENANT_URL_FRAGMENT}/{org_name}{REGISTER_CLIENT_ENDPOINT_FRAGMENT}"  # noqa: E501
        return register_client_url

    def _get_oauth_token_url(self):
        oauth_token_url = \
            f"{self._host_url}{BASE_OAUTH_ENDPOINT_FRAGMENT}"
        # /oauth endpoint is tenanted. which means, system administrators can
        # access the endpoint using /oauth/provider/token while tenant users
        # can access the endpoint using /oauth/tenant/{orgId}/token
        if self.vcd_api_client.is_sysadmin():
            oauth_token_url += \
                f"{OAUTH_PROVIDER_URL_FRAGMENT}{OAUTH_TOKEN_ENDPOINT_FRAGMENT}"
        else:
            logged_in_org = self.vcd_api_client.get_org()
            org_name = logged_in_org.get('name')
            oauth_token_url += \
                f"{OAUTH_TENANT_URL_FRAGMENT}/{org_name}{OAUTH_TOKEN_ENDPOINT_FRAGMENT}"  # noqa: E501
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
        self.oauth_client_id = response['client_id']

        return response

    def create_refresh_token(self):
        """Create a refresh token using client_id and jwt token.

        This method can only be executed once per client.
        """
        payload = {
            "grant_type": GRANT_TYPE_JWT_BEARER,
            "client_id": self.oauth_client_id,
            "assertion": self.vcd_api_client.get_access_token()
        }
        oauth_token_url = self._get_oauth_token_url()
        response = self.do_request(
            method=RequestMethod.POST,
            resource_url_absolute_path=oauth_token_url,
            content_type="application/x-www-form-urlencoded",
            payload=payload)

        if not response:
            raise Exception(f"Obtained an empty response from {oauth_token_url}")  # noqa: E501

        self.refresh_token = response['refresh_token']
        return response

    def create_access_token(self):
        """Create access token using refresh token."""
        if not self.refresh_token:
            raise Exception("Unable to find refresh token")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
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
