# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum

NCP_BOUNDARY_FIREWALL_SECTION_NAME = "NCP_BOUNDARY_FIREWALL_SECTION"
NCP_BOUNDARY_TOP_FIREWALL_SECTION_NAME = "NCP_BOUNDARY_TOP_FIREWALL_SECTION"
NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION_NAME = \
    "NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION"

ALL_NODES_IP_SET_NAME = 'ALL_NODES'
ALL_PODS_IP_SET_NAME = 'ALL_PODS'

ALL_NODES_PODS_NSGROUP_NAME = "ALL_NODES_PODS"


class RequestMethodVerb(Enum):
    GET = 'Get'
    POST = 'Post'
    PUT = 'Put'
    DELETE = 'Delete'


class INSERT_POLICY(Enum):
    INSERT_TOP = 'insert_top'
    INSERT_BEFORE = 'insert_before'
    INSERT_AFTER = 'insert_after'
    INSERT_BOTTOM = 'insert_bottom'


class FIREWALL_ACTION(Enum):
    ALLOW = "ALLOW"
    DROP = "DROP"
    REJECT = "REJECT"
