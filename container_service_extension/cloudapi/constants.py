# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum

CLOUDAPI_ROOT = 'cloudapi'
CLOUDAPI_DEFAULT_VERSION = '1.0.0'
COMPUTE_POLICY_NAME_PREFIX = 'cse----'


class CloudApiResource(str, Enum):
    """Keys that are used to get the cloudapi resource names."""

    VDC_COMPUTE_POLICIES = 'vdcComputePolicies'
