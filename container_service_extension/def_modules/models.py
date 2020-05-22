# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from enum import Enum
from enum import unique
from pathlib import Path

# Defined Entity Framework related constants
DEF_CSE_VENDOR = 'cse'
DEF_NATIVE_INTERFACE_NSS = 'native'
DEF_NATIVE_INTERFACE_VERSION = '1.0.0'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0


@unique
class DefConstantKeys(str, Enum):
    VENDOR = 'vendor'
    INTERFACE_NSS = 'interface_nss'
    INTERFACE_VERSION = 'interface_version'
    INTERFACE_NAME = 'interface_name'
    ENTITY_TYPE_NAME = 'entity_type_name'
    ENTITY_TYPE_NSS = 'entity_type_nss'
    ENTITY_TYPE_VERSION = 'entityt_type_version'
    ENTITY_TYPE_SCHEMA_FILEPATH = 'schema_filepath'


DEF_SCHEMA_PATH_PREFIX = Path.home() / '.cse-def-schema'

DEF_VERSION_TO_CONSTANTS_MAP = {
    35.0: {
        DefConstantKeys.VENDOR: DEF_CSE_VENDOR,
        DefConstantKeys.INTERFACE_NSS: DEF_NATIVE_INTERFACE_NSS,
        DefConstantKeys.INTERFACE_VERSION: DEF_NATIVE_INTERFACE_VERSION,
        DefConstantKeys.INTERFACE_NAME: 'nativeClusterInterface',
        DefConstantKeys.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefConstantKeys.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefConstantKeys.ENTITY_TYPE_NAME: 'nativeClusterEntityType',
        DefConstantKeys.ENTITY_TYPE_SCHEMA_FILEPATH: f"{DEF_SCHEMA_PATH_PREFIX}" # noqa: E501
                                                     '/api-v35' \
                                                     '/schema.json'
    }
}


@dataclass(frozen=True)
class DefInterface:
    """Provides interface for the defined entity type."""

    name: str = None
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
            return f"{DEF_INTERFACE_ID_PREFIX}:{self.vendor}.{self.nss}:" \
                f"{self.version}"
        else:
            return self.id


@dataclass(frozen=True)
class DefEntityType:
    """Represents the schema for Defined Entities."""

    name: str = None
    description: str = None
    schema: dict = None
    interfaces: list = None
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
            return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{self.vendor}.{self.nss}:" \
                f"{self.version}"
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


# DEF constructs initialized during CSE server startup
NativeClusterEntityType: DefEntityType = None
NativeClusterInterface: DefInterface = None
