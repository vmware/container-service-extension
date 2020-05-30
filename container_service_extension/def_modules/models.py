# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass

import container_service_extension.def_modules.utils as def_utils


@dataclass(frozen=True)
class DefInterface:
    """Provides interface for the defined entity type."""

    name: str
    vendor: str = def_utils.DEF_CSE_VENDOR
    nss: str = def_utils.DEF_NATIVE_INTERFACE_NSS
    version: str = def_utils.DEF_NATIVE_INTERFACE_VERSION
    id: str = None
    readonly: bool = False

    def get_id(self):
        """Get or generate interface id.

        Example: urn:vcloud:interface:cse.native:1.0.0.

        By no means, id generation in this method, guarantees the actual
        interface registration with vCD.
        """
        if self.id is None:
            return def_utils.\
                generate_interface_id(self.vendor, self.nss, self.version)
        else:
            return self.id


@dataclass(frozen=True)
class DefEntityType:
    """Represents the schema for Defined Entities."""

    name: str
    description: str
    schema: dict
    interfaces: list
    vendor: str = def_utils.DEF_CSE_VENDOR
    nss: str = def_utils.DEF_NATIVE_ENTITY_TYPE_NSS
    version: str = def_utils.DEF_NATIVE_ENTITY_TYPE_VERSION
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
            return def_utils.\
                generate_entity_type_id(self.vendor, self.nss, self.version)
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
    rollback_on_failure = True


@dataclass()
class Status:
    master_ip: str = None
    phase: str = None
    cni: str = None
    id: str = None


@dataclass()
class ClusterSpec:
    """Represents the cluster spec.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    control_plane: ControlPlane
    workers: Workers
    k8_distribution: Distribution
    settings: Settings

    def __init__(self, control_plane: ControlPlane, workers: Workers,
                 k8_distribution: Distribution, settings: Settings):

        self.control_plane = ControlPlane(**control_plane) \
            if isinstance(control_plane, dict) else control_plane
        self.workers = Workers(**workers) \
            if isinstance(workers, dict) else workers
        self.k8_distribution = Distribution(**k8_distribution)\
            if isinstance(k8_distribution, dict) else k8_distribution
        self.settings = Settings(**settings) \
            if isinstance(settings, dict) else settings


@dataclass()
class ClusterEntity:
    """Represents the Native Cluster entity.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.

    Sample representation in JSON format
    {
        "kind": "native",
        "spec": {
            "workers": {
                "count": 2,
                "sizing_class": "small",
                "storage_profile": "Any"
            },
            "control_plane": {
                "count": 1,
                "sizing_class": "Large",
                "storage_profile": "Any"
            },
            "k8_distribution": {
                "template_name": "k81.17",
                "template_revision": 1
            }
        },
        "status": {
            "id": null,
            "cni": null,
            "phase": null,
            "master_ip": "10.150.23.45"
        },
        "metadata": {
            "org_name": "org1",
            "ovdc_name": "ovdc1",
            "cluster_name": "myCluster"
        },
        "settings": {
            "network": "net",
            "ssh_key": null,
            "enable_nfs": false
        },
        "api_version": ""
    }
    """

    metadata: Metadata
    spec: ClusterSpec
    status: Status = Status()
    kind: str = def_utils.DEF_NATIVE_ENTITY_TYPE_NSS
    api_version: str = ''

    def __init__(self, metadata: Metadata, spec: ClusterSpec, status=Status(),
                 kind: str = def_utils.DEF_NATIVE_INTERFACE_NSS,
                 api_version: str = ''):

        self.metadata = Metadata(**metadata) \
            if isinstance(metadata, dict) else metadata
        self.spec = ClusterSpec(**spec) if isinstance(spec, dict) else spec
        self.status = Status(**status) if isinstance(status, dict) else status
        self.kind = kind
        self.api_version = api_version


@dataclass()
class DefEntity:
    """Represents defined entity instance.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

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
        self.entity = ClusterEntity(**entity) if isinstance(entity, dict) else entity # noqa: E501
        self.id = id
        self.entityType = entityType
        self.externalId = externalId
        self.state = state
