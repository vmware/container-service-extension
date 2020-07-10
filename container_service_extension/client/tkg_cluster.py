# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException

from container_service_extension.client.def_entity_cluster import DefEntityCluster  # noqa: E501
from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.configuration import Configuration
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster


class TKGCluster(DefEntityCluster):
    """Embedded Kubernetes into vSphere."""

    def __init__(self, client):
        self.client = client


    def __getattr__(self, name):
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)
