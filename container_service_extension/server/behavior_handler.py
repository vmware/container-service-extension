from container_service_extension.security.context.behavior_operation_context import \
    BehaviorOperationContext


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

