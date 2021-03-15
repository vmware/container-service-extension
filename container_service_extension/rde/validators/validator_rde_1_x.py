# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_1_0_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, cloudapi_client: CloudApiClient, entity_id: str = None,
                 entity: dict = None,
                 operation: BehaviorOperation = None) -> bool:
        """Validate the input_spec against current_status of the cluster.

        :param cloudapi_client: cloud api client
        :param dict entity: entity to be validated
        :param entity_id: entity id to be validated
        :param BehaviorOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        """
        raise NotImplementedError
