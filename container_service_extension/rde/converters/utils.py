# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import abc

from container_service_extension.rde.models.utils import get_model


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


def convert(data: dict, destn_rde_version: str, src_rde_version: str = None,
            strategy: AbstractConvertStrategy = None):
    """"""
    if strategy:
        return strategy.convert(data=data, src_rde_version=src_rde_version,
                                destn_rde_version=destn_rde_version)
    # Pass the data into the constructor of the associated model class for
    # destination_rde_version.
    # TODO Handle exceptions
    destn_model = get_model(destn_rde_version)
    data = destn_model(**data)
    return data
