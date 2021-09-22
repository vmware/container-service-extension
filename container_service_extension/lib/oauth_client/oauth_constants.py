# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum, unique


OAUTH_PROVIDER_URL_FRAGMENT = "/provider"
OAUTH_TENANT_URL_FRAGMENT = "/tenant"
BASE_OAUTH_ENDPOINT_FRAGMENT = "/oauth"
REGISTER_CLIENT_ENDPOINT_FRAGMENT = "/register"
OAUTH_TOKEN_ENDPOINT_FRAGMENT = "/token"


@unique
class GrantType(str, Enum):
    JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
    REFRESH_TOKEN = "refresh_token"


@unique
class OauthPayloadKey(str, Enum):
    GRANT_TYPE = "grant_type"
    CLIENT_ID = "client_id"
    ASSERTION = "assertion"
    REFRESH_TOKEN = "refresh_token"
