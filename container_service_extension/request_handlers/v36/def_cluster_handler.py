# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict

import container_service_extension.def_.cluster_service as cluster_svc
import container_service_extension.def_.models as def_models
import container_service_extension.operation_context as ctx
import container_service_extension.request_handlers.request_utils as request_utils  # noqa: E501
from container_service_extension.shared_constants import RequestKey
import container_service_extension.telemetry.constants as telemetry_constants
import container_service_extension.telemetry.telemetry_handler as telemetry_handler  # noqa: E501


@telemetry_handler.record_user_action_telemetry(cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_UPDATE)  # noqa: E501
@request_utils.v35_api_exception_handler
def cluster_update(data: dict, op_ctx: ctx.OperationContext):
    """Request handler for cluster resize operation.

    Validate data before actual resize is delegated to cluster service.

    :return: Defined entity of the native cluster
    :rtype: container_service_extension.def_.models.DefEntity
    """
    svc = cluster_svc.ClusterService(op_ctx)
    cluster_id = data[RequestKey.CLUSTER_ID]
    cluster_entity_spec = def_models.NativeEntity(**data[RequestKey.INPUT_SPEC])  # noqa: E501
    curr_entity = svc.entity_svc.get_entity(cluster_id)
    is_upgrade_operation = \
        request_utils.validate_cluster_update_request_and_check_cluster_upgrade(  # noqa: E501
            asdict(cluster_entity_spec.spec), asdict(curr_entity.entity.spec))
    if is_upgrade_operation:
        return asdict(svc.upgrade_cluster(cluster_id, cluster_entity_spec))
    return asdict(svc.resize_cluster(cluster_id, cluster_entity_spec))
