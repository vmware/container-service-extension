# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_1_0_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, request_spec: dict, current_status: dict, operation: CseOperation) -> bool:  # noqa: E501
        """Validate the input_spec against current_status.

        :param dict request_spec: Request spec of the cluster
        :param dict current_status: Current status of the cluster
        :param str operation: POST/PUT/DEL
        :return: is validation is successful or failure
        :rtype: bool
        :raises NotImplementedError
        """
        raise NotImplementedError
