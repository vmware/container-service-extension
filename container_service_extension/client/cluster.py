# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.def_entity_cluster_api import DefEntityClusterApi # noqa: E501
from container_service_extension.client.legacy_native_cluster_api import LegacyNativeClusterApi  # noqa: E501
from container_service_extension.client.native_cluster_api import NativeClusterApi  # noqa: E501
from container_service_extension.client.tkg_cluster_api import TKGClusterApi
from container_service_extension.def_.utils import ClusterEntityKind   # noqa: E501


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
        :param dict cluster_config: cluster configuration
        :return: instance of version specific client side cluster
        """
        api_version = client.get_api_version()
        if float(api_version) < float(vcd_client.ApiVersion.VERSION_35.value):   # noqa: E501
            return LegacyNativeClusterApi(client)
        elif float(api_version) >= float(vcd_client.ApiVersion.VERSION_35.value):  # noqa: E501
            if k8_runtime == ClusterEntityKind.NATIVE.value or k8_runtime == ClusterEntityKind.TANZU_PLUS.value:  # noqa: E501
                return NativeClusterApi(client)
            elif k8_runtime == ClusterEntityKind.TKG.value:
                return TKGClusterApi(client)
            else:
                return DefEntityClusterApi(client)
