# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
from dataclasses import dataclass
from typing import List

import container_service_extension.def_.utils as def_utils


@dataclass(frozen=True)
class DefInterface:
    """Provides interface for the defined entity type."""

    name: str
    vendor: str = def_utils.DEF_VMWARE_VENDOR
    nss: str = def_utils.DEF_VMWARE_INTERFACE_NSS
    version: str = def_utils.DEF_VMWARE_INTERFACE_VERSION
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
class Nfs:
    sizing_class: str = None
    storage_profile: str = None
    count: int = 0


@dataclass()
class ControlPlane:
    sizing_class: str = None
    storage_profile: str = None
    count: int = 1


@dataclass()
class Workers:
    sizing_class: str = None
    storage_profile: str = None
    count: int = 1


@dataclass()
class Distribution:
    template_name: str = ""
    template_revision: int = 0

    def __init__(self, template_name: str, template_revision: int):
        self.template_name = template_name
        self.template_revision = template_revision


@dataclass()
class Settings:
    network: str
    ssh_key: str = None
    rollback_on_failure: bool = True


@dataclass()
class Node:
    name: str
    ip: str
    sizing_class: str = None


@dataclass()
class NfsNode(Node):
    exports: str = None


@dataclass()
class Nodes:
    control_plane: Node = None
    workers: List[Node] = None
    nfs: List[NfsNode] = None

    def __init__(self, control_plane: Node = None, workers: List[Node] = None,
                 nfs: List[Node] = None):
        self.control_plane = Node(**control_plane) if isinstance(control_plane, dict) else control_plane  # noqa: E501
        self.workers = [Node(**w) if isinstance(w, dict) else w for w in workers]  # noqa: E501
        self.nfs = [NfsNode(**n) if isinstance(n, dict) else n for n in nfs]


@dataclass()
class Status:
    # TODO(DEF) Remove master_ip once nodes is implemented.
    phase: str = None
    cni: str = None
    task_href: str = None
    kubernetes: str = None
    cni: str = None
    docker_version: str = None
    os: str = None
    nodes: Nodes = None

    def __init__(self, phase: str = None,
                 cni: str = None, task_href: str = None,
                 kubernetes: str = None, docker_version: str = None,
                 os: str = None, nodes: Nodes = None):
        self.phase = phase
        self.cni = cni
        self.task_href = task_href
        self.kubernetes = kubernetes
        self.docker_version = docker_version
        self.os = os
        self.nodes = Nodes(**nodes) if isinstance(nodes, dict) else nodes


@dataclass()
class ClusterSpec:
    """Represents the cluster spec.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    control_plane: ControlPlane
    workers: Workers
    nfs: Nfs
    k8_distribution: Distribution
    settings: Settings

    def __init__(self, settings: Settings, k8_distribution: Distribution = None,  # noqa: E501
                 control_plane: ControlPlane = None, workers: Workers = None,
                 nfs: Nfs = None):
        self.settings = Settings(**settings) \
            if isinstance(settings, dict) else settings
        self.control_plane = ControlPlane(**control_plane) \
            if isinstance(control_plane, dict) else control_plane or ControlPlane()  # noqa: E501
        self.workers = Workers(**workers) \
            if isinstance(workers, dict) else workers or Workers()
        self.nfs = Nfs(**nfs) if isinstance(nfs, dict) else nfs or Nfs()
        self.k8_distribution = Distribution(**k8_distribution) \
            if isinstance(k8_distribution, dict) else k8_distribution or Distribution()  # noqa: E501


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
            "settings": {
                "network": "net",
                "ssh_key": null,
                "rollback_on_failure": true
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
        "api_version": ""
    }
    """

    metadata: Metadata
    spec: ClusterSpec
    status: Status = Status()
    kind: str = def_utils.DEF_NATIVE_ENTITY_TYPE_NSS
    api_version: str = ''

    def __init__(self, metadata: Metadata, spec: ClusterSpec, status=Status(),
                 kind: str = def_utils.DEF_VMWARE_INTERFACE_NSS,
                 api_version: str = ''):

        self.metadata = Metadata(**metadata) \
            if isinstance(metadata, dict) else metadata
        self.spec = ClusterSpec(**spec) if isinstance(spec, dict) else spec
        self.status = Status(**status) if isinstance(status, dict) else status
        self.kind = kind
        self.api_version = api_version


@dataclass()
class Owner:
    name: str = None
    id: str = None


@dataclass()
class Org:
    name: str = None
    id: str = None


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
    owner: Owner = None
    org: Org = None

    def __init__(self, entity: ClusterEntity, name: str = None, id: str = None,
                 entityType: str = None, externalId: str = None,
                 state: str = None, owner: Owner = None, org: Org = None):
        self.entity = ClusterEntity(**entity) if isinstance(entity, dict) else entity  # noqa: E501
        self.name = name or self.entity.metadata.cluster_name
        self.id = id
        self.entityType = entityType
        self.externalId = externalId
        self.state = state
        self.owner = Owner(**owner) if isinstance(owner, dict) else owner
        self.org = Org(**org) if isinstance(org, dict) else org


@dataclass()
class Ovdc:
    k8s_runtime: List[str]
    ovdc_name: str = None
    ovdc_id: str = None
    remove_cp_from_vms_on_disable: bool = False


@dataclass()
class ClusterAclEntry:
    accessLevelId: str = None
    memberId: str = None
    id: str = None
    grantType: str = None
    objectId: str = None
    username: str = None

    def get_filtered_dict(self, include=[]):
        orig_dict = asdict(self)
        include_set = set(include)
        filtered_dict = {}
        for key, value in orig_dict.items():
            if key in include_set:
                filtered_dict[key] = value
        return filtered_dict
