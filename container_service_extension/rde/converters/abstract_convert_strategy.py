# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.rde.models.utils import get_model


class AbstractConvertStrategy:
    def __init__(self):
        pass

    @staticmethod
    def convert(entity, src_rde_version: str, target_rde_version: str):
        """Convert the Cluster Entity from one RDE version to another.

        :param  entity: Input cluster entity
        :param src_rde_version: The current RDE version of the entity
        :param str target_rde_version: The target RDE version of the entity.
        :return data:
        """
        target_model = get_model(target_rde_version)
        return target_model(**entity)
