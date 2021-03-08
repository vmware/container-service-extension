# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501
import container_service_extension.server.behavior_handler as handler
from container_service_extension.security.context.behavior_operation_context \
    import BehaviorOperationContext, BehaviorUserContext
from container_service_extension.security.context.operation_context import OperationContext  # noqa: E501

MAP_BEHAVIOR_ID_TO_HANDLER_METHOD = {
    BehaviorOperation.CREATE_CLUSTER.value.id: handler.create_cluster,
    BehaviorOperation.UPDATE_CLUSTER.value.id: handler.update_cluster,
    BehaviorOperation.DELETE_CLUSTER.value.id: handler.delete_cluster,
    BehaviorOperation.GET_KUBE_CONFIG.value.id: handler.get_kubeconfig
}


def process_behavior_request(msg_json):
    task_id: str = msg_json['headers']['taskId']
    entity_id: str = msg_json['headers']['entityId']
    behavior_id: str = msg_json['headers']['behaviorId']
    usr_ctx: BehaviorUserContext = BehaviorUserContext(**msg_json['headers']['context'])  # noqa: E501
    payload: dict = json.loads(msg_json['payload'])
    entity: dict = payload['entity']
    entity_type_id: str = payload['typeId']
    # TODO Below properties are yet to be added by Extensibility team
    auth_token: str = msg_json['headers'].get('auth_token', None)
    api_version: str = msg_json['headers'].get('api_version', None)
    request_id: str = msg_json['headers'].get('request_id', None)
    # arguments: dict = payload['arguments']
    op_ctx = OperationContext(auth_token=auth_token, is_jwt=True, request_id=request_id)  # noqa: E501
    behavior_ctx = BehaviorOperationContext(behavior_id=behavior_id,
                                            task_id=task_id,
                                            entity_id=entity_id,
                                            payload=payload,
                                            api_version=api_version,
                                            entity=entity,
                                            user_context=usr_ctx,
                                            entity_type_id=entity_type_id,
                                            request_id=request_id,
                                            op_ctx=op_ctx)
    return MAP_BEHAVIOR_ID_TO_HANDLER_METHOD[behavior_id](behavior_ctx)


