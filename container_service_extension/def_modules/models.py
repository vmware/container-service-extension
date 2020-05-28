# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass, asdict

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
class Metadata:
    cluster_name: str
    org_name: str
    ovdc_name: str

@dataclass()
class ControlPlane:
    sizing_class: str = None
    storage_profile: str = None
    count: int = 1


@dataclass()
class Workers:
    sizing_class: str = None
    storage_profile: str = None
    count: int = 2


@dataclass()
class Distribution:
    template_name: str
    template_revision: int


@dataclass()
class Settings:
    network: str
    ssh_key: str = None
    enable_nfs: bool = False
    cleanup_on_failure = True


@dataclass()
class Status:
    master_ip: str = None
    phase: str = None
    cni: str = None
    id: str = None

@dataclass()
class ClusterSpec:
    control_plane: ControlPlane
    workers: Workers
    distribution: Distribution
    settings: Settings

    def __init__(self, control_plane: ControlPlane, workers: Workers,
                 distribution: Distribution, settings: Settings):
        if isinstance(control_plane, {}.__class__):
            self.control_plane = ControlPlane(**control_plane)
        else:
            self.control_plane = control_plane

        if isinstance(workers, {}.__class__):
            self.workers = Workers(**workers)
        else:
            self.workers = workers

        if isinstance(distribution, {}.__class__):
            self.distribution = Distribution(**distribution)
        else:
            self.distribution = distribution

        if isinstance(settings, {}.__class__):
            self.settings = Settings(**settings)
        else:
            self.settings = settings

@dataclass()
class ClusterEntity:
    metadata: Metadata
    spec: ClusterSpec
    status: Status = Status()
    kind: str = DEF_NATIVE_INTERFACE_NSS
    api_version: str = ''

    def __init__(self, metadata: Metadata, spec: ClusterSpec, status=Status(),
                 kind: str = DEF_NATIVE_INTERFACE_NSS, api_version: str = ''):
        if isinstance(metadata, {}.__class__):
            self.metadata = Metadata(**metadata)
        else:
            self.metadata = metadata

        if isinstance(spec, {}.__class__):
            self.spec = ClusterSpec(**spec)
        else:
            self.spec = spec

        if isinstance(status, {}.__class__):
            self.status = Status(**status)
        else:
            self.status = status

        self.kind = kind
        self.api_version = api_version

@dataclass()
class DefEntity:
    """Represents defined entity instance."""

    name: str
    entity: ClusterEntity
    id: str = None
    entityType: str = None
    externalId: str = None
    state: str = None

    def __init__(self, name: str, entity: ClusterEntity, id: str = None,
                 entityType: str = None, externalId: str = None,
                 state: str = None):
        self.name = name
        if isinstance(entity, {}.__class__):
            self.entity = ClusterEntity(**entity)
        else:
            self.entity= entity
        self.id = id
        self.entityType = entityType
        self.externalId = externalId
        self.state = state



dist = Distribution('k81.17',1)
settings = Settings('net')
spec = ClusterSpec(control_plane=ControlPlane(), workers=Workers(), distribution=dist, settings=settings)
metadata = Metadata(cluster_name='myCluster', org_name='org1', ovdc_name='ovdc1')
cluster_entity = ClusterEntity(metadata=metadata, spec=spec)
def_entity = DefEntity(name=cluster_entity.metadata.cluster_name, entity=cluster_entity)
print(def_entity)
def_dict = asdict(def_entity)
print(DefEntity(**def_dict))
