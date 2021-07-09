# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Constants shared between the client CLI and the server."""

from enum import Enum
from enum import unique


# vCD API versions supported by CSE
SUPPORTED_VCD_API_VERSIONS = ['33.0', '34.0', '35.0', '36.0']
API_VERSION_37_ALPHA = '37.0.0-alpha'

CSE_URL_FRAGMENT = 'cse'
PKS_URL_FRAGMENT = 'pks'
CSE_3_0_URL_FRAGMENT = '3.0'
CLUSTER_URL_FRAGMENT = 'cluster'
ACL_URL_FRAGMENT = 'acl'

ERROR_DESCRIPTION_KEY = "error description"
ERROR_MINOR_CODE_KEY = "minor error code"
UNKNOWN_ERROR_MESSAGE = "Unknown error. Please contact your System " \
                        "Administrator"

RESPONSE_MESSAGE_KEY = "message"
CSE_SERVER_API_VERSION = "cse_server_api_version"
CSE_SERVER_SUPPORTED_API_VERSIONS = "cse_server_supported_api_versions"
CSE_SERVER_LEGACY_MODE = "cse_server_running_in_legacy_mode"


class ClusterEntityKind(Enum):
    NATIVE = 'native'
    TKG_S = 'TanzuKubernetesCluster'
    TKG_PLUS = 'TKG+'
    TKG_M = 'TKGm'


# Cluster runtimes and placement policies
NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME = 'native'
TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME = 'tkgplus'
TKG_M_CLUSTER_RUNTIME_INTERNAL_NAME = 'tkgm'
CLUSTER_RUNTIME_PLACEMENT_POLICIES = [NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME,
                                      TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME]


RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP = {
    ClusterEntityKind.NATIVE.value: NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME,
    ClusterEntityKind.TKG_PLUS.value: TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME
}


RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP = {
    NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME: ClusterEntityKind.NATIVE.value,
    TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME: ClusterEntityKind.TKG_PLUS.value
}

# CSE Server Busy string
CSE_SERVER_BUSY_KEY = 'CSE Server Busy'


# Access control constants
# Note: these constants are only applicable for API version >= 35
READ_ONLY = 'ReadOnly'
READ_WRITE = 'ReadWrite'
FULL_CONTROL = 'FullControl'
URN_VCLOUD_ACCESS = 'urn:vcloud:accessLevel'
USER_URN_PREFIX = 'urn:vcloud:user:'
READ_ONLY_ACCESS_LEVEL_ID = f'{URN_VCLOUD_ACCESS}:{READ_ONLY}'
READ_WRITE_ACCESS_LEVEL_ID = f'{URN_VCLOUD_ACCESS}:{READ_WRITE}'
FULL_CONTROL_ACCESS_LEVEL_ID = f'{URN_VCLOUD_ACCESS}:{FULL_CONTROL}'
MEMBERSHIP_GRANT_TYPE = 'MembershipAccessControlGrant'
ACCESS_LEVEL_TYPE_TO_ID = {
    READ_ONLY.lower(): READ_ONLY_ACCESS_LEVEL_ID,
    READ_WRITE.lower(): READ_WRITE_ACCESS_LEVEL_ID,
    FULL_CONTROL.lower(): FULL_CONTROL_ACCESS_LEVEL_ID
}


# CSE Pagination default values
CSE_PAGINATION_FIRST_PAGE_NUMBER = 1
CSE_PAGINATION_DEFAULT_PAGE_SIZE = 25

# System org constants
SYSTEM_ORG_NAME = 'system'
SYSTEM_USER_GENERIC_NAME = 'system user'


@unique
class ServerAction(str, Enum):
    DISABLE = 'disable'
    ENABLE = 'enable'
    STOP = 'stop'


@unique
class RequestMethod(str, Enum):
    GET = 'GET'
    HEAD = 'HEAD'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    CONNECT = 'CONNECT'
    OPTIONS = 'OPTIONS'
    TRACE = 'TRACE'
    PATCH = 'PATCH'


@unique
class ComputePolicyAction(str, Enum):
    ADD = 'add'
    REMOVE = 'remove'


# TODO need mapping from request key to proper vcd construct error message
@unique
class RequestKey(str, Enum):
    """Keys that can exist in the request data that client sends to server.

    Request data should only ever be accessed by request handler functions,
    and when request data is recorded or entered, the dictionary should
    be accessed using this enum instead of a bare string.

    Example:
    - When inserting request data client-side:
        data = {RequestKey.ORG_NAME = 'my org'}
    - When indexing into request data server-side:
        org_name = request_data.get(RequestKey.ORG_NAME)
    """

    # common/multiple request keys
    ORG_NAME = 'org_name'
    OVDC_NAME = 'ovdc_name'
    INPUT_SPEC = 'spec_body'
    QUERY_PARAMS = 'query_filter'

    # keys related to cluster requests
    CLUSTER_NAME = 'cluster_name'
    CLUSTER_ID = 'cluster_id'
    MB_MEMORY = 'mb_memory'
    NUM_CPU = 'num_cpu'
    NETWORK_NAME = 'network_name'
    STORAGE_PROFILE_NAME = 'storage_profile_name'
    NUM_WORKERS = 'num_workers'
    TEMPLATE_NAME = 'template_name'
    TEMPLATE_REVISION = 'template_revision'
    NODE_NAME = 'node_name'
    ENABLE_NFS = 'enable_nfs'
    NODE_NAMES_LIST = 'node_names'
    SSH_KEY = 'ssh_key'
    ROLLBACK = 'rollback'

    # keys related to ovdc requests
    K8S_PROVIDER = 'k8s_provider'
    OVDC_ID = 'ovdc_id'
    PKS_CLUSTER_DOMAIN = 'pks_cluster_domain'
    PKS_PLAN_NAME = 'pks_plan_name'
    LIST_PKS_PLANS = 'list_pks_plans'
    COMPUTE_POLICY_ACTION = 'action'
    COMPUTE_POLICY_NAME = 'compute_policy_name'
    REMOVE_COMPUTE_POLICY_FROM_VMS = 'remove_compute_policy_from_vms'

    # keys related to system requests
    SERVER_ACTION = 'server_action'

    # keys that are only used internally at server side
    PKS_EXT_HOST = 'pks_ext_host'


@unique
class PaginationKey(str, Enum):
    PAGE_NUMBER = 'page'
    PAGE_SIZE = 'pageSize'
    PAGE_COUNT = 'pageCount'
    NEXT_PAGE_URI = 'nextPageUri'
    PREV_PAGE_URI = 'previousPageUri'
    RESULT_TOTAL = 'resultTotal'
    VALUES = 'values'
    CURSOR = 'cursor'


@unique
class AccessControlKey(str, Enum):
    """Keys for access control requests."""

    GRANT_TYPE = 'grantType'
    ACCESS_LEVEL_ID = 'accessLevelId'
    MEMBER_ID = 'memberId'
    NAME = 'name'
    ACCESS_LEVEL = 'accessLevel'
    ID = 'id'
    HREF = 'href'
    SUBJECT = 'subject'
    USERNAME = 'username'


DEF_ENTITY_ACCESS_CONTROL_KEYS = [AccessControlKey.GRANT_TYPE,
                                  AccessControlKey.ACCESS_LEVEL_ID,
                                  AccessControlKey.MEMBER_ID]


@unique
class ClusterAclKey(str, Enum):
    ACCESS_SETTING = 'accessSetting'
    UPDATE_ACL_ENTRIES = 'update_acl_entries'


@unique
class ClusterDetailsKey(str, Enum):
    CLUSTER_ID = 'cluster_id'
    CNI_NAME = 'cni'
    CNI_VERSION = 'cni_version'
    CSE_VERSION = 'cse_version'
    DOCKER_VERSION = 'docker_version'
    KUBERNETES_RUNTIME = 'kubernetes'
    KUBERNETES_VERSION = 'kubernetes_version'
    LEADER_ENDPOINT = 'leader_endpoint'
    CONTROL_PLANE_NODE_LIST = 'master_nodes'
    CLUSTER_NAME = 'name'
    NETWORK_NAME = 'network_name'
    NFS_NODE_LIST = 'nfs_nodes'
    WORKER_NODE_LIST = 'nodes'
    VM_COUNT = 'number_of_vms'
    ORG_NAME = 'org_name'
    ORG_HREF = 'org_href'
    OS = 'os'
    OWNER_NAME = 'owner_name'
    STATUS = 'status'
    STORAGE_PROFILE_NAME = 'storage_profile_name'
    TEMPLATE_NAME = 'template_name'
    TEMPLATE_REVISION = 'template_revision'
    VAPP_HREF = 'vapp_href'
    VAPP_ID = 'vapp_id'
    VDC_HREF = 'vdc_href'
    VDC_ID = 'vdc_id'
    VDC_NAME = 'vdc_name'


@unique
class HttpResponseHeader(str, Enum):
    LOCATION = 'Location'
    X_VMWARE_VCLOUD_TASK_LOCATION = 'X-VMWARE-VCLOUD-TASK-LOCATION'
