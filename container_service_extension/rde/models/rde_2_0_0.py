# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import List

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0


@dataclass()
class Metadata:
    name: str
    orgName: str
    ovdcName: str
    site: str


@dataclass()
class Nfs:
    sizingClass: str = None
    storageProfile: str = None
    count: int = 0


@dataclass()
class ControlPlane:
    sizingClass: str = None
    storageProfile: str = None
    count: int = 1


@dataclass()
class Workers:
    sizingClass: str = None
    storageProfile: str = None
    count: int = 0


@dataclass()
class Distribution:
    templateName: str = ""
    templateRevision: int = 0

    def __init__(self, templateName: str = '', templateRevision: int = 0, **kwargs):  # noqa: E501
        self.templateName = templateName
        self.templateRevision = templateRevision


@dataclass()
class Settings:
    network: str
    sshKey: str = None
    rollbackOnFailure: bool = True


@dataclass()
class Node:
    name: str
    ip: str
    sizingClass: str = None
    storageProfile: str = None


@dataclass()
class NfsNode(Node):
    exports: list = None


@dataclass()
class Nodes:
    controlPlane: Node = None
    workers: List[Node] = None
    nfs: List[NfsNode] = None

    def __init__(self, controlPlane: Node = None, workers: List[Node] = None,
                 nfs: List[Node] = None, **kwargs):
        self.controlPlane = Node(**controlPlane) if isinstance(controlPlane, dict) else controlPlane  # noqa: E501
        self.workers = [Node(**w) if isinstance(w, dict) else w for w in workers]  # noqa: E501
        self.nfs = [NfsNode(**n) if isinstance(n, dict) else n for n in nfs]


@dataclass()
class CloudProperties:
    site: str = None
    orgName: str = None
    ovdcName: str = None
    ovdcNetworkName: str = None
    k8Distribution: Distribution = None
    sshKey: str = None  # TODO contemplate the need to keep this attribute
    rollbackOnFailure: bool = True

    def __init__(self, site: str = None, orgName: str = None,
                 ovdcName: str = None, ovdcNetworkName: str = None,  # noqa: E501
                 k8Distribution: Distribution = None, sshKey: str = None,
                 rollbackOnFailure: bool = True, **kwargs):
        self.site = site
        self.orgName = orgName
        self.ovdcName = ovdcName
        self.ovdcNetworkName = ovdcNetworkName
        self.k8Distribution = Distribution(**k8Distribution) \
            if isinstance(k8Distribution, dict) else k8Distribution or Distribution()  # noqa: E501
        self.sshKey = sshKey
        self.rollbackOnFailure = rollbackOnFailure


@dataclass()
class Status:
    phase: str = None
    cni: str = None
    taskHref: str = None
    kubernetes: str = None
    dockerVersion: str = None
    os: str = None
    nodes: Nodes = None
    uid: str = None
    cloudProperties: CloudProperties = None

    def __init__(self, phase: str = None,
                 cni: str = None, taskHref: str = None,
                 kubernetes: str = None, dockerVersion: str = None,
                 os: str = None, nodes: Nodes = None, uid: str = None,
                 cloudProperties: CloudProperties = None, **kwargs):
        self.phase = phase
        self.cni = cni
        self.taskHref = taskHref
        self.kubernetes = kubernetes
        self.dockerVersion = dockerVersion
        self.os = os
        self.nodes = Nodes(**nodes) if isinstance(nodes, dict) else nodes
        self.uid = uid
        self.cloudProperties = CloudProperties(
            **cloudProperties) if isinstance(cloudProperties, dict) \
            else cloudProperties or CloudProperties()


@dataclass()
class ClusterSpec:
    """Represents the cluster spec.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    controlPlane: ControlPlane
    workers: Workers
    nfs: Nfs
    k8Distribution: Distribution
    settings: Settings

    def __init__(self, settings: Settings, k8Distribution: Distribution = None,
                 controlPlane: ControlPlane = None, workers: Workers = None,
                 nfs: Nfs = None, **kwargs):
        self.settings = Settings(**settings) \
            if isinstance(settings, dict) else settings
        self.controlPlane = ControlPlane(**controlPlane) \
            if isinstance(controlPlane, dict) else controlPlane or ControlPlane()  # noqa: E501
        self.workers = Workers(**workers) \
            if isinstance(workers, dict) else workers or Workers()
        self.nfs = Nfs(**nfs) if isinstance(nfs, dict) else nfs or Nfs()
        self.k8Distribution = Distribution(**k8Distribution) \
            if isinstance(k8Distribution, dict) else k8Distribution or Distribution()  # noqa: E501


@dataclass()
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
            "settings": {
                "network": "net",
                "sshKey": null,
                "rollbackOnFailure": true
            },
            "k8Distribution": {
                "templateName": "k81.17",
                "templateRevision": 1
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
    apiVersion: str
    status: Status = Status()
    kind: str = shared_constants.ClusterEntityKind.NATIVE.value

    def __init__(self, metadata: Metadata, spec: ClusterSpec, apiVersion: str,
                 status=Status(),
                 kind: str = shared_constants.ClusterEntityKind.NATIVE.value,
                 **kwargs):

        self.metadata = Metadata(**metadata) \
            if isinstance(metadata, dict) else metadata
        self.spec = ClusterSpec(**spec) if isinstance(spec, dict) else spec
        self.status = Status(**status) if isinstance(status, dict) else status
        self.kind = kind
        self.apiVersion = apiVersion

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

            # NOTE: since details for the field `site` is not present in
            # RDE 1.0, it is left empty
            cloud_properties = CloudProperties(site=None,
                                               orgName=rde_1_x_entity.metadata.org_name,  # noqa: E501
                                               ovdcName=rde_1_x_entity.metadata.ovdc_name,  # noqa: E501
                                               ovdcNetworkName=rde_1_x_entity.spec.settings.network,  # noqa: E501
                                               k8Distribution=rde_1_x_entity.spec.k8_distribution,  # noqa: E501
                                               sshKey=rde_1_x_entity.spec.settings.ssh_key,  # noqa: E501
                                               rollbackOnFailure=rde_1_x_entity.spec.settings.rollback_on_failure)  # noqa: E501
            # NOTE: since details for the field `uid` is not present in
            # RDE 1.0, it is left empty.
            # Proper value for `uid` should be populated after RDE is converted
            # as `uid` is a required property in Status for RDE 2.0
            status = Status(phase=rde_1_x_entity.status.phase,
                            cni=rde_1_x_entity.status.cni,
                            taskHref=rde_1_x_entity.status.task_href,
                            kubernetes=rde_1_x_entity.status.kubernetes,
                            dockerVersion=rde_1_x_entity.status.docker_version,  # noqa: E501
                            os=rde_1_x_entity.status.os,
                            nodes=rde_1_x_entity.status.nodes,
                            uid=None,
                            cloudProperties=cloud_properties)
            # NOTE: since details for the field `site` is not present in
            # RDE 1.0, it is left empty.
            # Proper value for `site` should be populated after RDE is
            # converted as `site` is a required property in Metadata
            # for RDE 2.0
            metadata = Metadata(name=rde_1_x_entity.metadata.cluster_name,
                                orgName=rde_1_x_entity.metadata.org_name,
                                ovdcName=rde_1_x_entity.metadata.ovdc_name,
                                site='')
            spec = ClusterSpec(
                settings=Settings(
                    network=rde_1_x_entity.spec.settings.network,
                    sshKey=rde_1_x_entity.spec.settings.ssh_key,
                    rollbackOnFailure=rde_1_x_entity.spec.settings.rollback_on_failure),  # noqa: E501,
                controlPlane=ControlPlane(
                    sizingClass=rde_1_x_entity.spec.control_plane.sizing_class,
                    storageProfile=rde_1_x_entity.spec.control_plane.storage_profile,  # noqa: E501
                    count=rde_1_x_entity.spec.control_plane.count),
                workers=Workers(
                    sizingClass=rde_1_x_entity.spec.workers.sizing_class,
                    storageProfile=rde_1_x_entity.spec.workers.storage_profile,
                    count=rde_1_x_entity.spec.workers.count),
                nfs=Nfs(
                    sizingClass=rde_1_x_entity.spec.nfs.sizing_class,
                    storageProfile=rde_1_x_entity.spec.nfs.storage_profile,
                    count=rde_1_x_entity.spec.nfs.count),
                k8Distribution=Distribution(
                    templateName=rde_1_x_entity.spec.k8_distribution.template_name,  # noqa: E501
                    templateRevision=rde_1_x_entity.spec.k8_distribution.template_revision))  # noqa: E501
            rde_2_entity = cls(metadata=metadata,
                               spec=spec,
                               status=status,
                               kind=rde_1_x_entity.kind,
                               apiVersion=rde_constants.PAYLOAD_VERSION_2_0)
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
            templateName=cluster['template_name'],
            templateRevision=int(cluster['template_revision']))

        cloud_properties = CloudProperties(site=site,
                                           orgName=cluster['org_name'],
                                           ovdcName=cluster['vdc_name'],
                                           ovdcNetworkName=cluster['network_name'],  # noqa: E501
                                           k8Distribution=k8_distribution,
                                           sshKey='')
        cluster_entity = cls(
            kind=kind,
            spec=ClusterSpec(
                workers=Workers(
                    count=len(cluster['nodes']),
                    storageProfile=cluster['storage_profile_name']
                ),
                controlPlane=ControlPlane(
                    count=len(cluster['master_nodes']),
                    storageProfile=cluster['storage_profile_name']
                ),
                nfs=Nfs(
                    count=len(cluster['nfs_nodes']),
                    storageProfile=cluster['storage_profile_name']
                ),
                settings=Settings(
                    network=cluster['network_name'],
                    sshKey=""
                ),
                k8Distribution=k8_distribution
            ),
            status=Status(
                phase=str(server_constants.DefEntityPhase(
                    server_constants.DefEntityOperation.CREATE,
                    server_constants.DefEntityOperationStatus.SUCCEEDED)
                ),
                kubernetes=f"{cluster['kubernetes']} {cluster['kubernetes_version']}", # noqa: E501
                cni=f"{cluster['cni']} {cluster['cni_version']}",
                os=cluster['os'],
                dockerVersion=cluster['docker_version'],
                nodes=Nodes(
                    controlPlane=Node(
                        name=cluster['master_nodes'][0]['name'],
                        ip=cluster['master_nodes'][0]['ipAddress']),
                    workers=worker_nodes,
                    nfs=nfs_nodes
                ),
                uid=cluster['cluster_id'],
                cloudProperties=cloud_properties
            ),
            metadata=Metadata(
                site=site,
                orgName=cluster['org_name'],
                ovdcName=cluster['vdc_name'],
                name=cluster['name']
            ),
            apiVersion=rde_constants.PAYLOAD_VERSION_2_0
        )
        return cluster_entity

    def get_latest_task_href(self):
        return self.status.taskHref

    @classmethod
    def sample_native_entity(cls, k8_runtime: str = shared_constants.ClusterEntityKind.NATIVE.value):  # noqa: E501
        metadata = Metadata('cluster_name', 'organization_name',
                            'org_virtual_datacenter_name', 'VCD_site')
        status = Status()
        settings = Settings(network='ovdc_network_name', sshKey=None)
        k8_distribution = Distribution(
            templateName='ubuntu-16.04_k8-1.17_weave-2.6.0',
            templateRevision=2
        )
        control_plane = ControlPlane(
            count=1,
            sizingClass='Large_sizing_policy_name',
            storageProfile='Gold_storage_profile_name'
        )
        workers = Workers(
            count=2,
            sizingClass='Medium_sizing_policy_name',
            storageProfile='Silver_storage_profile'
        )

        nfs = Nfs(
            count=0,
            sizingClass='Large_sizing_policy_name',
            storageProfile='Platinum_storage_profile_name'
        )

        cluster_spec = ClusterSpec(
            controlPlane=control_plane,
            k8Distribution=k8_distribution,
            settings=settings,
            workers=workers,
            nfs=nfs
        )

        return NativeEntity(apiVersion=rde_constants.PAYLOAD_VERSION_2_0,
                            metadata=metadata,
                            spec=cluster_spec,
                            status=status,
                            kind=k8_runtime)
