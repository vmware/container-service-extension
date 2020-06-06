# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.def_entity_cluster import DefEntityCluster # noqa: E501
from container_service_extension.client.def_native_cluster import DefNativeCluster  # noqa: E501
from container_service_extension.client.native_cluster import NativeCluster
from container_service_extension.client.utils import ApiVersion
from container_service_extension.client.utils import ClusterKind
from container_service_extension.client.vsphere_kubernetes import VsphereKubernetes  # noqa: E501


# TODO(): use pyvcloud constant
API_VERSION_TO_CLUSTER_CLASS = {
    vcd_client.ApiVersion.VERSION_33.value: {
        ClusterKind.NATIVE: NativeCluster,
        None: NativeCluster
    },
    ApiVersion.VERSION_34: {
        ClusterKind.NATIVE: NativeCluster,
        None: NativeCluster
    },
    ApiVersion.VERSION_35: {
        ClusterKind.NATIVE: DefNativeCluster,
        ClusterKind.VSPHERE_K8: VsphereKubernetes,
        None: DefEntityCluster  # common handler where cluster kind is not known  # noqa: E501
    }
}


class Cluster:
    """Returns the cluster class as determined by API version."""

    def __new__(cls, client: vcd_client, cluster_kind=None):
        """Create the right cluster class for the negotiated API version.

        :param pyvcloud.vcd.client client: vcd client
        :return: instance of version specific client side cluster
        """
        cluster_class = API_VERSION_TO_CLUSTER_CLASS.get(client.get_api_version(), {}).get(cluster_kind)  # noqa: E501
        return cluster_class(client)
