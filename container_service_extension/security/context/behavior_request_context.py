# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass
from typing import Dict
from typing import Optional

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
    behavior_id: Optional[str] = None
    task_id: Optional[str] = None
    entity_id: Optional[str] = None
    entity: Optional[str] = None
    entity_type_id: Optional[str] = None
    payload: Optional[str] = None
    api_version: Optional[str] = None
    request_id: Optional[str] = None
    op_ctx: Optional[OperationContext] = None
    user_context: Optional[BehaviorUserContext] = None
    mqtt_publisher: Optional[MQTTPublisher] = None
    arguments: Optional[Dict[str, str]] = None
