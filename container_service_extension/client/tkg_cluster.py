# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException

from container_service_extension.client.def_entity_cluster import DefEntityCluster  # noqa: E501


class TKGCluster(DefEntityCluster):
    """Embedded Kubernetes into vSphere."""

    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/vdc'

    def __getattr__(self, name):
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)
