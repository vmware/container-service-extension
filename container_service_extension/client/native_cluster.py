# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException

from container_service_extension.client.def_entity_cluster import DefEntityCluster  # noqa: E501
from container_service_extension.def_ import models as models


class NativeCluster(DefEntityCluster):
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param
        cluster resize where cluster kind specified as CLI param

    """

    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse/internal'

    def create_cluster(self, cluster_entity: models.ClusterEntity):
        """Create a new Kubernetes cluster.

        :param models.ClusterEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)

    def resize_cluster(self, cluster_entity: models.ClusterEntity):
        """Resize the existing Kubernetes cluster.

        :param models.ClusterEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)

    def apply(self, cluster_config_file_path):
        uri = f"{self._uri}/clusters"
        msg = f"Operation not supported; Implementation in progress for {uri}"
        raise(OperationNotSupportedException(msg))

    def __getattr__(self, name):
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)
