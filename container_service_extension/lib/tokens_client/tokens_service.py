# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.lib.cloudapi.constants import CloudApiResource
from container_service_extension.lib.cloudapi.constants import CloudApiVersion


class TokensService:
    """Cloudapi Client for /cloudapi/1.0.0/tokens endpoint."""

    def __init__(self, cloudapi_client: CloudApiClient):
        self._cloudapi_client = cloudapi_client

    def get_refresh_token_by_oauth_client_name(self, oauth_client_name: str):
        """Get refresh token information by oauth client name."""
        # NOTE: Oauth client name is uniqe to a refresh token
        if not oauth_client_name:
            raise ValueError("No oauth_client_name provided.")
        filters = {
            "type": "REFRESH",
            "name": oauth_client_name
        }
        filter_string = utils.construct_filter_string(filters)
        response = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0.value,
            resource_url_relative_path=f"{CloudApiResource.TOKENS.value}?filter={filter_string}")  # noqa: E501
        if not response:
            raise Exception(f"Failed to get refresh token information for client {oauth_client_name}")  # noqa: E501
        if len(response['values']) == 0:
            raise Exception("Cannot find refresh token for "
                            f"OAuth client {oauth_client_name}")
        return response['values'][0]

    def delete_refresh_token_by_oauth_client_name(self, oauth_client_name: str):  # noqa: E501
        """Delete a refresh token by oauth client name."""
        refresh_token = self.get_refresh_token_by_oauth_client_name(oauth_client_name)  # noqa: E501
        self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0.value,
            resource_url_relative_path=f"{CloudApiResource.TOKENS.value}/{refresh_token['id']}",  # noqa: E501
        )
