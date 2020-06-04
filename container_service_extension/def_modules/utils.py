# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from enum import Enum
from enum import unique

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient

# Defined Entity Framework related constants
from container_service_extension.exceptions import DefNotSupportedException

DEF_CSE_VENDOR = 'cse'
DEF_NATIVE_INTERFACE_NSS = 'native'
DEF_NATIVE_INTERFACE_VERSION = '1.0.0'
DEF_NATIVE_INTERFACE_NAME = 'nativeClusterInterface'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster1'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_NATIVE_ENTITY_TYPE_NAME = 'nativeClusterEntityType'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0
DEF_SCHEMA_DIRECTORY = 'cse_def_schema'
DEF_ENTITY_TYPE_SCHEMA_FILE = 'schema.json'
DEF_END_POINT_DESCRIMINATOR = 'internal'


@unique
class DefKey(str, Enum):
    VENDOR = 'vendor'
    INTERFACE_NSS = 'interface_nss'
    INTERFACE_VERSION = 'interface_version'
    INTERFACE_NAME = 'interface_name'
    ENTITY_TYPE_NAME = 'entity_type_name'
    ENTITY_TYPE_NSS = 'entity_type_nss'
    ENTITY_TYPE_VERSION = 'entity_type_version'
    ENTITY_TYPE_SCHEMA_VERSION = 'schema_version'


MAP_API_VERSION_TO_KEYS = {
    35.0: {
        DefKey.VENDOR: DEF_CSE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_NATIVE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_NATIVE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_NATIVE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME,
        DefKey.ENTITY_TYPE_SCHEMA_VERSION: 'api_v35',
    }
}

def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < DEF_API_MIN_VERSION:
        raise DefNotSupportedException("Defined entity framework is"
                                       " not supported for"
                                       f" {cloudapi_client.get_api_version()}")


def get_registered_def_interface():
    """Fetch the native cluster interface loaded during server startup."""
    from container_service_extension.service import Service
    return Service().get_native_cluster_interface()


def get_registered_def_entity_type():
    """Fetch the native cluster entity type loaded during server startup."""
    from container_service_extension.service import Service
    return Service().get_native_cluster_entity_type()


def generate_interface_id(vendor, nss, version):
    """Generate defined entity interface id.

    By no means, id generation in this method, guarantees the actual
    entity type registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{DEF_INTERFACE_ID_PREFIX}:{vendor}.{nss}:{version}"


def generate_entity_type_id(vendor, nss, version):
    """Generate defined entity type id.

    By no means, id generation in this method, guarantees the actual
    interface registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{vendor}.{nss}:{version}"


def is_def_supported_by_cse_server():
    """Return true if CSE server is qualified to invoke Defined Entity API

    :rtype: bool
    """
    import container_service_extension.utils as utils
    api_version = utils.get_server_api_version()
    return float(api_version) >= DEF_API_MIN_VERSION
