# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List, Optional

from dataclasses_json import dataclass_json
import yaml

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_2_0_0 as rde_2_0_0


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
    exposed: bool = False


@dataclass_json
@dataclass
class ClusterSpec:
    """Represents the cluster spec.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    settings: Settings
    control_plane: ControlPlane = ControlPlane()
    workers: Workers = Workers()
    nfs: Nfs = Nfs()
    k8_distribution: Distribution = Distribution()
    expose: bool = False


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
            "nfs": {
                "count": 1,
                "sizing_class": "small",
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
            },
            "expose": False
        },
        "status": {
            "cni": null,
            "docker_version": null,
            "exposed": False,
            "kubernetes": null,
            "nodes": {
                "workers": [
                    {
                        "name": "node-abcd",
                        "ip": "10.0.0.2",
                        "sizing_class": "small",
                    }
                ],
                "control_plane": [
                    {
                        "name": "mstr-xyzv",
                        "ip": "10.0.0.3",
                        "sizing_class": "Large",
                    }
                ],
                "nfs": [
                    {
                        "name": "nfsd-uvwx",
                        "ip": "10.0.0.4",
                        "sizing_class": "small",
                        "exports": "/usr/share/abc, /usr/share/xyz"
                    }
                ]
            },
            "os": null,
            "phase": null,
            "task_href" : null
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
        if isinstance(native_entity, NativeEntity):
            return native_entity

        if isinstance(native_entity, rde_2_0_0.NativeEntity):
            rde_2_x_entity: rde_2_0_0.NativeEntity = native_entity

            metadata = Metadata(
                cluster_name=rde_2_x_entity.metadata.name,
                org_name=rde_2_x_entity.metadata.org_name,
                ovdc_name=rde_2_x_entity.metadata.virtual_data_center_name
            )

            settings = Settings(
                network=rde_2_x_entity.spec.settings.ovdc_network,
                ssh_key=rde_2_x_entity.spec.settings.ssh_key,
                rollback_on_failure=rde_2_x_entity.spec.settings.rollback_on_failure  # noqa: E501
            )

            k8_distribution = Distribution(
                template_name=rde_2_x_entity.spec.distribution.template_name,
                template_revision=rde_2_x_entity.spec.distribution.template_revision  # noqa: E501
            )

            control_plane = ControlPlane(
                sizing_class=rde_2_x_entity.spec.topology.control_plane.sizing_class,  # noqa: E501
                storage_profile=rde_2_x_entity.spec.topology.control_plane.storage_profile,  # noqa: E501
                count=rde_2_x_entity.spec.topology.control_plane.count
            )

            workers = Workers(
                sizing_class=rde_2_x_entity.spec.topology.workers.sizing_class,
                storage_profile=rde_2_x_entity.spec.topology.workers.storage_profile,  # noqa: E501
                count=rde_2_x_entity.spec.topology.workers.count
            )

            nfs = Nfs(
                sizing_class=rde_2_x_entity.spec.topology.nfs.sizing_class,
                storage_profile=rde_2_x_entity.spec.topology.nfs.storage_profile,  # noqa: E501
                count=rde_2_x_entity.spec.topology.nfs.count
            )

            spec = ClusterSpec(
                settings=settings,
                k8_distribution=k8_distribution,
                control_plane=control_plane,
                workers=workers,
                nfs=nfs,
                expose=rde_2_x_entity.spec.settings.network.expose
            )

            # Convert "status" only for entities that are already created
            # New cluster creation won't have "status" section in RDE
            status = cls.status
            if rde_2_x_entity.status.nodes:

                if rde_2_x_entity.status.cloud_properties.exposed:
                    control_plane_ip = rde_2_x_entity.status.external_ip
                else:
                    control_plane_ip = rde_2_x_entity.status.nodes.control_plane.ip  # noqa: E501

                control_plane = Node(
                    name=rde_2_x_entity.status.nodes.control_plane.name,
                    ip=control_plane_ip,
                    sizing_class=rde_2_x_entity.status.nodes.control_plane.sizing_class  # noqa: E501
                )

                workers = []
                for worker_node in rde_2_x_entity.status.nodes.workers:
                    worker_node_1_x = Node(
                        name=worker_node.name,
                        ip=worker_node.ip,
                        sizing_class=worker_node.sizing_class
                    )
                    workers.append(worker_node_1_x)

                nfs_nodes = []
                for nfs_node in rde_2_x_entity.status.nodes.nfs:
                    nfs_node_1_x = NfsNode(
                        name=nfs_node.name,
                        ip=nfs_node.ip,
                        sizing_class=nfs_node.sizing_class,
                        exports=str(nfs_node.exports)
                    )
                    nfs_nodes.append(nfs_node_1_x)

                nodes = Nodes(
                    control_plane=control_plane,
                    workers=workers,
                    nfs=nfs_nodes
                )

                status = Status(
                    phase=rde_2_x_entity.status.phase,
                    cni=rde_2_x_entity.status.cni,
                    task_href=rde_2_x_entity.status.task_href,
                    kubernetes=rde_2_x_entity.status.kubernetes,
                    docker_version=rde_2_x_entity.status.docker_version,
                    os=rde_2_x_entity.status.os,
                    nodes=nodes,
                    exposed=rde_2_x_entity.status.cloud_properties.exposed
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
                Node(name=item['name'], ip=item['ipAddress'])
            )
        nfs_nodes = []
        for item in cluster['nfs_nodes']:
            nfs_nodes.append(
                NfsNode(
                    name=item['name'],
                    ip=item['ipAddress'],
                    exports=item['exports']
                )
            )

        k8_distribution = Distribution(
            template_name=cluster['template_name'],
            template_revision=int(cluster['template_revision'])
        )

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
                kubernetes=f"{cluster['kubernetes']} {cluster['kubernetes_version']}",  # noqa: E501
                cni=f"{cluster['cni']} {cluster['cni_version']}",
                os=cluster['os'],
                docker_version=cluster['docker_version'],
                nodes=Nodes(
                    control_plane=Node(
                        name=cluster['master_nodes'][0]['name'],
                        ip=cluster['master_nodes'][0]['ipAddress']
                    ),
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

    @classmethod
    def get_sample_native_cluster_specification(cls, k8_runtime: str = shared_constants.ClusterEntityKind.NATIVE.value):  # noqa: E501
        cluster_spec_field_descriptions = """# Short description of various properties used in this sample cluster configuration
# api_version: Represents the payload version of the cluster specification. By default, empty.
# kind: The kind of the Kubernetes cluster.
#
# metadata: This is a required section
# metadata.cluster_name: Name of the cluster to be created or resized.
# metadata.org_name: The name of the Organization in which cluster needs to be created or managed.
# metadata.ovdc_name: The name of the Organization Virtual data center in which the cluster need to be created or managed.
#
# spec: User specification of the desired state of the cluster.
# spec.control_plane: An optional sub-section for desired control-plane state of the cluster. The properties \"sizing_class\" and \"storage_profile\" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like \"resize\" and \"upgrade\".
# spec.control_plane.count: Number of control plane node(s). Only single control plane node is supported.
# spec.control_plane.sizing_class: The compute sizing policy with which control-plane node needs to be provisioned in a given \"ovdc\". The specified sizing policy is expected to be pre-published to the given ovdc.
# spec.control_plane.storage_profile: The storage-profile with which control-plane needs to be provisioned in a given \"ovdc\". The specified storage-profile is expected to be available on the given ovdc.
#
# spec.k8_distribution: This is a required sub-section.
# spec.k8_distribution.template_name: Template name based on guest OS, Kubernetes version, and the Weave software version
# spec.k8_distribution.template_revision: revision number
#
# spec.nfs: Optional sub-section for desired nfs state of the cluster. The properties \"sizing_class\" and \"storage_profile\" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like \"resize\" and \"upgrade\".
# spec.nfs.count: Nfs nodes can only be scaled-up; they cannot be scaled-down. Default value is 0.
# spec.nfs.sizingClass: The compute sizing policy with which nfs node needs to be provisioned in a given \"ovdc\". The specified sizing policy is expected to be pre-published to the given ovdc.
# spec.nfs.storageProfile: The storage-profile with which nfs needs to be provisioned in a given \"ovdc\". The specified storage-profile is expected to be available on the given ovdc.
#
# spec.settings: This is a required sub-section
# spec.settings.network: This value is mandatory. Name of the Organization's virtual data center network
# spec.settings.rollback_on_failure: Optional value that is true by default. On any cluster operation failure, if the value is set to true, affected node VMs will be automatically deleted.
# spec.settings.ssh_key: Optional ssh key that users can use to log into the node VMs without explicitly providing passwords.
#
# spec.workers: Optional sub-section for the desired worker state of the cluster. The properties \"sizing_class\" and \"storage_profile\" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like \"resize\" and \"upgrade\". Non uniform worker nodes in the clusters is not yet supported.
# spec.workers.count: number of worker nodes (default value:1) Worker nodes can be scaled up and down.
# spec.workers.sizing_class: The compute sizing policy with which worker nodes need to be provisioned in a given \"ovdc\". The specified sizing policy is expected to be pre-published to the given ovdc.
# spec.workers.storage_profile: The storage-profile with which worker nodes need to be provisioned in a given \"ovdc\". The specified storage-profile is expected to be available on the given ovdc.
#
# status: Current state of the cluster in the server. This is not a required section for any of the operations.\n
"""  # noqa: E501
        metadata = Metadata('cluster_name', 'organization_name',
                            'org_virtual_data_center_name')
        status = Status()
        settings = Settings(network='ovdc_network_name', ssh_key=None)
        k8_distribution = Distribution(
            template_name='ubuntu-16.04_k8-1.17_weave-2.6.0',
            template_revision=2
        )
        control_plane = ControlPlane(
            count=1,
            sizing_class='Large_sizing_policy_name',
            storage_profile='Gold_storage_profile_name'
        )
        workers = Workers(
            count=2,
            sizing_class='Medium_sizing_policy_name',
            storage_profile='Silver_storage_profile'
        )

        nfs = Nfs(
            count=0,
            sizing_class='Large_sizing_policy_name',
            storage_profile='Platinum_storage_profile_name'
        )

        cluster_spec = ClusterSpec(
            control_plane=control_plane,
            k8_distribution=k8_distribution,
            settings=settings,
            workers=workers,
            nfs=nfs
        )

        native_entity_dict = NativeEntity(metadata=metadata,
                                          spec=cluster_spec,
                                          status=status,
                                          kind=k8_runtime).to_dict()
        # remove status part of the entity dict
        del native_entity_dict['status']

        sample_apply_spec = yaml.dump(native_entity_dict)
        return cluster_spec_field_descriptions + sample_apply_spec
