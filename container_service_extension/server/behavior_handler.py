# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.security.context.behavior_operation_context import BehaviorOperationContext  # noqa: E501


# Responsibility of the functions in this file:
# 1. Validate the Input payload based on the api_version, BehaviorOperation.
# Get the validator based on the api_version.
# 2. Based on the rde_in_use, convert the entity if necessary
# 3. Based on the rde_in_use, call the appropriate backend method.
# 4. Return the HTTP equivalent return code(s) to indicate the success (or)
# failure. TODO Return codes are yet to be received from Extensibility.

# As of today (Mar 8, 2021), we do not anticipate the need to maintain
# multiple handlers based on api_version. This can be evaluated on the need basis.  # noqa: E501

def create_cluster(behavior_ctx: BehaviorOperationContext):
    entity_id = behavior_ctx.entity_id
    entity = behavior_ctx.entity
    api_version = behavior_ctx.api_version
    # TODO Get validator based on api_version and validate the entity.
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    return "Cluster creation successful."


def update_cluster(behavior_ctx: BehaviorOperationContext):
    entity_id = behavior_ctx.entity_id
    entity = behavior_ctx.entity
    api_version = behavior_ctx.api_version
    # TODO Get validator based on api_version and validate the entity.
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    return "Cluster update successful."


def delete_cluster(behavior_ctx: BehaviorOperationContext):
    entity_id = behavior_ctx.entity_id
    entity = behavior_ctx.entity
    api_version = behavior_ctx.api_version
    # TODO Get validator based on api_version and validate the entity.
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    return "Successfully deleted the cluster."


def get_kubeconfig(behavior_ctx: BehaviorOperationContext):
    entity_id = behavior_ctx.entity_id
    entity = behavior_ctx.entity
    api_version = behavior_ctx.api_version
    # TODO Get validator based on api_version and validate the entity.
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    return "Returning the kubeconfig"

