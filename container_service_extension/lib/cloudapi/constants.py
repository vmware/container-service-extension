# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum

CLOUDAPI_URN_PREFIX = 'urn:vcloud'


class CloudApiVersion(str, Enum):
    VERSION_1_0_0 = '1.0.0'
    VERSION_2_0_0 = '2.0.0'


class CloudApiResource(str, Enum):
    """Keys that are used to get the cloudapi resource names."""

    VDC_COMPUTE_POLICIES = 'vdcComputePolicies'
    PVDC_COMPUTE_POLICIES = 'pvdcComputePolicies'
    EXTENSION_UI = 'extensions/ui'
    INTERFACES = 'interfaces'
    BEHAVIOR_INVOCATION = 'invocations'
    BEHAVIORS = 'behaviors'
    BEHAVIOR_ACLS = 'behaviorAccessControls'
    ENTITY_TYPES = 'entityTypes'
    ENTITY_TYPES_TOKEN = 'types'
    ENTITIES = 'entities'
    ENTITY_RESOLVE = 'resolve'
    RIGHT_BUNDLES = 'rightsBundles'
    ACL = 'accessControls'
    USERS = 'users'
    VDCS = 'vdcs'
    EDGE_GATEWAYS = 'edgeGateways'
    EXTERNAL_NETWORKS = 'externalNetworks'
    USED_IP_ADDRESSES = 'usedIpAddresses'
    ORG_VDC_NETWORKS = 'orgVdcNetworks'


class ResponseKeys(str, Enum):
    LINK = 'link'
    REL = 'rel'
    URL = 'url'
