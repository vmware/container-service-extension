import json

from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation
import container_service_extension.server.behavior_handler as handler
from container_service_extension.security.context.behavior_operation_context import \
    BehaviorOperationContext, UserContext

MAP_BEHAVIOR_ID_TO_HANDLER_METHOD = {
    BehaviorOperation.CREATE_CLUSTER.value.id: handler.create_cluster,
    BehaviorOperation.UPDATE_CLUSTER.value.id: handler.update_cluster,
    BehaviorOperation.DELETE_CLUSTER.value.id: handler.delete_cluster,
    BehaviorOperation.GET_KUBE_CONFIG.value.id: handler.get_kubeconfig
}


def process_request(msg_json):
    task_id: str = msg_json['headers']['taskId']
    entity_id: str = msg_json['headers']['entityId']
    behavior_id: str = msg_json['headers']['behaviorId']
    usr_ctx: UserContext = UserContext(**msg_json['headers']['context'])
    payload: dict = json.loads(msg_json['payload'])
    entity: dict = payload['entity']
    entity_type_id: str = payload['typeId']
    arguments: dict = payload['arguments']
    behavior_ctx = BehaviorOperationContext(auth_token='123',
                                            behavior_id=behavior_id,
                                            task_id=task_id,
                                            entity_id=entity_id,
                                            payload=payload,
                                            api_version='36.0',
                                            entity=entity,
                                            user_context=usr_ctx,
                                            entity_type_id=entity_type_id)
    return MAP_BEHAVIOR_ID_TO_HANDLER_METHOD[behavior_id](behavior_ctx)


