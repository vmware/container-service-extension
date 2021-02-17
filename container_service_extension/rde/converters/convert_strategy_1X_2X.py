# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import semantic_version

from container_service_extension.rde.converters.abstract_convert_strategy import AbstractConvertStrategy  # noqa: E501


class ConvertStrategy_1X_2X(AbstractConvertStrategy):
    def __init__(self):
        pass

    @staticmethod
    def convert(entity, src_rde_version, target_rde_version):
        """Convert the Cluster Entity from one RDE version to another.

        :param  entity: Input Native cluster entity
        :param src_rde_version: The current RDE version of the entity
        :param str target_rde_version: The target RDE version of the entity.
        :return data:
        """
        src_rde_version: semantic_version.Version = semantic_version.Version(src_rde_version)  # noqa: E501
        target_rde_version: semantic_version.Version = semantic_version.Version(target_rde_version)  # noqa: E501
        if src_rde_version > target_rde_version:
            # TODO convert the data from 2.0 to 1.0
            pass
        elif src_rde_version < target_rde_version:
            # TODO convert the data from 1.0 to 2.0
            pass
        # return entity
        raise NotImplementedError
