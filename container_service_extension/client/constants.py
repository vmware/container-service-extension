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

# CLI Profile key
CSE_SERVER_RUNNING = 'cse_server_running'


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
