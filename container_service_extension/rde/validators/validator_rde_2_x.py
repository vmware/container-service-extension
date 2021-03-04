# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501
from container_service_extension.common.constants.server_constants import FlattenedClusterSpecKey  # noqa: E501
from container_service_extension.common.constants.server_constants import VALID_UPDATE_FIELDS  # noqa: E501
from container_service_extension.exception.exceptions import BadRequestError
import container_service_extension.rde.utils as rde_utils
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_2_0_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, request_spec: dict, current_spec: dict, operation: CseOperation) -> bool:  # noqa: E501
        """Validate the input_spec against current_status of the cluster.

        :param dict request_spec: Request spec of the cluster
        :param dict current_spec: Current status of the cluster
        :param CseOperation operation: CSE operation key
        :return: is validation is successful or failure
        :rtype: bool
        """
        # TODO: validators for rest of the CSE operations in V36 will be
        #  implemented as and when v36/def_cluster_handler.py get other handler
        #  functions
        if operation == CseOperation.V36_CLUSTER_UPDATE:
            return validate_cluster_update_request_and_check_cluster_upgrade(request_spec, current_spec)  # noqa: E501
        raise NotImplementedError(f"Validator for {operation.name} not found")


def validate_cluster_update_request_and_check_cluster_upgrade(input_spec: dict, reference_spec: dict) -> bool:  # noqa: E501
    """Validate the desired spec with curr spec and check if upgrade operation.

    :param dict input_spec: input spec
    :param dict reference_spec: reference spec to validate the desired spec
    :return: true if cluster operation is upgrade and false if operation is
        resize
    :rtype: bool
    :raises: BadRequestError for invalid payload.
    """
    diff_fields = \
        rde_utils.find_diff_fields(input_spec, reference_spec, exclude_fields=[])  # noqa: E501

    # Raise exception if empty diff
    if not diff_fields:
        raise BadRequestError("No change in cluster specification")  # noqa: E501

    # Raise exception if fields which cannot be changed are updated
    keys_with_invalid_value = [k for k in diff_fields if k not in VALID_UPDATE_FIELDS]  # noqa: E501
    if len(keys_with_invalid_value) > 0:
        err_msg = f"Invalid input values found in {sorted(keys_with_invalid_value)}"  # noqa: E501
        raise BadRequestError(err_msg)

    is_resize_operation = False
    if FlattenedClusterSpecKey.WORKERS_COUNT.value in diff_fields or \
            FlattenedClusterSpecKey.NFS_COUNT.value in diff_fields:
        is_resize_operation = True
    is_upgrade_operation = False
    if FlattenedClusterSpecKey.TEMPLATE_NAME.value in diff_fields or \
            FlattenedClusterSpecKey.TEMPLATE_REVISION.value in diff_fields:
        is_upgrade_operation = True

    # Raise exception if resize and upgrade are performed at the same time
    if is_resize_operation and is_upgrade_operation:
        err_msg = "Cannot resize and upgrade the cluster at the same time"
        raise BadRequestError(err_msg)

    return is_upgrade_operation
