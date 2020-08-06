# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

import container_service_extension.def_.utils as def_utils

ENV_CSE_CLIENT_WIRE_LOGGING = 'CSE_CLIENT_WIRE_LOGGING'
TKG_ENTITY_TYPE_ID = def_utils.generate_entity_type_id(
    def_utils.DEF_VMWARE_VENDOR,
    def_utils.TKG_ENTITY_TYPE_NSS,
    def_utils.TKG_ENTITY_TYPE_VERSION)

TKG_CLUSTER_RUNTIME = 'TkgCluster'


@unique
class CLIOutputKey(str, Enum):
    """Keys for displaying Cluster list output."""
    CLUSTER_NAME = "Name"
    VDC = "VDC"
    ORG = "Org"
    K8S_RUNTIME = "K8s Runtime"
    K8S_VERSION = "K8s Version"
    STATUS = "Status"
    OWNER = "Owner"


@unique
class TKGClusterEntityFilterKey(str, Enum):
    """Keys to filter TKG cluster entities in CSE CLI.

    Below Keys are commonly used filters. An entity can be filtered by any of
    its properties.
    """

    CLUSTER_NAME = 'entity.metadata.name'
    VDC_NAME = 'entity.metadata.virtualDataCenterName'
    ORG_NAME = 'org.name'


@unique
class TKGClusterMetadataKey(str, Enum):
    """Metadata keys for TKG cluster entities."""
    OVDC_NAME = 'virtualDataCenterName'
    CLUSTER_NAME = 'name'
    PLACEMENT_POLICY = 'placementPolicy'


@unique
class NativeClusterMetadataKey(str, Enum):
    """Metadata keys for Native cluster entities."""
    OVDC_NAME = 'ovdc_name'
    CLUSTER_NAME = 'cluster_name'
    ORG_NAME = 'org_name'
