# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.rde.converters.base_convert_strategy import BaseConvertStrategy  # noqa: E501


def convert(entity: dict, target_rde_version: str, src_rde_version: str = None,
            strategy: BaseConvertStrategy = BaseConvertStrategy):
    """Convert the Cluster Entity from one RDE version to another.

    :param dict  entity: Input Native cluster entity
    :param str src_rde_version: The current RDE version of the entity
    :param str target_rde_version: The target RDE version of the entity.
    :param BaseConvertStrategy strategy: The conversion strategy to use.
    :return data:
    """
    return strategy.convert(entity=entity, src_rde_version=src_rde_version,
                            target_rde_version=target_rde_version)
