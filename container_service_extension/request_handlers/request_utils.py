# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import functools

import container_service_extension.exceptions as cse_exception
from container_service_extension.exceptions import BadRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
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


def validate_request_payload(desired_spec: dict, actual_spec: dict,
                             exclude_fields={}, dict_name=None):
    """Validate the desired spec with the current spec.

    TODO: if the same 'key':{'subkey': ..} are repeated in the spec, and
    also included 'exclude_fields' argument, then all the occurrences of the
    'key':{'subkey': ..} will be excluded from validation. If there is a need
    to exclude only specific occurrence, it requires change in the
    implementation.


    :param dict desired_spec: input spec
    :param dict actual_spec: reference spec to validate the desired spec
    :param dict exclude_fields: exclude the list of given sub-keys from validation  # noqa: E501
    :param str dict_name: Name of the property - whose value is of type dict and which has to undergo further validation.
    :return: true on successful validation
    :rtype: bool
    :raises: BadRequestError on encountering invalid payload value
    """
    for payload_key, payload_val in desired_spec.items():

        if isinstance(payload_val, dict):
            validate_request_payload(payload_val, actual_spec.get(payload_key),
                                     exclude_fields=exclude_fields,
                                     dict_name=payload_key)
        else:
            if payload_key in exclude_fields.get(dict_name, []):
                continue
            expected_val = actual_spec.get(payload_key)
            if payload_val != expected_val:
                error_msg = f"Invalid input configuration: {dict_name}-->{payload_key} has incorrect value"  # noqa: E501
                raise BadRequestError(error_msg)

    return True


def v35_api_exception_handler(func):
    """Decorate to trap exceptions and process them.

    Raise errors of type KeyError, TypeError, ValueError as
    BadRequestError.

    Also raises BadRequest and Internal Server Errors from backend.

    :param method func: decorated function

    :return: reference to the function that executes the decorated function
        and traps exceptions raised by it.
    """
    @functools.wraps(func)
    def exception_handler_wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.error(error)
            raise cse_exception.BadRequestError(error_message=str(error))
        except Exception as error:
            LOGGER.error(error)
            raise error
        return result
    return exception_handler_wrapper
