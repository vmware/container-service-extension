# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Constants used for interaction with defined entity framework."""

from enum import Enum
from enum import unique

import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501

CLUSTER_ACL_LIST_FIELDS = [shared_constants.AccessControlKey.ACCESS_LEVEL_ID,
                           shared_constants.AccessControlKey.MEMBER_ID,
                           shared_constants.AccessControlKey.USERNAME]

# ACL Path
ACTION_CONTROL_ACCESS_PATH = '/action/controlAccess/'

DEF_CSE_VENDOR = 'cse'
DEF_VMWARE_VENDOR = 'vmware'
DEF_VMWARE_INTERFACE_NSS = 'k8s'
DEF_VMWARE_INTERFACE_VERSION = '1.0.0'
DEF_VMWARE_INTERFACE_NAME = 'Kubernetes'
DEF_TKG_ENTITY_TYPE_NSS = 'tkgcluster'
DEF_TKG_ENTITY_TYPE_VERSION = '1.0.0'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_NATIVE_ENTITY_TYPE_NAME = 'nativeClusterEntityType'
DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE = \
    f'{DEF_CSE_VENDOR}:{DEF_NATIVE_ENTITY_TYPE_NSS} Entitlement'

DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0
DEF_SCHEMA_DIRECTORY = 'cse_def_schema'
DEF_ENTITY_TYPE_SCHEMA_FILE = 'schema.json'
DEF_ERROR_MESSAGE_KEY = 'message'
DEF_RESOLVED_STATE = 'RESOLVED'
TKG_ENTITY_TYPE_NSS = 'tkgcluster'
TKG_ENTITY_TYPE_VERSION = '1.0.0'


@unique
class DefKey(str, Enum):
    INTERFACE_VENDOR = 'interface_vendor'
    INTERFACE_NSS = 'interface_nss'
    INTERFACE_VERSION = 'interface_version'
    INTERFACE_NAME = 'interface_name'
    ENTITY_TYPE_VENDOR = 'entity_type_vendor'
    ENTITY_TYPE_NAME = 'entity_type_name'
    ENTITY_TYPE_NSS = 'entity_type_nss'
    ENTITY_TYPE_VERSION = 'entity_type_version'
    ENTITY_TYPE_SCHEMA_VERSION = 'schema_version'


# Defines the RDE versions CSE makes use of.
# Different RDE versions may be used as CSE
# is compatible with multiple VCD API versions.
@unique
class RDESchemaVersions(str, Enum):
    RDE_1_X = '1.0.0'
    RDE_2_X = '2.0.0'


MAP_API_VERSION_TO_KEYS = {
    35.0: {
        DefKey.INTERFACE_VENDOR: DEF_VMWARE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_VMWARE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_VMWARE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_VMWARE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_VENDOR: DEF_CSE_VENDOR,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME,
        DefKey.ENTITY_TYPE_SCHEMA_VERSION: 'api_v35',
    },
    36.0: {
        DefKey.INTERFACE_VENDOR: DEF_VMWARE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_VMWARE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_VMWARE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_VMWARE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_VENDOR: DEF_CSE_VENDOR,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME,
        DefKey.ENTITY_TYPE_SCHEMA_VERSION: 'api_v35',
    }
}


MAP_RDE_VERSION_TO_KEYS = {
    RDESchemaVersions.RDE_1_X: {
        DefKey.INTERFACE_VENDOR: DEF_VMWARE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_VMWARE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_VMWARE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_VMWARE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_VENDOR: DEF_CSE_VENDOR,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME
    },
    RDESchemaVersions.RDE_2_X: {
        DefKey.INTERFACE_VENDOR: DEF_VMWARE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_VMWARE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_VMWARE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_VMWARE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_VENDOR: DEF_CSE_VENDOR,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME
    }
}

# Dictionary indicating RDE version to use
# for the VCD API version
# Based on the VCD-version CSE server is configured with,
# CSE server dynamically determines the RDE-version-to-use at runtime.
# Below dictionary essentially answers this question:
# "When CSE is configured with VCD of a given api-version, what is the
# compatible RDE-version CSE-server must use on that VCD?"
# Key represents the VCD api-version CSE is configured with.
# Value represents the RDE-version CSE-server must use for that VCD
#   environment.
# This map must be carefully updated for every major/minor/patch version
# increments of RDE for each official CSE release. Below are few examples on
#  how this map could be updated.
# NOTE: The RDE version used by the VCD API version can be different in other
#   CSE releases.
# Example -
# Mapping for CSE 3.1:
# MAP_VCD_API_VERSION_TO_RDE_SCHEMA_VERSION = {
#     35.0: 1.0.0,
#     36.0: 2.0.0
# }
# If CSE 3.2 introduces Minor version bump in RDE (i.e 2.1) and is released
#   alongside vCD 10.4 (API Version 37), mapping would be -
# MAP_VCD_API_VERSION_TO_RDE_SCHEMA_VERSION = {
# 35.0: 1.0.0,
# 36.0: 2.1.0 (Note the RDE version change),
# 37.0: 2.1.0 (Newly introduced RDE),
# }
# If CSE 3.2 introduces Major version bump in RDE (i.e 3.0) and is released
#   alongside vCD 10.4 (API version 37), mapping would be -
# MAP_VCD_API_VERSION_TO_RDE_SCHEMA_VERSION = {
# 35.0: 1.0.0,
# 36.0: 2.0.0,
# 37.0: 3.0.0 (Newly introduced RDE)
# }
MAP_VCD_API_VERSION_TO_RDE_VERSION = {
    35.0: RDESchemaVersions.RDE_1_X.value,
    36.0: RDESchemaVersions.RDE_2_X.value
}


class ClusterEntityFilterKey(Enum):
    """Keys to filter cluster entities in CSE (or) vCD.

    Below Keys are commonly used filters. An entity can be filtered by any of
    its properties.

    Usage examples:
    ..api/cse/internal/clusters?entity.kind=native
    ..api/cse/internal/clusters?entity.metadata.org_name=org1
    ..cloudapi/1.0.0/entities?filter=entity.metadata.org_name==org1
    """

    # TODO(DEF) CLI can leverage this enum for the filter implementation.
    CLUSTER_NAME = 'name'
    ORG_NAME = 'entity.metadata.org_name'
    OVDC_NAME = 'entity.metadata.ovdc_name'
    KIND = 'entity.kind'
    K8_DISTRIBUTION = 'entity.spec.k8_distribution.template_name'
    STATE = 'state'
    PHASE = 'entity.status.phase'
