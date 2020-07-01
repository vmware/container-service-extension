# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.def_.utils import ClusterEntityKind   # noqa: E501
from container_service_extension.client.def_entity_cluster import DefEntityCluster # noqa: E501
from container_service_extension.client.legacy_native_cluster import LegacyNativeCluster  # noqa: E501
from container_service_extension.client.native_cluster import NativeCluster  # noqa: E501
from container_service_extension.client.tkg_cluster import TKGCluster


class Cluster:
    """Returns the cluster class as determined by API version."""

    def __new__(cls, client: vcd_client, cluster_config=None):
        """Create the right cluster class for the negotiated API version.

        In case of ApiVersion.VERSION_35, return specific instance if the
        cluster kind is known up-front.

        If the cluster kind is unknown, return instance of DefEntityCluster for
        all common operations like get_cluster_info(), list_clusters()

        :param pyvcloud.vcd.client client: vcd client
        :param dict cluster_config: cluster configuration
        :return: instance of version specific client side cluster
        """
        api_version = client.get_api_version()
        if float(api_version) < float(vcd_client.ApiVersion.VERSION_35.value):   # noqa: E501
            return LegacyNativeCluster(client)
        elif float(api_version) >= float(vcd_client.ApiVersion.VERSION_35.value):  # noqa: E501
            cluster_entity_kind = cluster_config.get('kind')
            if cluster_entity_kind == ClusterEntityKind.NATIVE.value or cluster_entity_kind == ClusterEntityKind.TANZU_PLUS.value:  # noqa: E501
                return NativeCluster(client, cluster_config=cluster_config)
            elif cluster_entity_kind == ClusterEntityKind.TKG.value:
                return TKGCluster(client)
            else:
                return DefEntityCluster(client)
