# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_2_0_0 as rde_2_0_0


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
    kind: str = shared_constants.ClusterEntityKind.NATIVE.value
    api_version: str = ''

    def __init__(self, metadata: Metadata, spec: ClusterSpec, status=Status(),
                 kind: str = shared_constants.ClusterEntityKind.NATIVE.value,
                 api_version: str = ''):

        self.metadata = Metadata(**metadata) \
            if isinstance(metadata, dict) else metadata
        self.spec = ClusterSpec(**spec) if isinstance(spec, dict) else spec
        self.status = Status(**status) if isinstance(status, dict) else status
        self.kind = kind
        self.api_version = api_version

    @classmethod
    def from_native_entity(cls, native_entity: AbstractNativeEntity):
        """Construct rde_1.0.0 native entity.

        :param AbstractNativeEntity native_entity: input native entity
        :return: native entity
        :rtype: rde_1.0.0.NativeEntity
        """
        if isinstance(native_entity, NativeEntity):
            return native_entity

        if isinstance(native_entity, rde_2_0_0.NativeEntity):
            rde_2_x_entity: rde_2_0_0.NativeEntity = native_entity

            metadata = Metadata(
                cluster_name=rde_2_x_entity.metadata.name,
                org_name=rde_2_x_entity.metadata.orgName,
                ovdc_name=rde_2_x_entity.metadata.ovdcName
            )

            settings = Settings(
                network=rde_2_x_entity.spec.settings.network,
                ssh_key=rde_2_x_entity.spec.settings.sshKey,
                rollback_on_failure=rde_2_x_entity.spec.settings.rollbackOnFailure  # noqa: E501
            )

            k8_distribution = Distribution(
                template_name=rde_2_x_entity.spec.k8Distribution.templateName,
                template_revision=rde_2_x_entity.spec.k8Distribution.templateRevision  # noqa: E501
            )

            control_plane = ControlPlane(
                sizing_class=rde_2_x_entity.spec.controlPlane.sizingClass,
                storage_profile=rde_2_x_entity.spec.controlPlane.storageProfile,  # noqa: E501
                count=rde_2_x_entity.spec.controlPlane.count
            )

            workers = Workers(
                sizing_class=rde_2_x_entity.spec.workers.sizingClass,
                storage_profile=rde_2_x_entity.spec.workers.storageProfile,
                count=rde_2_x_entity.spec.workers.count
            )

            nfs = Nfs(
                sizing_class=rde_2_x_entity.spec.nfs.sizingClass,
                storage_profile=rde_2_x_entity.spec.nfs.storageProfile,
                count=rde_2_x_entity.spec.nfs.count
            )

            spec = ClusterSpec(
                settings=settings,
                k8_distribution=k8_distribution,
                control_plane=control_plane,
                workers=workers,
                nfs=nfs
            )

            status = Status(
                phase=rde_2_x_entity.status.phase,
                cni=rde_2_x_entity.status.cni,
                task_href=rde_2_x_entity.status.taskHref,
                kubernetes=rde_2_x_entity.status.kubernetes,
                docker_version=rde_2_x_entity.status.dockerVersion,
                os=rde_2_x_entity.status.os,
                nodes=rde_2_x_entity.status.nodes
            )

            rde_1_entity = cls(
                metadata=metadata,
                spec=spec,
                status=status,
                kind=rde_2_x_entity.kind,
                api_version=''
            )
            return rde_1_entity

        return native_entity

    @classmethod
    def from_cluster_data(cls, cluster: dict, kind: str, **kwargs):
        """Construct rde_1.0.0 native entity from non-rde cluster.

        :param dict cluster: cluster metadata
        :param str kind: cluster kind
        :return: native entity
        :rtype: rde_1.0.0.NativeEntity
        """
        worker_nodes = []
        for item in cluster['nodes']:
            worker_nodes.append(
                Node(name=item['name'], ip=item['ipAddress']))
        nfs_nodes = []
        for item in cluster['nfs_nodes']:
            nfs_nodes.append(NfsNode(
                name=item['name'],
                ip=item['ipAddress'],
                exports=item['exports']))

        k8_distribution = Distribution(
            template_name=cluster['template_name'],
            template_revision=int(cluster['template_revision']))

        cluster_entity = cls(
            kind=kind,
            spec=ClusterSpec(
                workers=Workers(
                    count=len(cluster['nodes']),
                    storage_profile=cluster['storage_profile_name']
                ),
                control_plane=ControlPlane(
                    count=len(cluster['master_nodes']),
                    storage_profile=cluster['storage_profile_name']
                ),
                nfs=Nfs(
                    count=len(cluster['nfs_nodes']),
                    storage_profile=cluster['storage_profile_name']
                ),
                settings=Settings(
                    network=cluster['network_name'],
                    ssh_key=""
                ),
                k8_distribution=k8_distribution
            ),
            status=Status(
                phase=str(server_constants.DefEntityPhase(
                    server_constants.DefEntityOperation.CREATE,
                    server_constants.DefEntityOperationStatus.SUCCEEDED)
                ),
                kubernetes=f"{cluster['kubernetes']} {cluster['kubernetes_version']}", # noqa: E501
                cni=f"{cluster['cni']} {cluster['cni_version']}",
                os=cluster['os'],
                docker_version=cluster['docker_version'],
                nodes=Nodes(
                    control_plane=Node(
                        name=cluster['master_nodes'][0]['name'],
                        ip=cluster['master_nodes'][0]['ipAddress']),
                    workers=worker_nodes,
                    nfs=nfs_nodes
                )
            ),
            metadata=Metadata(
                org_name=cluster['org_name'],
                ovdc_name=cluster['vdc_name'],
                cluster_name=cluster['name']
            ),
            api_version=""
        )
        return cluster_entity

    def get_latest_task_href(self):
        return self.status.task_href
