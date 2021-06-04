# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

import container_service_extension.def_.utils as def_utils

# Client environment variables
ENV_CSE_CLIENT_WIRE_LOGGING = 'CSE_CLIENT_WIRE_LOGGING'
ENV_CSE_TKG_PLUS_ENABLED = 'CSE_TKG_PLUS_ENABLED'
ENV_CSE_TKG_M_ENABLED = 'CSE_TKG_M_ENABLED'

TKG_ENTITY_TYPE_ID = def_utils.generate_entity_type_id(
    def_utils.DEF_VMWARE_VENDOR,
    def_utils.TKG_ENTITY_TYPE_NSS,
    def_utils.TKG_ENTITY_TYPE_VERSION)


# if cse_server_running key is set to false in profiles.yaml, CSE CLI can
# only be used to work with TKG clusters. This key is set when the first call
# to CSE server is made. If CSE server starts running after the first call
# fails, a re-login is needed to reset the key in profiles.yaml
CSE_SERVER_RUNNING = 'cse_server_running'


TKG_RESPONSE_MESSAGES_BY_STATUS_CODE = {
    403: "User doesn't have required rights to perform the operation",
    500: "Unexpected error occurred"
}


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
class TKGEntityFilterKey(str, Enum):
    """Keys to filter TKG cluster entities in CSE CLI.

    Below Keys are commonly used filters. An entity can be filtered by any of
    its properties.
    """

    CLUSTER_NAME = 'entity.metadata.name'
    VDC_NAME = 'entity.metadata.virtualDataCenterName'
    ORG_NAME = 'org.name'


@unique
class TKGRequestHeaderKey(str, Enum):
    """Header keys for tkgCluster requests."""

    AUTHORIZATION = 'Authorization'
    X_VCLOUD_AUTHORIZATION = 'x-vcloud-authorization'
    ACCEPT = 'Accept'
    X_VMWARE_VCLOUD_TENANT_CONTEXT = "x-vmware-vcloud-tenant-context"
