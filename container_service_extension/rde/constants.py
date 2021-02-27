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
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0
DEF_SCHEMA_DIRECTORY = 'cse_def_schema'
DEF_ENTITY_TYPE_SCHEMA_FILE = 'schema.json'
DEF_ERROR_MESSAGE_KEY = 'message'
DEF_RESOLVED_STATE = 'RESOLVED'
TKG_ENTITY_TYPE_NSS = 'tkgcluster'


@unique
class Vendor(str, Enum):
    CSE = 'cse'
    VMWARE = 'vmware'


@unique
class Nss(str, Enum):
    KUBERNETES = 'k8s'
    NATIVE_ClUSTER = 'nativeCluster'
    TKG = 'tkgcluster'


DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE = \
    f'{Vendor.CSE.value}:{Nss.NATIVE_ClUSTER.value} Entitlement'


# Defines the RDE versions CSE makes use of.
# Different RDE versions may be used as CSE
# is compatible with multiple VCD API versions.
# NOTE: Value for RDESchemaVersions Enum will be updated on
# each minor version RDE update.
# NOTE: New Entry for RDESchemaVersions will be added on
# each major version RDE change.
@unique
class RDESchemaVersions(str, Enum):
    RDE_1_X = '1.0.0'
    RDE_2_X = '2.0.0'


class CommonInterfaceMetadata(str, Enum):
    VENDOR = Vendor.VMWARE.value
    NSS = Nss.KUBERNETES.value
    VERSION = '1.0.0'
    NAME = "Kubernetes"

    @classmethod
    def get_id(cls):
        return f"{DEF_INTERFACE_ID_PREFIX}:{cls.VENDOR}:{cls.NSS}:{cls.VERSION}"  # noqa: E501


class NativeEntityTypeMetadata_1_0_0(str, Enum):
    VENDOR = Vendor.CSE.value
    NSS = DEF_NATIVE_ENTITY_TYPE_NSS
    VERSION = '1.0.0'
    SCHEMA_FILE = 'schema_1_0_0.json'
    NAME = 'nativeClusterEntityType'

    @classmethod
    def get_id(cls):
        return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{cls.VENDOR}:{cls.NSS}:{cls.VERSION}"  # noqa: E501


class NativeEntityTypeMetadata_2_0_0(str, Enum):
    VENDOR = Vendor.CSE.value
    NSS = DEF_NATIVE_ENTITY_TYPE_NSS
    VERSION = '2.0.0'
    SCHEMA_FILE = 'schema_2_0_0.json'
    NAME = 'nativeClusterEntityType'

    @classmethod
    def get_id(cls):
        return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{cls.VENDOR}:{cls.NSS}:{cls.VERSION}"  # noqa: E501


class TKGEntityTypeMetadata_1_0_0(str, Enum):
    VENDOR = Vendor.VMWARE.value
    NSS = TKG_ENTITY_TYPE_NSS
    VERSION = '1.0.0'
    NAME = "TKG Cluster"

    @classmethod
    def get_id(cls):
        return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{cls.VENDOR}:{cls.NSS}:{cls.VERSION}"  # noqa: E501


@unique
class RDEMetadataKey(str, Enum):
    ENTITY_TYPE_METADATA = 'entity_type_metadata'
    INTERFACES_METADATA_LIST = "interfaces_metadata_list"


MAP_RDE_VERSION_TO_ITS_METADATA = {
    RDESchemaVersions.RDE_1_X: {
        RDEMetadataKey.ENTITY_TYPE_METADATA: NativeEntityTypeMetadata_1_0_0,
        RDEMetadataKey.INTERFACES_METADATA_LIST: [CommonInterfaceMetadata]
    },
    RDESchemaVersions.RDE_2_X: {
        RDEMetadataKey.ENTITY_TYPE_METADATA: NativeEntityTypeMetadata_2_0_0,
        RDEMetadataKey.INTERFACES_METADATA_LIST: [CommonInterfaceMetadata]
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
