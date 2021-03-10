# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum, unique

NCP_BOUNDARY_FIREWALL_SECTION_NAME = "NCP_BOUNDARY_FIREWALL_SECTION"
NCP_BOUNDARY_TOP_FIREWALL_SECTION_NAME = "NCP_BOUNDARY_TOP_FIREWALL_SECTION"
NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION_NAME = \
    "NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION"

ALL_NODES_IP_SET_NAME = 'ALL_NODES'
ALL_PODS_IP_SET_NAME = 'ALL_PODS'

ALL_NODES_PODS_NSGROUP_NAME = "ALL_NODES_PODS"

# Prefix for Gateway urn
GATEWAY_URN_PREFIX = 'urn:vcloud:gateway'

# NSXT Gateway NAT constants
NATS_PATH_FRAGMENT = 'nat'
RULES_PATH_FRAGMENT = 'rules'
DNAT_RULE_TYPE = 'DNAT'

# NSX-T constants
NSXT_BACKED_GATEWAY_UPLINK_INDEX = 0  # NSX-T gateway only have 1 ext network
NSXT_PUT_REQUEST_WAIT_TIME = 3

# External network available ip address path fragment
AVAILABLE_IP_PATH_FRAGMENT = 'availableIpAddresses'

# NSX-T realized status
NSXT_GATEWAY_REALIZED_STATUS = 'REALIZED'


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


@unique
class NsxtNATRuleKey(str, Enum):
    """Keys for NSXT NAT Rules."""

    NAME = 'name'
    DESCRIPTION = 'description'
    ENABLED = 'enabled'
    RULE_TYPE = 'ruleType'
    EXTERNAL_ADDRESSES = 'externalAddresses'
    INTERNAL_ADDRESSES = 'internalAddresses'
    LOGGING = 'logging'
    APPLICATION_PORT_PROFILE = 'applicationPortProfile'
    DNAT_EXTERNAL_PORT = 'dnatExternalPort'
    ID = 'id'


@unique
class NsxtGatewayRequestKey(str, Enum):
    EDGE_GATEWAY_UPLINKS = 'edgeGatewayUplinks'
    UPLINK_ID = 'uplinkId'
    GATEWAY = 'gateway'
    PREFIX_LENGTH = 'prefixLength'
    TOTAL_IP_COUNT = 'totalIpCount'
    AUTO_ALLOCATE_IP_RANGES = 'autoAllocateIpRanges'
    SUBNETS = 'subnets'
    VALUES = 'values'
    IP_RANGES = 'ipRanges'
    START_ADDRESS = 'startAddress'
    END_ADDRESS = 'endAddress'
    STATUS = 'status'
    IP_ADDRESS = 'ipAddress'
