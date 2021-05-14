# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
from urllib.parse import parse_qsl

from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
from container_service_extension.common.constants.shared_constants import RESPONSE_MESSAGE_KEY  # noqa: E501
from container_service_extension.common.constants.shared_constants import SUPPORTED_VCD_API_VERSIONS  # noqa: E501
from container_service_extension.exception.exception_handler import handle_exception  # noqa: E501
import container_service_extension.exception.exceptions as cse_exception
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.security.context.operation_context as ctx
import container_service_extension.server.request_handlers.cluster_handler as cluster_handler  # noqa: E501
import \
    container_service_extension.server.request_handlers.legacy.native_cluster_handler as native_cluster_handler  # noqa: E501
import container_service_extension.server.request_handlers.legacy.ovdc_handler as ovdc_handler  # noqa: E501
import container_service_extension.server.request_handlers.pks.pks_cluster_handler as pks_cluster_handler  # noqa: E501
import container_service_extension.server.request_handlers.pks.pks_ovdc_handler as pks_ovdc_handler  # noqa: E501
import container_service_extension.server.request_handlers.system_handler as system_handler  # noqa: E501
import container_service_extension.server.request_handlers.template_handler as template_handler  # noqa: E501 E501
import container_service_extension.server.request_handlers.v35.def_cluster_handler as v35_cluster_handler  # noqa: E501
import container_service_extension.server.request_handlers.v35.ovdc_handler as v35_ovdc_handler  # noqa: E501

DUAL_FORM_TOKENS = {
    'template': ('template', 'templates'),
    'templates': ('template', 'templates'),
    'cluster': ('cluster', 'clusters'),
    'clusters': ('cluster', 'clusters'),
    'ovdc': ('ovdc', 'ovdcs'),
    'ovdcs': ('ovdc', 'ovdcs'),
    'orgvdc': ('orgvdc', 'orgvdcs'),
    'orgvdcs': ('orgvdc', 'orgvdcs'),
    'nativecluster': ('nativecluster', 'nativeclusters'),
    'nativeclusters': ('nativecluster', 'nativeclusters'),
    'node': ('node', 'nodes'),
    'nodes': ('node', 'nodes')
}

# /system end points
SYSTEM_HANDLERS = [
    {
        'url': "cse/system",
        RequestMethod.GET: {
            ('*',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.SYSTEM_INFO,
                'handler': system_handler.system_info
            }
        },
        RequestMethod.PUT: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.SYSTEM_UPDATE,
                'handler': system_handler.system_update
            }
        }
    }
]

# /template end point
TEMPLATE_HANDLERS = [
    {
        'url': "cse/templates",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.TEMPLATE_LIST,
                'handler': template_handler.template_list
            }
        }
    }
]

# /pks end points
PKS_HANDLERS = [
    {
        'url': "pks/clusters",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.PKS_CLUSTER_LIST,
                'handler': pks_cluster_handler.cluster_list
            }
        },
        RequestMethod.POST: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.PKS_CLUSTER_CREATE,
                'handler': pks_cluster_handler.cluster_create
            }
        }
    },
    {
        'url': f"pks/cluster/${RequestKey.CLUSTER_NAME}",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.PKS_CLUSTER_INFO,
                'handler': pks_cluster_handler.cluster_info
            }
        },
        RequestMethod.PUT: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.PKS_CLUSTER_RESIZE,
                'handler': pks_cluster_handler.cluster_resize
            }
        },
        RequestMethod.DELETE: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.PKS_CLUSTER_DELETE,
                'handler': pks_cluster_handler.cluster_delete
            }
        },
    },
    {
        'url': f"pks/cluster/${RequestKey.CLUSTER_NAME}/config",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.PKS_CLUSTER_CONFIG,
                'handler': pks_cluster_handler.cluster_config
            }
        }
    },
    {
        'url': "pks/ovdcs",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['list_pks_plans'],
                'required_params': [],
                'operation': CseOperation.PKS_OVDC_LIST,
                'handler': pks_ovdc_handler.ovdc_list
            }
        }
    },
    {
        'url': "pks/orgvdcs",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': ['list_pks_plans', 'page', 'pageSize'],
                'required_params': [],
                'operation': CseOperation.PKS_ORG_VDC_LIST,
                'handler': pks_ovdc_handler.org_vdc_list
            }
        }
    },
    {
        'url': f"pks/ovdc/${RequestKey.OVDC_ID}",
        RequestMethod.GET: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.PKS_OVDC_INFO,
                'handler': pks_ovdc_handler.ovdc_info
            }
        },
        RequestMethod.PUT: {
            tuple(SUPPORTED_VCD_API_VERSIONS): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.PKS_OVDC_UPDATE,
                'handler': pks_ovdc_handler.ovdc_update
            }
        }
    }
]

# /cse/cluster end points
LEGACY_CLUSTER_HANDLERS = [
    {
        'url': "cse/clusters",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.CLUSTER_LIST,
                'handler': native_cluster_handler.cluster_list,
                'feature_flags': ['legacy_api']
            }
        },
        RequestMethod.POST: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.CLUSTER_CREATE,
                'handler': native_cluster_handler.cluster_create,
                'feature_flags': ['legacy_api']
            }
        }
    },
    {
        'url': f"cse/cluster/${RequestKey.CLUSTER_NAME}",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.CLUSTER_INFO,
                'handler': native_cluster_handler.cluster_info,
                'feature_flags': ['legacy_api']
            }
        },
        RequestMethod.PUT: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.CLUSTER_RESIZE,
                'handler': native_cluster_handler.cluster_resize,
                'feature_flags': ['legacy_api']
            },
        },
        RequestMethod.DELETE: {
            ('33.0', '34.0'): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.CLUSTER_DELETE,
                'handler': native_cluster_handler.cluster_delete,
                'feature_flags': ['legacy_api']
            }
        }
    },
    {
        'url': f"cse/cluster/${RequestKey.CLUSTER_NAME}/config",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.CLUSTER_CONFIG,
                'handler': native_cluster_handler.cluster_config,
                'feature_flags': ['legacy_api']
            }
        }
    },
    {
        'url': f"cse/cluster/${RequestKey.CLUSTER_NAME}/upgrade-plan",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['org_name', 'ovdc_name'],
                'required_params': [],
                'operation': CseOperation.CLUSTER_UPGRADE_PLAN,
                'handler': native_cluster_handler.cluster_upgrade_plan,
                'feature_flags': ['legacy_api']
            }
        }
    },
    {
        'url': f"cse/cluster/${RequestKey.CLUSTER_NAME}/action/upgrade",
        RequestMethod.POST: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.CLUSTER_UPGRADE,
                'handler': native_cluster_handler.cluster_upgrade,
                'feature_flags': ['legacy_api']
            }
        }
    }
]

# /cse/nativeclusters end points
LEGACY_NATIVE_CLUSTER_HANDLERS = [
    {
        'url': "cse/nativeclusters",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['org_name', 'ovdc_name', 'pageSize', 'page'],  # noqa: E501
                'required_params': [],
                'operation': CseOperation.NATIVE_CLUSTER_LIST,
                'handler': native_cluster_handler.native_cluster_list,
                'feature_flags': ['legacy_api']
            }
        },
    }
]

# /cse/nodes end points
LEGACY_NODE_HANDLERS = [
    {
        'url': "cse/nodes",
        RequestMethod.POST: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.NODE_CREATE,
                'handler': native_cluster_handler.node_create,
                'feature_flags': ['legacy_api']
            }
        },
        RequestMethod.DELETE: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.NODE_DELETE,
                'handler': native_cluster_handler.node_delete,
                'feature_flags': ['legacy_api']
            }
        },
    },
    {
        'url': f"cse/node/${RequestKey.NODE_NAME}",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['cluster_name', 'org_name', 'ovdc_name'],
                'required_params': ['cluster_name'],
                'operation': CseOperation.NODE_INFO,
                'handler': native_cluster_handler.node_info,
                'feature_flags': ['legacy_api']
            }
        },
    }
]

# /cse/ovdcs end points
LEGACY_OVDC_HANDLERS = [
    {
        'url': "cse/ovdcs",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.OVDC_LIST,
                'handler': ovdc_handler.ovdc_list,
                'feature_flags': ['legacy_api']
            }
        },
    },
    {
        'url': f"cse/ovdc/${RequestKey.OVDC_ID}",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.OVDC_INFO,
                'handler': ovdc_handler.ovdc_info,
                'feature_flags': ['legacy_api']
            }
        },
        RequestMethod.PUT: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.OVDC_UPDATE,
                'handler': ovdc_handler.ovdc_update,
                'feature_flags': ['legacy_api']
            }
        }
    },
    {
        'url': f"cse/ovdc/${RequestKey.OVDC_ID}/compute-policies",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.OVDC_COMPUTE_POLICY_LIST,
                'handler': ovdc_handler.ovdc_compute_policy_list,
                'feature_flags': ['legacy_api']
            }
        },
        RequestMethod.PUT: {
            ('33.0', '34.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.OVDC_COMPUTE_POLICY_UPDATE,
                'handler': ovdc_handler.ovdc_compute_policy_update,
                'feature_flags': ['legacy_api']
            }
        }
    }
]

# /cse/orgvdcs end points
# These differ from /ovdcs in terms of pagination support
LEGACY_ORG_VDC_HANDLERS = [
    {
        'url': "cse/orgvdcs",
        RequestMethod.GET: {
            ('33.0', '34.0'): {
                'allowed_params': ['pageSize', 'page'],
                'required_params': [],
                'operation': CseOperation.ORG_VDC_LIST,
                'handler': ovdc_handler.org_vdc_list,
                'feature_flags': ['legacy_api']
            }
        },
    }
]

# /cse/3.0/cluster end points
CLUSTER_HANDLERS = [
    {
        'url': "cse/3.0/clusters",
        RequestMethod.GET: {
            ('35.0',): {
                'allowed_params': [],  # how to handle open list of query params?  # noqa: E501
                'required_params': [],
                'operation': CseOperation.V35_CLUSTER_LIST,
                'handler': v35_cluster_handler.cluster_list,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_CLUSTER_LIST,
                'handler': cluster_handler.cluster_list,
                'feature_flags': ['non_legacy_api']
            }
        },
        RequestMethod.POST: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V35_CLUSTER_CREATE,
                'handler': v35_cluster_handler.cluster_create,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V36_CLUSTER_CREATE,
                'handler': cluster_handler.cluster_create,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': "cse/3.0/nativeclusters",
        RequestMethod.GET: {
            ('36.0',): {
                'allowed_params': ['org_name', 'ovdc_name', 'pageSize', 'page'],  # noqa: E501
                'required_params': [],
                'operation': CseOperation.V36_NATIVE_CLUSTER_LIST,
                'handler': cluster_handler.native_cluster_list,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': f"cse/3.0/cluster/${RequestKey.CLUSTER_ID}",
        RequestMethod.GET: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_CLUSTER_INFO,
                'handler': v35_cluster_handler.cluster_info,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_CLUSTER_INFO,
                'handler': cluster_handler.cluster_info,
                'feature_flags': ['non_legacy_api']
            }
        },
        RequestMethod.PUT: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V35_CLUSTER_RESIZE,
                'handler': v35_cluster_handler.cluster_resize,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V36_CLUSTER_UPDATE,
                'handler': cluster_handler.cluster_update,
                'feature_flags': ['non_legacy_api']
            }
        },
        RequestMethod.DELETE: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_CLUSTER_DELETE,
                'handler': v35_cluster_handler.cluster_delete,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_CLUSTER_DELETE,
                'handler': cluster_handler.cluster_delete,
                'feature_flags': ['non_legacy_api']
            }
        }
    },
    {
        'url': f"cse/3.0/cluster/${RequestKey.CLUSTER_ID}/config",
        RequestMethod.GET: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_CLUSTER_CONFIG,
                'handler': v35_cluster_handler.cluster_config,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_CLUSTER_CONFIG,
                'handler': cluster_handler.cluster_config,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': f"cse/3.0/cluster/${RequestKey.CLUSTER_ID}/upgrade-plan",
        RequestMethod.GET: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_CLUSTER_UPGRADE_PLAN,
                'handler': v35_cluster_handler.cluster_upgrade_plan,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_CLUSTER_UPGRADE_PLAN,
                'handler': cluster_handler.cluster_upgrade_plan,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': f"cse/3.0/cluster/${RequestKey.CLUSTER_ID}/action/upgrade",
        RequestMethod.POST: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V35_CLUSTER_UPGRADE,
                'handler': v35_cluster_handler.cluster_upgrade,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': f"cse/3.0/cluster/${RequestKey.CLUSTER_ID}/nfs/${RequestKey.NODE_NAME}",  # noqa: E501
        RequestMethod.DELETE: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_NODE_DELETE,
                'handler': v35_cluster_handler.nfs_node_delete,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_NODE_DELETE,
                'handler': cluster_handler.nfs_node_delete,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': f"cse/3.0/cluster/${RequestKey.CLUSTER_ID}/acl",
        RequestMethod.GET: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_CLUSTER_ACL_LIST,
                'handler': v35_cluster_handler.cluster_acl_info,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V36_CLUSTER_ACL_LIST,
                'handler': cluster_handler.cluster_acl_info,
                'feature_flags': ['non_legacy_api']
            }
        },
        RequestMethod.PUT: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V35_CLUSTER_ACL_UPDATE,
                'handler': v35_cluster_handler.cluster_acl_update,
                'feature_flags': ['non_legacy_api']
            },
            ('36.0',): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V36_CLUSTER_ACL_UPDATE,
                'handler': cluster_handler.cluster_acl_update,
                'feature_flags': ['non_legacy_api']
            }
        },
    }
]

# /cse/3.0/ovdcs end points
OVDC_HANDLERS = [
    {
        'url': "cse/3.0/ovdcs",
        RequestMethod.GET: {
            ('35.0',): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_OVDC_LIST,
                'handler': v35_ovdc_handler.ovdc_list,
                'feature_flags': ['non_legacy_api']
            }
        },
    },
    {
        'url': f"cse/3.0/ovdc/${RequestKey.OVDC_ID}",
        RequestMethod.GET: {
            ('35.0', '36.0'): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_OVDC_INFO,
                'handler': v35_ovdc_handler.ovdc_info,
                'feature_flags': ['non_legacy_api']
            }
        },
        RequestMethod.PUT: {
            ('35.0', '36.0'): {
                'allowed_params': [],
                'required_params': [],
                'verify_payload': False,
                'payload_type': '*',
                'operation': CseOperation.V35_OVDC_UPDATE,
                'handler': v35_ovdc_handler.ovdc_update,
                'feature_flags': ['non_legacy_api']
            }
        },
    }
]

# /cse/3.0/orgvdcs end points
# These differ from /ovdcs in terms of pagination support
ORG_VDC_HANDLERS = [
    {
        'url': "cse/3.0/orgvdcs",
        RequestMethod.GET: {
            ('35.0', '36.0'): {
                'allowed_params': [],
                'required_params': [],
                'operation': CseOperation.V35_ORG_VDC_LIST,
                'handler': v35_ovdc_handler.org_vdc_list,
                'feature_flags': ['non_legacy_api']
            }
        },
    }
]

CSE_REQUEST_DISPATCHER_LIST = [
    *SYSTEM_HANDLERS,
    *TEMPLATE_HANDLERS,
    *PKS_HANDLERS,
    *LEGACY_CLUSTER_HANDLERS,
    *LEGACY_NATIVE_CLUSTER_HANDLERS,
    *LEGACY_NODE_HANDLERS,
    *LEGACY_OVDC_HANDLERS,
    *LEGACY_ORG_VDC_HANDLERS,
    *CLUSTER_HANDLERS,
    *OVDC_HANDLERS,
    *ORG_VDC_HANDLERS
]

for url_entry in CSE_REQUEST_DISPATCHER_LIST:
    url_entry['url_tokens'] = url_entry['url'].split('/')


def _parse_accept_header(accept_header: str):
    """Parse accept headers and select one that fits CSE.

    CSE is looking for headers like
    * application/json;version=33.0
    * *;version=33.0
    * */*;version=33.0
    * application/*+json;version=33.0
    If multiple matches are found, Will pick the first match.

    :param str accept_header: value of 'Accept' header sent by client

    :returns: accept header that can be serviced by CSE

    :raises NotAcceptableRequestError: If none of the accept headers matches
        what CSE is looking for.
    """
    accept_header = accept_header.lower()
    accept_headers = accept_header.split(",")
    processed_headers = {}

    for header in accept_headers:
        # break the header into a tuple that follows the following structure
        # "application/json;version=33.0" ->
        #     ('application', 'json', 'version', '33.0')
        # "application/*;version=33.0" ->
        #     ('application', '*', 'version', '33.0')
        # "application/*+json;version=33.0" ->
        #     ('application', '*+json', 'version', '33.0')
        # "*/*;version=33.0" -> ('*', '*', 'version', '33.0')
        # "*;version=33.0" -> ('*', '', 'version', '33.0')

        tokens = header.split(';')
        application_fragment = ''
        version_fragment = ''
        if len(tokens) >= 1:
            application_fragment = tokens[0]
        if len(tokens) >= 2:
            version_fragment = tokens[1]

        tokens = application_fragment.split("/")
        val0 = ''
        val1 = ''
        if len(tokens) >= 1:
            val0 = tokens[0]
        if len(tokens) >= 2:
            val1 = tokens[1]

        tokens = version_fragment.split("=")
        val2 = ''
        val3 = ''
        if len(tokens) >= 1:
            val2 = tokens[0]
        if len(tokens) >= 2:
            val3 = tokens[1]

        processed_headers[header] = (val0, val1, val2, val3)

    selected_header = None
    for header, value in processed_headers.items():
        val0, val1, val2, _ = value

        # * -> */*
        if val0 == '*' and not val1:
            val1 = '*'

        if val0 == '*':
            val0 = 'application'

        # *+json -> json
        val1 = val1.replace('*+', '')
        if val1 == '*':
            val1 = 'json'

        if (val0, val1, val2) == ('application', 'json', 'version'):
            selected_header = header
            break

    if not selected_header:
        raise cse_exception.NotAcceptableRequestError(
            error_message="CSE can only serve response as json.")

    return selected_header


def _get_api_version_from_accept_header(api_version_header: str):
    """Split input string and return the api version.

    Input must be of the format:
    [something];version=[some version]

    :param str api_version_header: value of 'Accept' header

    :returns: api version specified in the input string.
        Returns 0.0 by default.
    """
    api_version = '0.0'
    if api_version_header:
        tokens = api_version_header.split(";")
        if len(tokens) == 2:
            tokens = tokens[1].split("=")
            if len(tokens) == 2:
                api_version = tokens[1]
    return api_version


@handle_exception
def process_request(message, mqtt_publisher=None):
    """
    Determine the correct api handler to invoke and invoke it.

    The request URI, api version and HTTP verb are used to determine the
    request operation and the corresponding handler.

    Additionally support for payload verification, query param verification
    will be added in a later point of time.

    URL template matching is also performed to compute values of url template
    parameters. These computed values, request body and query params are all
    sent to handlers in form of a dictionary.

    :param dict message: message received over AMQP/MQTT bus representing the
        incoming REST request.

    :returns: response computed by the handler after processing the request
    """
    LOGGER.debug(f"Incoming request message: {json.dumps(message)}")

    api_version_header = _parse_accept_header(
        accept_header=message['headers'].get('Accept'))
    api_version = _get_api_version_from_accept_header(
        api_version_header=api_version_header)

    # Convert to upper case for matching the ENUM values
    method = RequestMethod(message['method'].upper())

    url = message['requestUri']
    url_tokens = url.split("/")
    # ignore the vcd host and /api in the url
    if len(url_tokens) > 2:
        url_tokens = url_tokens[2:]

    query_params = None
    if message['queryString']:
        query_params = dict(parse_qsl(message['queryString']))

    request_body = None
    # Should we do a content-type check? and allow only application/json content?  # noqa: E501
    # Process request body only for requests with HTTP verbs that allow body
    if method in [RequestMethod.POST,
                  RequestMethod.PUT,
                  RequestMethod.DELETE] and \
            len(message['body']) > 0:
        raw_body = base64.b64decode(message['body']).decode(sys.getfilesystemencoding())  # noqa: E501
        request_body = json.loads(raw_body)

    import container_service_extension.server.service as cse_service
    server_config = cse_service.Service().get_service_config()

    found = False
    operation = None
    handler_method = None
    url_data = {}
    for entry in CSE_REQUEST_DISPATCHER_LIST:
        if found:
            break
        if len(entry['url_tokens']) != len(url_tokens):
            continue

        url_matched = True
        for i in range(0, len(url_tokens)):
            token = entry['url_tokens'][i]
            if token.startswith("$"):
                url_data[token[1:]] = url_tokens[i]
            else:
                # Certain url tokens can be singular as well plural
                # e.g. cluster / clusters. This ensures that we support both
                # /api/cse/cluster and
                # /api/cse/clusters
                # as well as
                # /api/cse/cluster/{id} and
                # /api/cse/clusters/{id}
                target_tag = url_tokens[i].lower()
                if target_tag in DUAL_FORM_TOKENS:
                    target_tag = DUAL_FORM_TOKENS[target_tag]
                else:
                    target_tag = (target_tag,)
                if token.lower() not in target_tag:
                    url_matched = False
                    url_data.clear()
                    break

        if not url_matched:
            continue

        if method not in entry.keys():
            raise cse_exception.MethodNotAllowedRequestError()

        handlers = entry[method]
        matched_handler = None
        supported_api_versions = []
        for versions in handlers.keys():
            supported_api_versions.extend(list(versions))
            if api_version in versions or '*' in versions:
                matched_handler = handlers[versions]
                break

        if not matched_handler:
            raise cse_exception.NotAcceptableRequestError(
                error_message="Invalid api version specified. Expected "
                              f"api version '{supported_api_versions}'.")

        required_feature_flags = matched_handler.get('feature_flags', {})
        feature_flags_satisfied = True
        for feature_flag in required_feature_flags:
            value = server_config['feature_flags'].get(feature_flag, False)
            if not value:
                LOGGER.debug("Url matched but failed to satisfy feature "
                             f"flag {feature_flag}")
                feature_flags_satisfied = False
                break

        if feature_flags_satisfied:
            operation = matched_handler['operation']
            handler_method = matched_handler['handler']

            # ToDo: Extra validation based on allowed query params, content type etc.  # noqa: E501
            found = True
        else:
            break

    if not found:
        raise cse_exception.NotFoundRequestError()

    # /system operations are excluded from these checks
    if operation not in (CseOperation.SYSTEM_INFO, CseOperation.SYSTEM_UPDATE):
        if not cse_service.Service().is_running():
            raise cse_exception.BadRequestError(
                error_message='CSE service is disabled. '
                              'Contact the System Administrator.')

    # create request data dict from incoming message data
    request_data = {}

    # update request data dict with query params data
    if query_params:
        request_data[RequestKey.QUERY_PARAMS] = query_params
        LOGGER.debug(f"query parameters: {query_params}")

    # update request_data with request_body
    if request_body:
        request_data[RequestKey.INPUT_SPEC] = request_body
        LOGGER.debug(f"request body: {request_body}")

    # update request_data with url template param key-values
    request_data.update(url_data)
    request_data['url'] = url

    # extract out the authorization token
    tenant_auth_token = message['headers'].get('x-vcloud-authorization')
    is_jwt_token = False
    auth_header = message['headers'].get('Authorization')
    if auth_header:
        tokens = auth_header.split(" ")
        if len(tokens) == 2 and tokens[0].lower() == 'bearer':
            tenant_auth_token = tokens[1]
            is_jwt_token = True

    # create operation context
    operation_ctx = ctx.OperationContext(
        tenant_auth_token, is_jwt=is_jwt_token, request_id=message['id'], mqtt_publisher=mqtt_publisher)  # noqa: E501

    try:
        body_content = handler_method(request_data, operation_ctx)
    finally:
        if not operation_ctx.is_async:
            operation_ctx.end()

    if not isinstance(body_content, (list, dict)):
        body_content = {RESPONSE_MESSAGE_KEY: str(body_content)}
    response = {
        'status_code': operation.ideal_response_code,
        'body': body_content,
    }
    LOGGER.debug(f"Outgoing response: {str(response)}")
    return response
