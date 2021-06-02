# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.de_cluster import DECluster
from container_service_extension.client.de_cluster_native import DEClusterNative  # noqa: E501
from container_service_extension.client.de_cluster_tkg import DEClusterTKG
from container_service_extension.client.legacy_cluster_native import LegacyClusterNative  # noqa: E501
from container_service_extension.shared_constants import ClusterEntityKind


class Cluster:
    """Returns the cluster class as determined by API version."""

    def __new__(cls, client: vcd_client, k8_runtime=None):
        """Create the right cluster class for the negotiated API version.

        In case of ApiVersion.VERSION_35, return specific instance if the
        cluster kind is known up-front.

        If the cluster entity kind is unknown, return instance of
        DefEntityCluster for all common operations like get_cluster_info(),
        list_clusters()

        :param pyvcloud.vcd.client client: vcd client
        :param str k8_runtime:

        :return: instance of version specific client side cluster
        """
        api_version = client.get_api_version()
        if float(api_version) < float(vcd_client.ApiVersion.VERSION_35.value):   # noqa: E501
            return LegacyClusterNative(client)
        elif float(api_version) >= float(vcd_client.ApiVersion.VERSION_35.value):  # noqa: E501
            if k8_runtime in [ClusterEntityKind.NATIVE.value, ClusterEntityKind.TKG_PLUS.value, ClusterEntityKind.TKG_M.value]:  # noqa: E501
                return DEClusterNative(client)
            elif k8_runtime == ClusterEntityKind.TKG.value:
                return DEClusterTKG(client)
            else:
                return DECluster(client)
