# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import \
    BehaviorOperation
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_1_0_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, api_version, input_entity: AbstractNativeEntity,
                 current_entity: AbstractNativeEntity = None,
                 operation: BehaviorOperation = None) -> bool:  # noqa: E501
        """Validate the input_spec against current_status.

        :param api_version:
        :param AbstractNativeEntity input_entity: Request spec of the cluster
        :param AbstractNativeEntity current_entity: Current status of the cluster  # noqa: E501
        :param BehaviorOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        :raises NotImplementedError
        """
        raise NotImplementedError
