# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List

from container_service_extension.rde import constants as def_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501


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
class NativeEntity(AbstractNativeEntity):
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
    kind: str = def_constants.DEF_NATIVE_ENTITY_TYPE_NSS
    api_version: str = ''

    def __init__(self, metadata: Metadata, spec: ClusterSpec, status=Status(),
                 kind: str = def_constants.DEF_VMWARE_INTERFACE_NSS,
                 api_version: str = ''):

        self.metadata = Metadata(**metadata) \
            if isinstance(metadata, dict) else metadata
        self.spec = ClusterSpec(**spec) if isinstance(spec, dict) else spec
        self.status = Status(**status) if isinstance(status, dict) else status
        self.kind = kind
        self.api_version = api_version
