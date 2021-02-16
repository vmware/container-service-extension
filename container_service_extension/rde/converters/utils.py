# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.rde.converters.abstract_convert_strategy import \
    AbstractConvertStrategy
from container_service_extension.rde.models.utils import get_model


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
