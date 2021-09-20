# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import semantic_version

from container_service_extension.common.constants.shared_constants import ClusterEntityKind  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
from container_service_extension.rde.backend.cluster_service_1_x import ClusterService as ClusterService1X  # noqa: E501
from container_service_extension.rde.backend.cluster_service_2_x import ClusterService as ClusterService2X  # noqa: E501
from container_service_extension.rde.backend.cluster_service_2_x_tkgm import ClusterService as ClusterService2XTKGm  # noqa: E501
import container_service_extension.rde.common.entity_service as entity_service


class ClusterServiceFactory:
    def __init__(self, req_ctx):  # noqa: E501
        self.req_ctx = req_ctx

    def get_cluster_service(self, rde_version_in_use=None, skip_tkgm_check=False):  # noqa: E501
        """Get the right instance of backend cluster service.

        Factory method to return the ClusterService based on the RDE version in use.
        :param rde_version_in_use (str)
        :param bool skip_tkgm_check: flag specifying not to use TKGm cluster service

        :rtype cluster_service (container_service_extension.server.abstract_broker.AbstractBroker)  # noqa: E501
        """
        if rde_version_in_use is None:
            rde_version_in_use = server_utils.get_rde_version_in_use()
        rde_version: semantic_version.Version = semantic_version.Version(rde_version_in_use)  # noqa: E501
        if rde_version.major == 1:
            return ClusterService1X(op_ctx=self.req_ctx)
        elif rde_version.major == 2:
            entity = self.req_ctx.entity
            if not skip_tkgm_check and entity is None:
                def_entity_svc = entity_service.DefEntityService(self.req_ctx.op_ctx.cloudapi_client)  # noqa: E501
                def_entity = def_entity_svc.get_entity(self.req_ctx.op_ctx.entity_id)  # noqa: E501
                entity = def_entity.entity.to_dict()
            if not skip_tkgm_check and entity.get('kind') == ClusterEntityKind.TKG_M.value:  # noqa: E501
                return ClusterService2XTKGm(self.req_ctx)
            else:
                return ClusterService2X(self.req_ctx)
