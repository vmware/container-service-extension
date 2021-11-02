# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.de_cluster import DECluster
from container_service_extension.client.de_cluster_native import DEClusterNative  # noqa: E501
from container_service_extension.client.de_cluster_tkg_s import DEClusterTKGS
from container_service_extension.client.legacy_cluster_native import LegacyClusterNative  # noqa: E501
from container_service_extension.common.constants.shared_constants import ClusterEntityKind  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_SERVER_RUNTIMES  # noqa: E501


class Cluster:
    """Returns the cluster class as determined by API version."""

    def __new__(cls, client: vcd_client.Client, k8_runtime=None):
        """Create the right cluster class for the negotiated API version.

        In case of ApiVersion.VERSION_35, return specific instance if the
        cluster kind is known up-front.

        If the cluster entity kind is unknown, return instance of
        DefEntityCluster for all common operations like get_cluster_info(),
        list_clusters()

        :param pyvcloud.vcd.client client: vcd client

        :return: instance of version specific client side cluster
        """
        api_version = client.get_vcd_api_version()
        if api_version < vcd_client.VcdApiVersionObj.VERSION_35.value:
            return LegacyClusterNative(client)
        elif api_version >= vcd_client.VcdApiVersionObj.VERSION_35.value:
            if k8_runtime in CSE_SERVER_RUNTIMES:
                return DEClusterNative(client)
            elif k8_runtime == ClusterEntityKind.TKG_S.value:
                return DEClusterTKGS(client)
            else:
                return DECluster(client)
