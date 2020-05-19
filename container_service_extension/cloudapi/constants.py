# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum

CLOUDAPI_VERSION_1_0_0 = '1.0.0'
CSE_COMPUTE_POLICY_PREFIX = 'cse----'

# Defined Entity Framework related constants
DEF_CSE_VENDOR = 'cse'
DEF_NATIVE_INTERFACE_NSS = 'native'
DEF_NATIVE_INTERFACE_VERSION = '1.0.0'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'


class CloudApiResource(str, Enum):
    """Keys that are used to get the cloudapi resource names."""

    VDC_COMPUTE_POLICIES = 'vdcComputePolicies'
    EXTENSION_UI = 'extensions/ui'
    INTERFACES = 'interfaces'
    ENTITY_TYPES = 'entityTypes'
    ENTITIES = 'entities'
    ENTITY_RESOLVE = 'resolve'
