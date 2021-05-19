# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from enum import Enum
from enum import unique


CSE_URL_FRAGMENT = 'cse'
PKS_URL_FRAGMENT = 'pks'
CSE_3_0_URL_FRAGMENT = '3.0'

ERROR_DESCRIPTION_KEY = "error description"
ERROR_MINOR_CODE_KEY = "minor error code"
UNKNOWN_ERROR_MESSAGE = "Unknown error. Please contact your System " \
                        "Administrator"

RESPONSE_MESSAGE_KEY = "message"
CSE_SERVER_API_VERSION = 'cse_server_api_version'


class ClusterEntityKind(Enum):
    NATIVE = 'native'
    TKG = 'TanzuKubernetesCluster'
    TKG_PLUS = 'TKG+'
    TKGM = 'TKGm'


NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME = 'native'
TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME = 'tkgplus'
TKGM_CLUSTER_RUNTIME_INTERNAL_NAME = 'tkgm'
CLUSTER_RUNTIME_PLACEMENT_POLICIES = [NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME,
                                      TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME,
                                      TKGM_CLUSTER_RUNTIME_INTERNAL_NAME]

RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP = {
    ClusterEntityKind.NATIVE.value: NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME,
    ClusterEntityKind.TKG_PLUS.value: TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME,
    ClusterEntityKind.TKGM.value: TKGM_CLUSTER_RUNTIME_INTERNAL_NAME
}

RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP = {
    NATIVE_CLUSTER_RUNTIME_INTERNAL_NAME: ClusterEntityKind.NATIVE.value,
    TKG_PLUS_CLUSTER_RUNTIME_INTERNAL_NAME: ClusterEntityKind.TKG_PLUS.value,
    TKGM_CLUSTER_RUNTIME_INTERNAL_NAME: ClusterEntityKind.TKGM.value
}


# CSE Server Busy strings
CSE_SERVER_BUSY_KEY = 'CSE Server Busy'


# CSE Pagination default values
CSE_PAGINATION_FIRST_PAGE_NUMBER = 1
CSE_PAGINATION_DEFAULT_PAGE_SIZE = 25


@unique
class OperationType(str, Enum):
    NATIVE_CLUSTER = 'nativecluster'
    CLUSTER = 'cluster'
    NODE = 'node'
    OVDC = 'ovdc'
    SYSTEM = 'system'
    TEMPLATE = 'template'
    ORG_VDCS = 'orgvdc'


@unique
class ServerAction(str, Enum):
    DISABLE = 'disable'
    ENABLE = 'enable'
    STOP = 'stop'


@unique
class RequestMethod(str, Enum):
    GET = 'GET'
    POST = 'POST'
    DELETE = 'DELETE'
    PUT = 'PUT'


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

    # keys related to cluster requests
    V35_SPEC = 'spec_body'
    V35_QUERY = 'query_filter'
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
class DefEntityOperation(str, Enum):
    CREATE = 'CREATE'
    DELETE = 'DELETE'
    UPDATE = 'UPDATE'
    UPGRADE = 'UPGRADE'
    UNKNOWN = 'UNKNOWN'


@unique
class DefEntityOperationStatus(str, Enum):
    IN_PROGRESS = 'IN_PROGRESS'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    UNKNOWN = 'UNKNOWN'


@unique
class FlattenedClusterSpecKey(Enum):
    WORKERS_COUNT = 'workers.count'
    NFS_COUNT = 'nfs.count'
    TEMPLATE_NAME = 'k8_distribution.template_name'
    TEMPLATE_REVISION = 'k8_distribution.template_revision'
    EXPOSE = 'expose'


@dataclass
class DefEntityPhase:
    """Supports two ways of creation.

    1. DefEntityPhase(DefEntityOperation.CREATE, DefEntityOperationStatus.SUCCEEDED) # noqa: E501
    2. DefEntityPhase.from_phase('CREATE:SUCCEEDED')
    """

    operation: DefEntityOperation
    status: DefEntityOperationStatus

    def __str__(self):
        return f'{self.operation}:{self.status}'

    @classmethod
    def from_phase(cls, phase: str):
        """Return instance of DefEntityPhase.

        :param str phase: defined entity phase value. ex: "CREATE:SUCCEEDED"
        :return: DefEntityPhase
        :rtype: <class DefEntityPhase>
        """
        operation, status = phase.split(':')
        return cls(DefEntityOperation[operation], DefEntityOperationStatus[status])  # noqa: E501

    def is_operation_status_success(self) -> bool:
        try:
            return self.status == DefEntityOperationStatus.SUCCEEDED
        except Exception:
            return False

    def is_entity_busy(self) -> bool:
        return self.status == DefEntityOperationStatus.IN_PROGRESS
