# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List, Optional

from dataclasses_json import dataclass_json, LetterCase

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Metadata:
    name: str
    org_name: str
    virtual_data_center_name: str
    site: str


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Nfs:
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None
    count: int = 0


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ControlPlane:
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None
    count: int = 1


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Workers:
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None
    count: int = 0


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Distribution:
    template_name: Optional[str] = ''
    template_revision: Optional[int] = 0


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Topology:
    control_plane: ControlPlane = ControlPlane()
    workers: Workers = Workers()
    nfs: Nfs = Nfs()


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Cni:
    name: Optional[str] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Pods:
    cidr_blocks: Optional[List[str]] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Services:
    cidr_blocks: Optional[List[str]] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Network:
    cni: Optional[Cni] = None
    pods: Optional[Pods] = None
    services: Optional[Services] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Settings:
    ovdc_network: str
    ssh_key: Optional[str] = None
    rollback_on_failure: bool = True
    network: Optional[Network] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Node:
    name: str
    ip: str
    sizing_class: Optional[str] = None
    storage_profile: Optional[str] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class NfsNode(Node):
    exports: Optional[List[str]] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Nodes:
    control_plane: Optional[Node] = None
    workers: Optional[List[Node]] = None
    nfs: Optional[List[NfsNode]] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class CloudProperties:
    site: Optional[str] = None
    org_name: Optional[str] = None
    virtual_data_center_name: Optional[str] = None
    ovdc_network_name: Optional[str] = None
    distribution: Distribution = Distribution()

    # TODO contemplate the need to keep this attribute
    ssh_key: Optional[str] = None

    rollback_on_failure: bool = True


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Private:
    kube_config: Optional[str] = None
    kube_token: Optional[str] = None
    certificates: Optional[List[str]] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Status:
    phase: Optional[str] = None
    cni: Optional[str] = None
    task_href: Optional[str] = None
    kubernetes: Optional[str] = None
    docker_version: Optional[str] = None
    os: Optional[str] = None
    nodes: Optional[Nodes] = None
    uid: Optional[str] = None
    cloud_properties: CloudProperties = CloudProperties()
    exposed: bool = False
    persistent_volumes: Optional[List[str]] = None
    virtual_IPs: Optional[List[str]] = None
    private: Optional[Private] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ClusterSpec:
    """Represents the cluster spec.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    settings: Settings
    topology: Topology = Topology()
    distribution: Distribution = Distribution()
    expose: bool = False


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class NativeEntity(AbstractNativeEntity):
    # TODO change the comment to have camelCase
    """Represents the Native Cluster entity.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.

    Sample representation in JSON format
    # TODO change sample representation
    {
        "kind": "native",
        "spec": {
            "topology": {
                "workers": {
                    "count": 2,
                    "sizingClass": "small",
                    "storageProfile": "Any"
                },
                "controlPlane": {
                    "count": 1,
                    "sizingClass": "Large",
                    "storageProfile": "Any"
                },
            }
            "settings": {
                "network": "net",
                "sshKey": null,
                "rollbackOnFailure": true
            },
            "distribution": {
                "templateName": "k81.17",
                "templateRevision": 1
            }
        },
        "status": {
            "id": null,
            "cni": null,
            "phase": null,
        },
        "metadata": {
            "orgName": "org1",
            "virtualDataCenterName": "ovdc1",
            "name": "myCluster"
            "site": "vcd_site"
        },
        "apiVersion": ""
    }
    """

    metadata: Metadata
    spec: ClusterSpec
    api_version: str
    status: Status = Status()
    kind: str = shared_constants.ClusterEntityKind.NATIVE.value

    @classmethod
    def from_native_entity(cls, native_entity: AbstractNativeEntity):
        """Construct rde_2.0.0 native entity from different rde_x.x.x.

        Use case: converts the NativeEntity of the specified RDE version
        to RDE 2.0.0.

        :param AbstractNativeEntity native_entity: input native entity
        :return: native entity
        :rtype: rde_2.0.0.NativeEntity
        """
        if isinstance(native_entity, NativeEntity):
            return native_entity

        if isinstance(native_entity, rde_1_0_0.NativeEntity):
            # TODO should change very much
            rde_1_x_entity: rde_1_0_0.NativeEntity = native_entity

            distribution = Distribution(
                template_name=rde_1_x_entity.spec.k8_distribution.template_name,  # noqa: E501
                template_revision=rde_1_x_entity.spec.k8_distribution.template_revision  # noqa: E501
            )
            # NOTE: since details for the field `site` is not present in
            # RDE 1.0, it is left empty
            cloud_properties = CloudProperties(site=None,
                                               org_name=rde_1_x_entity.metadata.org_name,  # noqa: E501
                                               virtual_data_center_name=rde_1_x_entity.metadata.ovdc_name,  # noqa: E501
                                               ovdc_network_name=rde_1_x_entity.spec.settings.network,  # noqa: E501
                                               distribution=distribution,
                                               ssh_key=rde_1_x_entity.spec.settings.ssh_key,  # noqa: E501
                                               rollback_on_failure=rde_1_x_entity.spec.settings.rollback_on_failure)  # noqa: E501
            # RDE 1.0 don't have storage_profile in Node definition
            control_plane = Node(
                name=rde_1_x_entity.status.nodes.control_plane.name,
                ip=rde_1_x_entity.status.nodes.control_plane.ip,
                sizing_class=rde_1_x_entity.status.nodes.control_plane.sizing_class  # noqa: E501
            )
            workers = []
            for worker in rde_1_x_entity.status.nodes.workers:
                worker_node_2_x = Node(
                    name=worker.name,
                    ip=worker.ip,
                    sizing_class=worker.sizing_class
                )
                workers.append(worker_node_2_x)
            nfs_nodes = []
            for nfs_node in rde_1_x_entity.status.nodes.nfs:
                nfs_node_2_x = Node(
                    name=nfs_node.name,
                    ip=nfs_node.ip,
                    sizing_class=nfs_node.sizing_class
                )
                nfs_nodes.append(nfs_node_2_x)
            nodes = Nodes(
                control_plane=control_plane,
                workers=workers,
                nfs=nfs_nodes
            )
            # NOTE: since details for the field `uid` is not present in
            # RDE 1.0, it is left empty.
            # Proper value for `uid` should be populated after RDE is converted
            # as `uid` is a required property in Status for RDE 2.0
            status = Status(phase=rde_1_x_entity.status.phase,
                            cni=rde_1_x_entity.status.cni,
                            task_href=rde_1_x_entity.status.task_href,
                            kubernetes=rde_1_x_entity.status.kubernetes,
                            docker_version=rde_1_x_entity.status.docker_version,  # noqa: E501
                            os=rde_1_x_entity.status.os,
                            nodes=nodes,
                            uid=None,
                            cloud_properties=cloud_properties,
                            exposed=rde_1_x_entity.status.exposed)
            # NOTE: since details for the field `site` is not present in
            # RDE 1.0, it is left empty.
            # Proper value for `site` should be populated after RDE is
            # converted as `site` is a required property in Metadata
            # for RDE 2.0
            metadata = Metadata(name=rde_1_x_entity.metadata.cluster_name,
                                org_name=rde_1_x_entity.metadata.org_name,
                                virtual_data_center_name=rde_1_x_entity.metadata.ovdc_name,  # noqa: E501
                                site='')
            topology = Topology(
                control_plane=ControlPlane(
                    sizing_class=rde_1_x_entity.spec.control_plane.sizing_class,  # noqa: E501
                    storage_profile=rde_1_x_entity.spec.control_plane.storage_profile,  # noqa: E501
                    count=rde_1_x_entity.spec.control_plane.count),
                workers=Workers(
                    sizing_class=rde_1_x_entity.spec.workers.sizing_class,
                    storage_profile=rde_1_x_entity.spec.workers.storage_profile,  # noqa: E501
                    count=rde_1_x_entity.spec.workers.count),
                nfs=Nfs(
                    sizing_class=rde_1_x_entity.spec.nfs.sizing_class,
                    storage_profile=rde_1_x_entity.spec.nfs.storage_profile,
                    count=rde_1_x_entity.spec.nfs.count),
            )
            spec = ClusterSpec(
                settings=Settings(
                    network=rde_1_x_entity.spec.settings.network,
                    ssh_key=rde_1_x_entity.spec.settings.ssh_key,
                    rollback_on_failure=rde_1_x_entity.spec.settings.rollback_on_failure),  # noqa: E501,
                topology=topology,
                distribution=Distribution(
                    template_name=rde_1_x_entity.spec.k8_distribution.template_name,  # noqa: E501
                    template_revision=rde_1_x_entity.spec.k8_distribution.template_revision),  # noqa: E501
                expose=rde_1_x_entity.spec.expose)
            rde_2_entity = cls(metadata=metadata,
                               spec=spec,
                               status=status,
                               kind=rde_1_x_entity.kind,
                               api_version=rde_constants.PAYLOAD_VERSION_2_0)
            return rde_2_entity

    @classmethod
    def from_cluster_data(cls, cluster: dict, kind: str, **kwargs):
        """Construct rde_2.0.0 native entity from non-rde cluster.

        :param dict cluster: cluster metadata
        :param str kind: cluster kind
        :return: native entity
        :rtype: rde_2.0.0.NativeEntity
        """
        site = kwargs.get('site', '')
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

        cloud_properties = CloudProperties(site=site,
                                           org_name=cluster['org_name'],
                                           virtual_data_center_name=cluster['vdc_name'],  # noqa: E501
                                           ovdc_network_name=cluster['network_name'],  # noqa: E501
                                           distribution=k8_distribution,
                                           ssh_key='')
        topology = Topology(
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
            )
        )
        cluster_entity = cls(
            kind=kind,
            spec=ClusterSpec(
                topology=topology,
                settings=Settings(
                    network=cluster['network_name'],
                    ssh_key=""
                ),
                distribution=k8_distribution
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
                uid=cluster['cluster_id'],
                cloud_properties=cloud_properties
            ),
            metadata=Metadata(
                site=site,
                org_name=cluster['org_name'],
                virtual_data_center_name=cluster['vdc_name'],
                name=cluster['name']
            ),
            api_version=rde_constants.PAYLOAD_VERSION_2_0
        )
        return cluster_entity

    @classmethod
    def sample_native_entity(cls, k8_runtime: str = shared_constants.ClusterEntityKind.NATIVE.value):  # noqa: E501
        metadata = Metadata('cluster_name', 'organization_name',
                            'org_virtual_data_center_name', 'VCD_site')
        status = Status()
        settings = Settings(ovdc_network='ovdc_network_name', ssh_key=None)
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

        topology = Topology(
            control_plane=control_plane,
            workers=workers,
            nfs=nfs
        )

        cluster_spec = ClusterSpec(
            topology=topology,
            distribution=k8_distribution,
            settings=settings,
        )

        return NativeEntity(api_version=rde_constants.PAYLOAD_VERSION_2_0,
                            metadata=metadata,
                            spec=cluster_spec,
                            status=status,
                            kind=k8_runtime)
