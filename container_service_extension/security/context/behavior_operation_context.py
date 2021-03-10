# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass

from container_service_extension.security.context.operation_context import OperationContext  # noqa: E501


@dataclass(frozen=True)
class BehaviorUserContext:
    userId: str
    orgId: str
    rights: list


@dataclass(frozen=True)
class BehaviorOperationContext:
    behavior_id: str
    task_id: str
    entity_id: str
    entity: dict
    entity_type_id: str
    payload: dict
    api_version: str
    request_id: str
    op_ctx: OperationContext
    user_context: BehaviorUserContext
