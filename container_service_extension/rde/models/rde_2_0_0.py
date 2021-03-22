# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.rde.constants import PAYLOAD_VERSION_2_0
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0


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

    def __init__(self, template_name: str = '', template_revision: int = 0, **kwargs):  # noqa: E501
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
    storage_profile: str = None


@dataclass()
class NfsNode(Node):
    exports: str = None


@dataclass()
class Nodes:
    control_plane: Node = None
    workers: List[Node] = None
    nfs: List[NfsNode] = None

    def __init__(self, control_plane: Node = None, workers: List[Node] = None,
                 nfs: List[Node] = None, **kwargs):
        self.control_plane = Node(**control_plane) if isinstance(control_plane, dict) else control_plane  # noqa: E501
        self.workers = [Node(**w) if isinstance(w, dict) else w for w in workers]  # noqa: E501
        self.nfs = [NfsNode(**n) if isinstance(n, dict) else n for n in nfs]


@dataclass()
class CloudProperties:
    org_name: str = None
    ovdc_name: str = None
    ovdc_network_name: str = None
    k8_distribution: Distribution = None
    ssh_key: str = None  # TODO contemplate the need to keep this attribute
    rollback_on_failure: bool = True

    def __init__(self, org_name: str = None, ovdc_name: str = None, ovdc_network_name: str = None,  # noqa: E501
                 k8_distribution: Distribution = None, ssh_key: str = None,
                 rollback_on_failure: bool = True, **kwargs):
        self.org_name = org_name
        self.ovdc_name = ovdc_name
        self.ovdc_network_name = ovdc_network_name
        self.k8_distribution = Distribution(**k8_distribution) \
            if isinstance(k8_distribution, dict) else k8_distribution or Distribution()  # noqa: E501
        self.ssh_key = ssh_key
        self.rollback_on_failure = rollback_on_failure


@dataclass()
class Status:
    phase: str = None
    cni: str = None
    task_href: str = None
    kubernetes: str = None
    docker_version: str = None
    os: str = None
    nodes: Nodes = None
    cloud_properties: CloudProperties = None

    def __init__(self, phase: str = None,
                 cni: str = None, task_href: str = None,
                 kubernetes: str = None, docker_version: str = None,
                 os: str = None, nodes: Nodes = None,
                 cloud_properties: CloudProperties = None, **kwargs):
        self.phase = phase
        self.cni = cni
        self.task_href = task_href
        self.kubernetes = kubernetes
        self.docker_version = docker_version
        self.os = os
        self.nodes = Nodes(**nodes) if isinstance(nodes, dict) else nodes
        self.cloud_properties = CloudProperties(
            **cloud_properties) if isinstance(cloud_properties, dict) \
            else cloud_properties or CloudProperties()


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
                 nfs: Nfs = None, **kwargs):
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
    api_version: str = PAYLOAD_VERSION_2_0

    def __init__(self, metadata: Metadata, spec: ClusterSpec, status=Status(),
                 kind: str = shared_constants.ClusterEntityKind.NATIVE.value,
                 api_version: str = PAYLOAD_VERSION_2_0, **kwargs):

        self.metadata = Metadata(**metadata) \
            if isinstance(metadata, dict) else metadata
        self.spec = ClusterSpec(**spec) if isinstance(spec, dict) else spec
        self.status = Status(**status) if isinstance(status, dict) else status
        self.kind = kind
        self.api_version = api_version

    @classmethod
    def from_native_entity(cls, native_entity: AbstractNativeEntity):
        """Construct rde_2.0.0 native entity.

        :param AbstractNativeEntity native_entity: input native entity
        :return: native entity
        :rtype: rde_2.0.0.NativeEntity
        """
        if isinstance(native_entity, rde_1_0_0.NativeEntity):
            rde_1_x_entity: rde_1_0_0.NativeEntity = native_entity

            cloud_properties = CloudProperties(org_name=rde_1_x_entity.metadata.org_name,  # noqa: E501
                                               ovdc_name=rde_1_x_entity.metadata.ovdc_name,  # noqa: E501
                                               ovdc_network_name=rde_1_x_entity.spec.settings.network,  # noqa: E501
                                               k8_distribution=rde_1_x_entity.spec.k8_distribution,  # noqa: E501
                                               ssh_key=rde_1_x_entity.spec.settings.ssh_key,  # noqa: E501
                                               rollback_on_failure=rde_1_x_entity.spec.settings.rollback_on_failure)  # noqa: E501

            status = Status(phase=rde_1_x_entity.status.phase,
                            cni=rde_1_x_entity.status.cni,
                            task_href=rde_1_x_entity.status.task_href,
                            kubernetes=rde_1_x_entity.status.kubernetes,
                            docker_version=rde_1_x_entity.status.docker_version,  # noqa: E501
                            os=rde_1_x_entity.status.os,
                            nodes=rde_1_x_entity.status.nodes,
                            cloud_properties=cloud_properties)
            rde_2_entity = cls(metadata=rde_1_x_entity.metadata,
                               spec=rde_1_x_entity.spec,
                               status=status,
                               kind=rde_1_x_entity.kind,
                               api_version=rde_1_x_entity.api_version)
            # TODO - api_version needs revisit when it is going to be in real use in the upcoming tasks  # noqa: E501
            return rde_2_entity

    @classmethod
    def from_cluster_data(cls, cluster: dict, kind: str):
        """Construct rde_2.0.0 native entity from non-rde cluster.

        :param dict cluster: cluster metadata
        :param str kind: cluster kind
        :return: native entity
        :rtype: rde_2.0.0.NativeEntity
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

        cloud_properties = CloudProperties(org_name=cluster['org_name'],
                                           ovdc_name=cluster['vdc_name'],
                                           ovdc_network_name=cluster['network_name'],  # noqa: E501
                                           k8_distribution=k8_distribution,
                                           ssh_key='')
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
                ),
                cloud_properties=cloud_properties
            ),
            metadata=Metadata(
                org_name=cluster['org_name'],
                ovdc_name=cluster['vdc_name'],
                cluster_name=cluster['name']
            ),
            api_version=""
        )
        return cluster_entity
