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
DEF_ERROR_MESSAGE_KEY = 'message'
DEF_RESOLVED_STATE = 'RESOLVED'


@unique
class Vendor(str, Enum):
    CSE = 'cse'
    VMWARE = 'vmware'


@unique
class Nss(str, Enum):
    KUBERNETES = 'k8s'
    NATIVE_ClUSTER = 'nativeCluster'
    TKG = 'tkgcluster'


@unique
class SchemaFile(str, Enum):
    SCHEMA_1_0_0 = 'schema_1_0_0.json'
    SCHEMA_2_0_0 = 'schema_2_0_0.json'


DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE = \
    f'{Vendor.CSE.value}:{Nss.NATIVE_ClUSTER.value} Entitlement'


# Defines the RDE version CSE server uses at runtime.
# RDE version used by a given CSE version can differ based on the VCD
# environment it is configured with.
#
# Examples on how to updated this Enum:
#
# 1. An existing entry must be updated on a minor or patch version
# increment of RDE, example: RDE_2_X = '2.1.0'.
# 2. A New Entry must be added on each major version increment of
# RDE, example RDE_3_X = '3.0.0'
#
# Any updates to this enum may also require updating common_models.MAP_RDE_VERSION_TO_ITS_METADATA  # noqa: E501
@unique
class RuntimeRDEVersion(str, Enum):
    RDE_1_X = '1.0.0'
    RDE_2_X = '2.0.0'


@unique
class RDEVersion(str, Enum):
    RDE_1_0_0 = '1.0.0'
    RDE_2_0_0 = '2.0.0'


@unique
class RDEMetadataKey(str, Enum):
    ENTITY_TYPE = 'entity_type'
    INTERFACES = 'interfaces'
    INTERFACE_TO_BEHAVIORS_MAP = 'map_from_interface_id_to_behaviors'
    ENTITY_TYPE_TO_OVERRIDABLE_BEHAVIORS_MAP = 'map_from_entitytype_id_to_behaviors_to_override'  # noqa: E501
    BEHAVIOR_TO_ACL_MAP = 'map_from_behavior_id_to_behavior_acls'


# Dictionary indicating RDE version to use for a given VCD API version.
# Based on the VCD-version CSE server is configured with,
# CSE server dynamically determines the RDE-version-to-use at runtime.
# Below dictionary essentially answers this question:
# "When CSE is configured with VCD of a given api-version, what is the
# compatible RDE-version CSE-server must use on that VCD?"
#
# Key: represents the VCD api-version CSE is configured with.
# Value: represents the RDE-version CSE-server uses for that VCD environment.
#
# This map must be carefully updated for every major/minor/patch version
# increments of RDE for each official CSE release. Below are few examples on
#  how this map could be updated.
# NOTE: The RDE version used by the VCD API version can be different in other
#   CSE releases.

# Examples:
# Mapping for CSE 3.1:
# MAP_VCD_API_VERSION_TO_RDE_VERSION = {
#     35.0: 1.0.0,
#     36.0: 2.0.0
# }
#
# If CSE 3.2 introduces Minor version bump in RDE (i.e 2.1) and is released
#   alongside vCD 10.4 (API Version 37), mapping would become -
# MAP_VCD_API_VERSION_TO_RDE_SCHEMA_VERSION = {
# 35.0: 1.0.0,
# 36.0: 2.1.0 (Note the RDE version change),
# 37.0: 2.1.0 (Newly introduced RDE),
# }
#
# If CSE 3.2 introduces Major version bump in RDE (i.e 3.0) and is released
#   alongside vCD 10.4 (API version 37), mapping would be -
# MAP_VCD_API_VERSION_TO_RDE_SCHEMA_VERSION = {
# 35.0: 1.0.0,
# 36.0: 2.0.0,
# 37.0: 3.0.0 (Newly introduced RDE)
# }
MAP_VCD_API_VERSION_TO_RDE_VERSION = {
    35.0: RuntimeRDEVersion.RDE_1_X.value,
    36.0: RuntimeRDEVersion.RDE_2_X.value
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
