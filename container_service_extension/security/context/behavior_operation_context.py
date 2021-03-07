from dataclasses import dataclass

from container_service_extension.security.context.operation_context import \
    OperationContext


class BehaviorOperationContext:
    def __init__(self, auth_token, behavior_id, task_id, entity_id, payload,
                 api_version, entity, entity_type_id, user_context, **kwargs):
        self.behavior_id = behavior_id
        self.task_id = task_id
        self.entity_id = entity_id
        self.entity = entity
        self.entity_type_id = entity_type_id
        self.user_context = user_context
        self.payload = payload
        self.api_version = api_version
        self.request_id = kwargs.get('request_id', None)
        self.op_ctx: OperationContext = OperationContext(auth_token=auth_token, is_jwt=True, request_id=self.request_id)

    # TODO Enable only getters.


@dataclass
class UserContext:
    userId: str
    orgId: str
    rights: list


