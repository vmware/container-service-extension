# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique


@unique
class MinorErrorCode(Enum):
    """Collection of error code and related messages."""

    DEFAULT = -1, "This is the default error message when minor error code is not specified." # noqa: E501

    CLUSTER_CREATE_CLUSTER_NAME_MISSING = 


    OVDC_COMPUTE_POLICY_LIST_OVDC_ID_MISSING

    OVDC_COMPUTE_POLICY_UPDATE_OVDC_ID_MISSING
    OVDC_COMPUTE_POLICY_UPDATE_COMPUTE_POLICY_ACTION_MISSING
    OVDC_COMPUTE_POLICY_UPDATE_COMPUTE_POLICY_NAME_MISSING

    OVDC_INFO_OVDC_ID_MISSING = 

    OVDC_UPDATE_ORG_NAME_MISSING = 3001, ""
    OVDC_UPDATE_OVDC_NAME_MISSING = 3002, ""
    OVDC_UPDATE_K8S_PROVIDER_MISSING = 3003, ""
    OVDC_UPDATE_OVDC_ID_MISSING = 3004, ""
    OVDC_UPDATE_PKS_PLAN_NAME_MISSING = 3005, ""
    OVDC_UPDATE_PKS_CLUSTER_DOMAIN_MISSING = 3006, ""

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    # ignore the first param since it's already set by __new__
    def __init__(self, _, msg):
        self._msg = msg

    def __str__(self):
        return str(self.value)

    @property
    def msg(self):
        return self._msg