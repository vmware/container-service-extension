# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

ERROR_DESCRIPTION_KEY = "description"
ERROR_MESSAGE_KEY = "message"
ERROR_REASON_KEY = "reason"
ERROR_STACKTRACE_KEY = "stacktrace"
UNKNOWN_ERROR_MESSAGE = "Unknown error. Please contact your system " \
                        "administrator"


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
    CLUSTER_NAME = 'cluster_name'
    MB_MEMORY = 'mb_memory'
    NUM_CPU = 'num_cpu'
    NETWORK_NAME = 'network_name'
    STORAGE_PROFILE_NAME = 'storage_profile_name'
    NUM_WORKERS = 'num_workers'
    TEMPLATE_NAME = 'template_name'
    NODE_NAME = 'node_name'
    ENABLE_NFS = 'enable_nfs'
    NODE_NAMES_LIST = 'node_names'
    SSH_KEY_FILEPATH = 'ssh_key_filepath'
    DISABLE_ROLLBACK = 'disable_rollback'
    FORCE_DELETE = 'force_delete'

    # keys related to ovdc requests
    K8S_PROVIDER = 'k8s_provider'
    OVDC_ID = 'ovdc_id'
    PKS_CLUSTER_DOMAIN = 'pks_cluster_domain'
    PKS_PLAN_NAME = 'pks_plan_name'
    GET_PKS_PLANS = 'get_pks_plans'

    # keys related to system requests
    SERVER_ACTION = 'server_action'
