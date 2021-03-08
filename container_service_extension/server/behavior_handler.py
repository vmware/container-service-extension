# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

# from container_service_extension.rde.behaviors.behavior_model import BehaviorErrorPayload  # noqa: E501
from container_service_extension.security.context.behavior_operation_context import BehaviorOperationContext  # noqa: E501


# Responsibility of the functions in this file:
# 1. Validate the Input payload based on the (api_version, BehaviorOperation, payload_version).  # noqa: E501
# Get the validator based on the api_version and payload_version.
# 2. Based on the rde_in_use, convert the entity if necessary
# 3. Based on the rde_in_use, call the appropriate backend method.
# 4. Return the HTTP equivalent return code(s) to indicate the success (or)
# failure.

# As of today (Mar 8, 2021), we do not anticipate the need to maintain
# multiple handlers based on api_version. This can be evaluated on the need basis.  # noqa: E501

def create_cluster(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='400',
    #                                 minorErrorCode='Input validation failed',
    #                                 message='Input RDE version 1.0 is not supported at api_version 36')  # noqa: E501
    return "Cluster creation successful"


def update_cluster(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='500',
    #                                 minorErrorCode='Cluster initialization failed',  # noqa: E501
    #                                 message='Cluster initialization failed')
    return "Cluster update successful."


def delete_cluster(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='500',
    #                                 minorErrorCode='vApp does not exist',
    #                                 message='vApp does not exist')
    return "Successfully deleted the cluster."


def get_kubeconfig(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='500',
    #                                 minorErrorCode='Cannot reach the cluster',  # noqa: E501
    #                                 message='Cannot reach the cluster')
    return "Returning the kubeconfig"
