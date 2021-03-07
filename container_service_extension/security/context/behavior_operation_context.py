from dataclasses import dataclass

from container_service_extension.rde.models.abstractNativeEntity import \
    AbstractNativeEntity
from container_service_extension.security.context.operation_context import \
    OperationContext


@dataclass
class UserContext:
    userId: str
    orgId: str
    rights: list


@dataclass(frozen=True)
class BehaviorOperationContext:
    behavior_id: str
    task_id: str
    entity_id: str
    entity: AbstractNativeEntity
    entity_type_id: str
    user_context: UserContext
    payload: dict
    api_version: str
    request_id: str
    op_ctx: OperationContext





