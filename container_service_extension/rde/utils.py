# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Utility methods to help interaction with defined entities framework."""
import container_service_extension.exception.exceptions as excptn
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
import container_service_extension.rde.constants as def_constants


def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < \
            def_constants.DEF_API_MIN_VERSION:
        raise excptn.DefNotSupportedException("Defined entity framework is not"
                                              " supported for {cloudapi_client.get_api_version()}")  # noqa: E501


def generate_interface_id(vendor, nss, version):
    """Generate defined entity interface id.

    By no means, id generation in this method, guarantees the actual
    entity type registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{def_constants.DEF_INTERFACE_ID_PREFIX}:{vendor}:{nss}:{version}"


def generate_entity_type_id(vendor, nss, version):
    """Generate defined entity type id.

    By no means, id generation in this method, guarantees the actual
    interface registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{def_constants.DEF_ENTITY_TYPE_ID_PREFIX}:{vendor}:{nss}:{version}"  # noqa: E501


def get_rde_version_by_vcd_api_version(vcd_api_version: float) -> str:
    return def_constants.MAP_VCD_API_VERSION_TO_RDE_VERSION[vcd_api_version]  # noqa: E501


def get_def_metadata(rde_version: str) -> dict:
    return def_constants.MAP_RDE_VERSION_TO_DEF_METADATA[rde_version]
