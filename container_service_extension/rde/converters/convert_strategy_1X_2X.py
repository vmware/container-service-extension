# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import semantic_version

from container_service_extension.rde.converters.utils import AbstractConvertStrategy  # noqa: E501


class ConvertStrategy_1X_2X(AbstractConvertStrategy):
    def __init__(self):
        pass

    def convert(self, data, src_rde_version, destn_rde_version):
        """Convert the Cluster Entity from one RDE version to another.

        :param  data: Input Native cluster entity
        :param src_rde_version:
        :param str destn_rde_version:
        :retur data:
        """
        src_rde_version: semantic_version.Version = semantic_version.Version(src_rde_version)  # noqa: E501
        destn_rde_version: semantic_version.Version = semantic_version.Version(destn_rde_version)  # noqa: E501
        if src_rde_version > destn_rde_version:
            # TODO convert the data from 2.0 to 1.0
            pass
        elif src_rde_version < destn_rde_version:
            # TODO convert the data from 1.0 to 2.0
            pass
        # return data
        raise NotImplementedError
