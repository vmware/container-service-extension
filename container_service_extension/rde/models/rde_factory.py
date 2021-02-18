# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import semantic_version

from container_service_extension.rde.models.rde_1_0_0 import NativeEntity as NativeEntity1X  # noqa: E501
from container_service_extension.rde.models.rde_2_0_0 import NativeEntity as NativeEntity2X  # noqa: E501


def get_rde_model(rde_version):
    """Get the model class of the specified rde_version.

    Factory method to return the model class based on the specified RDE version
    :param rde_version (str)

    :rtype model: NativeEntity
    """
    rde_version: semantic_version.Version = semantic_version.Version(rde_version)  # noqa: E501
    if rde_version.major == 1:
        return NativeEntity1X
    elif rde_version.major == 2:
        return NativeEntity2X
