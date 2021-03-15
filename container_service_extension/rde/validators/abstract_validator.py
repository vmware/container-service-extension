# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501


class AbstractValidator(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def validate(self, cloudapi_client: CloudApiClient, entity_id: str = None,
                 entity: dict = None,
                 operation: BehaviorOperation = None) -> bool:
        """Validate the input_spec against current_spec.

        :param cloudapi_client: cloud api client
        :param dict entity: entity to be validated
        :param entity_id: entity id to be validated
        :param BehaviorOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        """
        pass
