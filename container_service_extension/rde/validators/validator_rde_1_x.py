# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.rde.validators.abstract_validator import \
    AbstractValidator


class Validator1X(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, request_spec: dict, current_spec: dict, operation: str):
        """Validate the input_spec against current_spec.

        :param dict request_spec: Request spec of the cluster
        :param dict current_spec: Current status of the cluster
        :param str operation: POST/PUT/DEL
        :retur bool:
        """
        raise NotImplementedError
