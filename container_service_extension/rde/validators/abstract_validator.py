# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501


class AbstractValidator(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def validate(self, input_entity: AbstractNativeEntity, current_entity: AbstractNativeEntity, operation: CseOperation) -> bool:  # noqa: E501
        """Validate the input_spec against current_spec.

        :param AbstractNativeEntity input_entity: Request spec of the cluster
        :param AbstractNativeEntity current_entity: Current status of the cluster  # noqa: E501
        :param CseOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        """
        pass
