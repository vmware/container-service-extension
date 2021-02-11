# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import semantic_version

import container_service_extension.security.context.operation_context as ctx


class ClusterServiceFactory:
    def __init__(self, op_ctx: ctx.OperationContext):
        self.op_ctx = op_ctx

    def get_cluster_service(self, rde_version_in_use):
        """Get the right instance of backend cluster service.

        Factory method to return the ClusterService based on the RDE version in use.
        :param rde_version_in_use (str)
        :param op_ctx (container_service_extension.security.context.operation_context.OperationContext)

        :rtype cluster_service (container_service_extension.server.abstract_broker.AbstractBroker)  # noqa: E501
        """
        rde_version: semantic_version.Version = semantic_version.Version(rde_version_in_use)  # noqa: E501
        if rde_version.major == 1:
            from container_service_extension.rde.backend.cluster_service_1_x import ClusterService as ClusterService1X  # noqa: E501
            return ClusterService1X(op_ctx=self.op_ctx)
        elif rde_version.major == 2:
            from container_service_extension.rde.backend.cluster_service_2_x import ClusterService as ClusterService2X  # noqa: E501
            return ClusterService2X(op_ctx=self.op_ctx)
