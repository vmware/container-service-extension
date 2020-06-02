# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.def_cluster import DefCluster
from container_service_extension.client.native_cluster import NativeCluster
from container_service_extension.client.utils import ApiVersion


API_VERSION_TO_CLUSTER_CLASS = {
    vcd_client.ApiVersion.VERSION_33.value: NativeCluster,
    ApiVersion.VERSION_34: NativeCluster,
    ApiVersion.VERSION_35: DefCluster  # TODO(): use pyvcloud constant
}


class Cluster:
    """Returns the cluster class that is determined by API version."""

    def __new__(cls, client: vcd_client):
        """Create the right cluster class for the negotiated API version.

        :param pyvcloud.vcd.client client: vcd client
        :return: instance of version specific client side cluster
        """
        cluster_class = API_VERSION_TO_CLUSTER_CLASS.get(client.get_api_version())  # noqa: E501
        if cluster_class:
            return cluster_class(client)

        # Defaults to native cluster
        return NativeCluster(client)
