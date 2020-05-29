# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from enum import Enum
from enum import unique

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
DEF_SCHEMA_DIRECTORY = 'cse_def_schema'
DEF_ENTITY_TYPE_SCHEMA_FILE = 'schema.json'


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
    k8_distribution: Distribution
    settings: Settings

    def __init__(self, control_plane: ControlPlane, workers: Workers,
                 k8_distribution: Distribution, settings: Settings):
        if isinstance(control_plane, {}.__class__):
            self.control_plane = ControlPlane(**control_plane)
        else:
            self.control_plane = control_plane

        if isinstance(workers, {}.__class__):
            self.workers = Workers(**workers)
        else:
            self.workers = workers

        if isinstance(k8_distribution, {}.__class__):
            self.k8_distribution = Distribution(**k8_distribution)
        else:
            self.k8_distribution = k8_distribution

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


class DefNotSupportedException(OperationNotSupportedException):
    """Defined entity framework is not supported."""


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
