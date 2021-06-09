# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import dataclasses

import yaml

import container_service_extension.def_.models as def_models
from container_service_extension.logger import CLIENT_LOGGER
import container_service_extension.shared_constants as shared_constants


SAMPLE_K8_CLUSTER_SPEC_HELP = """# Short description of various properties used in this sample cluster configuration
# kind: The kind of the Kubernetes cluster.
#
# metadata: This is a required section
# metadata.cluster_name: Name of the cluster to be created or resized
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
# spec.nfs.sizing_class: The compute sizing policy with which nfs node needs to be provisioned in a given \"ovdc\". The specified sizing policy is expected to be pre-published to the given ovdc.
# spec.nfs.storage_profile: The storage-profile with which nfs needs to be provisioned in a given \"ovdc\". The specified storage-profile is expected to be available on the given ovdc.
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


SAMPLE_TKG_CLUSTER_SPEC_HELP = """# Short description of various properties used in this sample cluster configuration
# kind: The kind of TKG cluster.
#
# metadata: Section for cluster metadata.
# metadata.name: Name of the cluster to be created or resized
# metadata.placementPolicy: Targets where to place this cluster. Note that the placement policy also determines the range of valid values for storage class (see classes and defaultClass below) and virtual hardware settings (see VirtualMachineClass below). Required during create, read-only after.
# metadata.virtualDataCenterName: Cloud Director organization vDC where to place the cluster. Required during create, read-only after.
#
# spec: Section for user specification of the desired state of the cluster
# spec.distribution.version: Kubernetes software distribution version
#
# spec.topology.controlPlane: Required sub-section for desired control-plane state of the cluster. The properties \"class\" and \"StorageClass\" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like \"resize\" and \"upgrade\"
# spec.topology.controlPlane.class: The Kubernetes policy with which control-plane node needs to be provisioned in a given \"ovdc\". The specified sizing policy is expected to be pre-published to the given ovdc.
# spec.topology.controlPlane.count: Number of control plane node(s).
# spec.topology.controlPlane.storageClass: The storage policy with which control-plane needs to be provisioned in a given \"ovdc\". The specified policy is expected to be available on the given ovdc.
#
# spec.topology.workers: Required sub-section for the desired worker state of the cluster. The properties \"class\" and \"storageClass\" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like \"resize\" and \"upgrade\".
# spec.topology.workers.class: The Kubernetes policy with which worker nodes need to be provisioned in a given \"ovdc\". The specified sizing policy is expected to be pre-published to the given ovdc.
# spec.topology.workers.count: number of worker nodes. Worker nodes can be scaled up and down.
# spec.topology.workers.storageClass: The storage policy with which worker nodes need to be provisioned in a given \"ovdc\". The specified policy is expected to be available on the given ovdc.

"""  # noqa: E501


def get_sample_cluster_configuration(output=None, k8_runtime=None):
    """Generate sample cluster configuration.

    :param str output: full path of output file
    :param shared_constants.ClusterEntityKind k8_runtime: cluster kind
    :return: sample cluster configuration
    :rtype: str
    """
    if k8_runtime == shared_constants.ClusterEntityKind.TKG.value:
        sample_cluster_config = SAMPLE_TKG_CLUSTER_SPEC_HELP + _get_sample_tkg_cluster_configuration()  # noqa: E501
    else:
        sample_cluster_config = SAMPLE_K8_CLUSTER_SPEC_HELP + _get_sample_cluster_configuration_by_k8_runtime(k8_runtime)  # noqa: E501

    if output:
        with open(output, 'w') as f:
            f.write(sample_cluster_config)

    return sample_cluster_config


def _get_sample_cluster_configuration_by_k8_runtime(k8_runtime):
    metadata = def_models.Metadata('cluster_name', 'organization_name',
                                   'org_virtual_datacenter_name')
    status = def_models.Status()
    settings = def_models.Settings(network='ovdc_network_name', ssh_key=None)
    k8_distribution = def_models.Distribution(
        template_name='ubuntu-16.04_k8-1.17_weave-2.6.0',
        template_revision=2
    )
    control_plane = def_models.ControlPlane(
        count=1,
        sizing_class='Large_sizing_policy_name',
        storage_profile='Gold_storage_profile_name'
    )
    workers = def_models.Workers(
        count=2,
        sizing_class='Medium_sizing_policy_name',
        storage_profile='Silver_storage_profile'
    )

    nfs = def_models.Nfs(
        count=0,
        sizing_class='Large_sizing_policy_name',
        storage_profile='Platinum_storage_profile_name'
    )

    cluster_spec = def_models.ClusterSpec(
        control_plane=control_plane,
        k8_distribution=k8_distribution,
        settings=settings,
        workers=workers,
        nfs=nfs
    )
    cluster_entity = def_models.NativeEntity(
        metadata=metadata,
        spec=cluster_spec,
        status=status,
        kind=k8_runtime
    )

    sample_cluster_config = yaml.dump(dataclasses.asdict(cluster_entity))
    CLIENT_LOGGER.info(sample_cluster_config)
    return sample_cluster_config


def _get_sample_tkg_cluster_configuration():
    sample_tkg_plus_config = {
        "kind": "TanzuKubernetesCluster",
        "spec": {
            "topology": {
                "workers": {
                    "class": "Gold_storage_profile_name",
                    "count": 1,
                    "storageClass": "development #sample storage class"
                },
                "controlPlane": {
                    "class": "Gold_storage_profile_name",
                    "count": 1,
                    "storageClass": "development"
                }
            },
            "distribution": {
                "version": "v1.16"
            }
        },
        "metadata": {
            "name": "cluster_name",
            "placementPolicy": "placement_policy_name",
            "virtualDataCenterName": "org_virtual_datacenter_name"
        }
    }
    sample_cluster_config = yaml.dump(sample_tkg_plus_config)
    CLIENT_LOGGER.info(sample_cluster_config)
    return sample_cluster_config
