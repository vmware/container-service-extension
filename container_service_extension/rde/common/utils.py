# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.rde.backend.cluster_service_factory as cluster_service_factory  # noqa: E501
import container_service_extension.security.context.operation_context as ctx


def get_runtime_cluster_service(op_ctx: ctx.OperationContext):
    rde_in_use = server_utils.get_rde_version_in_use()
    return cluster_service_factory.ClusterServiceFactory(op_ctx).get_cluster_service(rde_in_use)  # noqa: E501
