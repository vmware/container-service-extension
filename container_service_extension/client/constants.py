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

TKG_CLUSTER_RUNTIME = 'TKG'


@unique
class CLIOutputKey(str, Enum):
    # Output keys for cluster list
    CLUSTER_NAME = "name"
    VDC = "VDC"
    ORG = "Org"
    K8S_RUNTIME = "K8s Runtime"
    K8S_VERSION = "K8s Version"
    STATUS = "Status"
    OWNER = "Owner"
