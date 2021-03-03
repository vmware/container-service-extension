# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

from container_service_extension.common.constants.server_constants import CseOperation  # noqa: E501


class AbstractValidator(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def validate(self, request_spec: dict, current_spec: dict, operation: CseOperation) -> bool:  # noqa: E501
        """Validate the input_spec against current_spec.

        :param dict request_spec: Request spec of the cluster
        :param dict current_spec: Current status of the cluster
        :param str operation: POST/PUT/DEL
        :retur bool:
        """
        pass
