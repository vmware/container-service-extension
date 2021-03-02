# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501
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
        if operation == CseOperation.V36_CLUSTER_UPDATE:
            return rde_utils.validate_cluster_update_request_and_check_cluster_upgrade(request_spec, current_spec)  # noqa: E501
        raise NotImplementedError(f"Validator for {operation.name} not found")
