# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from enum import Enum
from enum import unique
from pathlib import Path

from pyvcloud.vcd.exceptions import OperationNotSupportedException

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient

# Defined Entity Framework related constants
DEF_CSE_VENDOR = 'cse'
DEF_NATIVE_INTERFACE_NSS = 'native'
DEF_NATIVE_INTERFACE_VERSION = '1.0.0'
DEF_NATIVE_INTERFACE_NAME = 'nativeClusterInterface'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_NATIVE_ENTITY_TYPE_NAME = 'nativeClusterEntityType'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0
DEF_SCHEMA_PATH_PREFIX = Path.home() / '.cse-def-schema'


@unique
class DefKeys(str, Enum):
    VENDOR = 'vendor'
    INTERFACE_NSS = 'interface_nss'
    INTERFACE_VERSION = 'interface_version'
    INTERFACE_NAME = 'interface_name'
    ENTITY_TYPE_NAME = 'entity_type_name'
    ENTITY_TYPE_NSS = 'entity_type_nss'
    ENTITY_TYPE_VERSION = 'entity_type_version'
    ENTITY_TYPE_SCHEMA_FILEPATH = 'schema_filepath'


MAP_API_VERSION_TO_KEYS = {
    35.0: {
        DefKeys.VENDOR: DEF_CSE_VENDOR,
        DefKeys.INTERFACE_NSS: DEF_NATIVE_INTERFACE_NSS,
        DefKeys.INTERFACE_VERSION: DEF_NATIVE_INTERFACE_VERSION,
        DefKeys.INTERFACE_NAME: DEF_NATIVE_INTERFACE_NAME,
        DefKeys.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKeys.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKeys.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME,
        DefKeys.ENTITY_TYPE_SCHEMA_FILEPATH: f"{DEF_SCHEMA_PATH_PREFIX}"
                                             '/api-v35/schema.json'
    }
}


@dataclass(frozen=True)
class DefInterface:
    """Provides interface for the defined entity type."""

    name: str
    vendor: str = DEF_CSE_VENDOR
    nss: str = DEF_NATIVE_INTERFACE_NSS
    version: str = DEF_NATIVE_INTERFACE_VERSION
    id: str = None
    readonly: bool = False

    def get_id(self):
        """Get or generate interface id.

        Example: urn:vcloud:interface:cse.native:1.0.0.

        By no means, id generation in this method, guarantees the actual
        interface registration with vCD.
        """
        if self.id is None:
            return generate_interface_id(self.vendor, self.nss, self.version)
        else:
            return self.id


@dataclass(frozen=True)
class DefEntityType:
    """Represents the schema for Defined Entities."""

    name: str
    description: str
    schema: dict
    interfaces: list
    vendor: str = DEF_CSE_VENDOR
    nss: str = DEF_NATIVE_ENTITY_TYPE_NSS
    version: str = DEF_NATIVE_ENTITY_TYPE_VERSION
    id: str = None
    externalId: str = None
    readonly: bool = False

    def get_id(self):
        """Get or generate entity type id.

        Example : "urn:vcloud:interface:cse.native:1.0.0

        By no means, id generation in this method, guarantees the actual
        entity type registration with vCD.
        """
        if self.id is None:
            return generate_entity_type_id(self.vendor, self.nss, self.version)
        else:
            return self.id


@dataclass()
class DefEntity:
    """Represents defined entity instances."""

    name: str
    entity: dict
    id: str = None
    entityType: str = None
    externalId: str = None
    state: str = None


class DefNotSupportedException(OperationNotSupportedException):
    """Defined entity framework is not supported."""


def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < DEF_API_MIN_VERSION:
        raise DefNotSupportedException("Defined entity framework is not supported") # noqa: E501


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
