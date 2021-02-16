# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc


class AbstractConvertStrategy(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def convert(self, data, src_rde_version: str, destn_rde_version: str):
        """Convert the Cluster Entity from one RDE version to another.

        :param  data: Input cluster entity
        :param src_rde_version: Source RDE version
        :param str destn_rde_version: Destination RDE version
        :return data:
        """
        pass