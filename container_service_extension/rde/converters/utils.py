# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.rde.converters.abstract_convert_strategy import AbstractConvertStrategy  # noqa: E501


def convert(data: dict, target_rde_version: str, src_rde_version: str = None,
            strategy: AbstractConvertStrategy = AbstractConvertStrategy):
    """"""
    return strategy.convert(data=data, src_rde_version=src_rde_version,
                            target_rde_version=target_rde_version)
