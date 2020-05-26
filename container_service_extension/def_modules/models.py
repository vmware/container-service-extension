# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass

# Defined Entity Framework related constants
DEF_CSE_VENDOR = 'cse'
DEF_NATIVE_INTERFACE_NSS = 'native'
DEF_NATIVE_INTERFACE_VERSION = '1.0.0'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'


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
            return f"{DEF_INTERFACE_ID_PREFIX}:{self.vendor}.{self.nss}:" \
                f"{self.version}"
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
            return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{self.vendor}.{self.nss}:" \
                f"{self.version}"
        else:
            return self.id

@dataclass()
class ClusterEntity:
    # Sample ClusterEntity - Yet to be done
    name: str
    control_plane: {'count':None, 'sizing_class':None}
    workers: {'count':None, 'sizing_class':None}
    k8_dist: {'template':None, 'version':None}
    settings: {'enable_nfs':False, 'ssh_key':None}
    state: {'master_ip':None}

@dataclass()
class DefEntity:
    """Represents defined entity instance."""

    name: str
    entity: ClusterEntity
    id: str = None
    entityType: str = None
    externalId: str = None
    state: str = None