# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum

CLOUDAPI_VERSION_1_0_0 = '1.0.0'
CSE_COMPUTE_POLICY_PREFIX = 'cse----'


class CloudApiResource(str, Enum):
    """Keys that are used to get the cloudapi resource names."""

    VDC_COMPUTE_POLICIES = 'vdcComputePolicies'
    PVDC_COMPUTE_POLICIES = 'pvdcComputePolicies'
    EXTENSION_UI = 'extensions/ui'
    INTERFACES = 'interfaces'
    ENTITY_TYPES = 'entityTypes'
    ENTITIES = 'entities'
    ENTITY_RESOLVE = 'resolve'
