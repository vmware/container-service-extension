# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.exceptions import BadRequestError
from container_service_extension.minor_error_codes import MinorErrorCode
from container_service_extension.shared_constants import RequestKey


MISSING_KEY_TO_MINOR_ERROR_CODE_MAPPING = {
    RequestKey.CLUSTER_NAME: MinorErrorCode.REQUEST_KEY_CLUSTER_NAME_MISSING,
    RequestKey.COMPUTE_POLICY_ACTION: MinorErrorCode.REQUEST_KEY_COMPUTE_POLICY_ACTION_MISSING, # noqa: E501
    RequestKey.COMPUTE_POLICY_NAME: MinorErrorCode.REQUEST_KEY_COMPUTE_POLICY_NAME_MISSING, # noqa: E501
    RequestKey.K8S_PROVIDER: MinorErrorCode.REQUEST_KEY_K8S_PROVIDER_MISSING,
    RequestKey.NETWORK_NAME: MinorErrorCode.REQUEST_KEY_NETWORK_NAME_MISSING,
    RequestKey.NODE_NAME: MinorErrorCode.REQUEST_KEY_NODE_NAME_MISSING,
    RequestKey.NODE_NAMES_LIST: MinorErrorCode.REQUEST_KEY_NODE_NAMES_LIST_MISSING, # noqa: E501
    RequestKey.NUM_WORKERS: MinorErrorCode.REQUEST_KEY_NUM_WORKERS_MISSING,
    RequestKey.ORG_NAME: MinorErrorCode.REQUEST_KEY_ORG_NAME_MISSING,
    RequestKey.OVDC_ID: MinorErrorCode.REQUEST_KEY_OVDC_ID_MISSING,
    RequestKey.OVDC_NAME: MinorErrorCode.REQUEST_KEY_OVDC_NAME_MISSING,
    RequestKey.PKS_CLUSTER_DOMAIN: MinorErrorCode.REQUEST_KEY_PKS_CLUSTER_DOMAIN_MISSING, # noqa: E501
    RequestKey.PKS_EXT_HOST: MinorErrorCode.REQUEST_KEY_PKS_EXT_HOST_MISSING,
    RequestKey.PKS_PLAN_NAME: MinorErrorCode.REQUEST_KEY_PKS_PLAN_NAME_MISSING,
    RequestKey.SERVER_ACTION: MinorErrorCode.REQUEST_KEY_SERVER_ACTION_MISSING
}

INVALID_VALUE_TO_MINOR_ERROR_CODE_MAPPING = {
    RequestKey.CLUSTER_NAME: MinorErrorCode.REQUEST_KEY_CLUSTER_NAME_INVALID,
    RequestKey.COMPUTE_POLICY_ACTION: MinorErrorCode.REQUEST_KEY_COMPUTE_POLICY_ACTION_INVALID, # noqa: E501
    RequestKey.COMPUTE_POLICY_NAME: MinorErrorCode.REQUEST_KEY_COMPUTE_POLICY_NAME_INVALID, # noqa: E501
    RequestKey.K8S_PROVIDER: MinorErrorCode.REQUEST_KEY_K8S_PROVIDER_INVALID,
    RequestKey.NETWORK_NAME: MinorErrorCode.REQUEST_KEY_NETWORK_NAME_INVALID,
    RequestKey.NODE_NAME: MinorErrorCode.REQUEST_KEY_NODE_NAME_INVALID,
    RequestKey.NODE_NAMES_LIST: MinorErrorCode.REQUEST_KEY_NODE_NAMES_LIST_INVALID, # noqa: E501
    RequestKey.NUM_WORKERS: MinorErrorCode.REQUEST_KEY_NUM_WORKERS_INVALID,
    RequestKey.ORG_NAME: MinorErrorCode.REQUEST_KEY_ORG_NAME_INVALID,
    RequestKey.OVDC_ID: MinorErrorCode.REQUEST_KEY_OVDC_ID_INVALID,
    RequestKey.OVDC_NAME: MinorErrorCode.REQUEST_KEY_OVDC_NAME_INVALID,
    RequestKey.PKS_CLUSTER_DOMAIN: MinorErrorCode.REQUEST_KEY_PKS_CLUSTER_DOMAIN_INVALID, # noqa: E501
    RequestKey.PKS_EXT_HOST: MinorErrorCode.REQUEST_KEY_PKS_EXT_HOST_INVALID,
    RequestKey.PKS_PLAN_NAME: MinorErrorCode.REQUEST_KEY_PKS_PLAN_NAME_INVALID,
    RequestKey.SERVER_ACTION: MinorErrorCode.REQUEST_KEY_SERVER_ACTION_INVALID
}


def validate_payload(payload, required_keys):
    """Validate a given payload is good for a particular request.

    Raise appropriate error if keys are missing or if the corresponding value
    in the payload is None. Otherwise return True.

    :param dict payload:
    :param list required_keys:

    :return: True, if payload is valid
    :rtype: bool
    """
    valid = True
    minor_error_code = None

    required = set(required_keys)
    if not required.issubset(payload.keys()):
        missing_keys = list(required.difference(payload.keys()))
        error_message = \
            f"Missing required keys in request payload: {missing_keys}"
        valid = False
        key = RequestKey(missing_keys[0])
        if key in MISSING_KEY_TO_MINOR_ERROR_CODE_MAPPING:
            minor_error_code = MISSING_KEY_TO_MINOR_ERROR_CODE_MAPPING[key]
    else:
        keys_with_none_value = [k for k, v in payload.items() if k in required and v is None] # noqa: E501
        if len(keys_with_none_value) > 0:
            error_message = f"Following keys in request payloads have None as value: {keys_with_none_value}" # noqa: E501
            valid = False
            key = RequestKey(keys_with_none_value[0])
            if key in INVALID_VALUE_TO_MINOR_ERROR_CODE_MAPPING:
                minor_error_code = INVALID_VALUE_TO_MINOR_ERROR_CODE_MAPPING[key] # noqa: E501

    if not valid:
        raise BadRequestError(error_message, minor_error_code)

    return valid
