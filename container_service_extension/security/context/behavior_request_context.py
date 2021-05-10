# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import Union

from container_service_extension.mqi.consumer.mqtt_publisher import \
    MQTTPublisher
from container_service_extension.security.context.operation_context import OperationContext  # noqa: E501


@dataclass(frozen=True)
class BehaviorUserContext:
    userId: str
    orgId: str
    rights: list


@dataclass(frozen=True)
class RequestContext:
    behavior_id: Union[str, None]
    task_id: Union[str, None]
    entity_id: Union[str, None]
    entity: Union[str, None]
    entity_type_id: Union[str, None]
    payload: Union[str, None]
    api_version: Union[str, None]
    request_id: Union[str, None]
    op_ctx: OperationContext
    user_context: Union[BehaviorUserContext, None]
    mqtt_publisher: Union[MQTTPublisher, None]
