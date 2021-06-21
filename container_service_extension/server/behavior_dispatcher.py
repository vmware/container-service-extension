# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
import json

from pyvcloud.vcd.client import ApiVersion

from container_service_extension.common.constants.shared_constants import \
    API_VERSION_37_ALPHA
from container_service_extension.exception.exceptions import CseRequestError
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
from container_service_extension.mqi.consumer.mqtt_publisher import \
    MQTTPublisher
from container_service_extension.rde.behaviors.behavior_model import \
    BehaviorError, BehaviorOperation, BehaviorTaskStatus  # noqa: E501
from container_service_extension.security.context.behavior_request_context \
    import BehaviorUserContext, RequestContext
from container_service_extension.security.context.operation_context import OperationContext  # noqa: E501
import container_service_extension.server.behavior_handler as handler


MAP_BEHAVIOR_ID_TO_HANDLER_METHOD = {
    BehaviorOperation.CREATE_CLUSTER.value.id: handler.create_cluster,
    BehaviorOperation.UPDATE_CLUSTER.value.id: handler.update_cluster,
    BehaviorOperation.DELETE_CLUSTER.value.id: handler.delete_cluster,
    BehaviorOperation.GET_KUBE_CONFIG.value.id: handler.get_kubeconfig,
    BehaviorOperation.DELETE_NFS_NODE.value.id: handler.nfs_node_delete
}


def process_behavior_request(msg_json, mqtt_publisher: MQTTPublisher):
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

    # This is needed to enable unified API endpoint workflows. Unified API
    # endpoint is currently exposed at 37.0.0-alpha (VCD 10.3 Andromeda).
    if api_version == API_VERSION_37_ALPHA:
        api_version = ApiVersion.VERSION_36.value
    auth_token: str = payload['_metadata']['actAsToken']
    request_id: str = payload['_metadata']['requestId']
    arguments: dict = payload['arguments']

    # Initializing Behavior operation context
    op_ctx = OperationContext(auth_token=auth_token, is_jwt=True, request_id=request_id)  # noqa: E501
    behavior_ctx = RequestContext(behavior_id=behavior_id,
                                  task_id=task_id,
                                  entity_id=entity_id,
                                  payload=payload,
                                  api_version=float(api_version),
                                  entity=entity,
                                  user_context=usr_ctx,
                                  entity_type_id=entity_type_id,
                                  request_id=request_id,
                                  op_ctx=op_ctx,
                                  mqtt_publisher=mqtt_publisher,
                                  arguments=arguments)

    # Invoke the handler method and return the response in the string format.
    try:
        return MAP_BEHAVIOR_ID_TO_HANDLER_METHOD[behavior_id](behavior_ctx)
    except CseRequestError as e:
        error_details = asdict(BehaviorError(majorErrorCode=e.status_code,
                                             minorErrorCode=e.minor_error_code,
                                             message=e.error_message))
        payload = mqtt_publisher. \
            construct_behavior_payload(status=BehaviorTaskStatus.ERROR.value,
                                       error_details=error_details)
        LOGGER.error(f"Error while executing handler: {error_details}", exc_info=True)  # noqa: E501
        return payload
    except Exception as e:
        error_details = asdict(BehaviorError(majorErrorCode='500',
                                             message=str(e)))
        payload = mqtt_publisher. \
            construct_behavior_payload(status=BehaviorTaskStatus.ERROR.value,
                                       error_details=error_details)
        LOGGER.error(f"Error while executing handler: {error_details}", exc_info=True)  # noqa: E501
        return payload
