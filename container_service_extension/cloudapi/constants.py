# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum

CLOUDAPI_DEFAULT_VERSION = '1.0.0'
COMPUTE_POLICY_NAME_PREFIX = 'cse----'


class CloudApiResource(str, Enum):
    """Keys that are used to get the cloudapi resource names."""

    VDC_COMPUTE_POLICIES = 'vdcComputePolicies'


class RelationType(Enum):
    """Keys to use to find the link relation type."""

    # TODO should be moved to pyvcloud
    OPEN_API = 'openapi'


class EntityType(str, Enum):
    """Media type."""

    # TODO should be moved to pyvcloud
    APPLICATION_JSON = 'application/json'
