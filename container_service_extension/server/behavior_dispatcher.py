# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
import json

from container_service_extension.rde.behaviors.behavior_model import \
    BehaviorErrorPayload, BehaviorOperation
from container_service_extension.security.context.behavior_operation_context \
    import BehaviorOperationContext, BehaviorUserContext
from container_service_extension.security.context.operation_context import OperationContext  # noqa: E501
import container_service_extension.server.behavior_handler as handler


MAP_BEHAVIOR_ID_TO_HANDLER_METHOD = {
    BehaviorOperation.CREATE_CLUSTER.value.id: handler.create_cluster,
    BehaviorOperation.UPDATE_CLUSTER.value.id: handler.update_cluster,
    BehaviorOperation.DELETE_CLUSTER.value.id: handler.delete_cluster,
    BehaviorOperation.GET_KUBE_CONFIG.value.id: handler.get_kubeconfig
}


def process_behavior_request(msg_json):
    # Extracting contents from headers
    task_id: str = msg_json['headers']['taskId']
    entity_id: str = msg_json['headers']['entityId']
    behavior_id: str = msg_json['headers']['behaviorId']
    usr_ctx: BehaviorUserContext = BehaviorUserContext(**msg_json['headers']['context'])  # noqa: E501

    # Extracting contents from the input payload
    payload: dict = json.loads(msg_json['payload'])
    entity: dict = payload['entity']
    entity_type_id: str = payload['typeId']
    api_version: str = payload['_metadata']['apiVersion']
    auth_token: str = payload['_metadata']['actAsToken']
    request_id: str = payload['_metadata']['requestId']

    # Initializing Behavior operation context
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

    # Invoke the handler method.
    response_payload = MAP_BEHAVIOR_ID_TO_HANDLER_METHOD[behavior_id](behavior_ctx)  # noqa: E501
    if isinstance(response_payload, BehaviorErrorPayload):
        return 'error', json.dumps(asdict(response_payload))
    else:
        return 'success', response_payload
