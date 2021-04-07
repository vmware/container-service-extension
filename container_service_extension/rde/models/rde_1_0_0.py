# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List, Optional

from dataclasses_json import dataclass_json

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501


@dataclass_json
@dataclass
class Metadata:
    cluster_name: str
    org_name: str
    ovdc_name: str


@dataclass_json
@dataclass
class Nfs:
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None
    count: int = 0


@dataclass_json
@dataclass
class ControlPlane:
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None
    count: int = 1


@dataclass_json
@dataclass
class Workers:
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None
    count: int = 1


@dataclass_json
@dataclass
class Distribution:
    template_name: Optional[str] = ""
    template_revision: int = 0


@dataclass_json
@dataclass
class Settings:
    network: str
    ssh_key: Optional[str] = None
    rollback_on_failure: bool = True


@dataclass_json
@dataclass
class Node:
    name: str
    ip: str
    sizing_class: Optional[str] = None


@dataclass_json
@dataclass
class NfsNode(Node):
    exports: Optional[str] = None


@dataclass_json
@dataclass
class Nodes:
    control_plane: Optional[Node] = None
    workers: Optional[List[Node]] = None
    nfs: Optional[List[NfsNode]] = None


@dataclass_json
@dataclass
class Status:
    # TODO(DEF) Remove master_ip once nodes is implemented.
    phase: Optional[str] = None
    cni: Optional[str] = None
    task_href: Optional[str] = None
    kubernetes: Optional[str] = None
    docker_version: Optional[str] = None
    os: Optional[str] = None
    nodes: Optional[Nodes] = None


@dataclass_json
@dataclass
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


@dataclass_json
@dataclass
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

    @classmethod
    def from_native_entity(cls, native_entity: AbstractNativeEntity):
        """Construct rde_1.0.0 native entity.

        :param AbstractNativeEntity native_entity: input native entity
        :return: native entity
        :rtype: rde_1.0.0.NativeEntity
        """
        raise NotImplementedError

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
