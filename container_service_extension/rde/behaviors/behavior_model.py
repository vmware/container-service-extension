# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from enum import Enum
from enum import unique

from container_service_extension.common.constants.server_constants import AclAccessLevelId, ExtensionType, MQTT_EXTENSION_URN   # noqa: E501

KUBE_CONFIG_BEHAVIOR_INTERFACE_ID = 'urn:vcloud:behavior-interface:createKubeConfig:vmware:k8s:1.0.0'  # noqa: E501
KUBE_CONFIG_BEHAVIOR_INTERFACE_NAME = 'createKubeConfig'


@dataclass()
class ExecutionProperties:
    serviceId: str = MQTT_EXTENSION_URN
    # TODO Remove this property once Extensibility team sets the default value.
    invocation_timeout: int = 216000

    def __init__(self, serviceId: str = MQTT_EXTENSION_URN,
                 invocation_timeout: int = 216000, **kwargs):
        self.serviceId = serviceId
        self.invocation_timeout = invocation_timeout


@dataclass
class Execution:
    id: str
    type: str = ExtensionType.MQTT.value
    execution_properties: ExecutionProperties = ExecutionProperties()

    def __init__(self, id: str, type: str = ExtensionType.MQTT.value,
                 execution_properties: ExecutionProperties = ExecutionProperties(), **kwargs):  # noqa: E501
        self.id = id
        self.type = type
        self.execution_properties = \
            ExecutionProperties(**execution_properties)\
            if isinstance(execution_properties, dict) else execution_properties


@dataclass
class Behavior:
    name: str
    description: str = None
    id: str = None
    ref: str = None
    execution: Execution = None

    def __init__(self, name: str, description: str = None, id: str = None,
                 ref: str = None, execution: Execution = None, **kwargs):
        self.name = name
        self.description = description
        self.id = id
        self.ref = ref
        if execution:
            self.execution = Execution(**execution) if isinstance(execution, dict) else execution  # noqa: E501
        else:
            self.execution = Execution(name)


@dataclass
class BehaviorAclEntry:
    behaviorId: str
    accessLevelId: AclAccessLevelId


@unique
class BehaviorOperation(Behavior, Enum):
    CREATE_CLUSTER = Behavior(name='Create_cluster', description='Creates native cluster')  # noqa: E501
    UPDATE_CLUSTER = Behavior(name='Update_cluster', description='Updates native cluster')  # noqa: E501
    DELETE_CLUSTER = Behavior(name='Delete_cluster', description='Deletes native cluster')  # noqa: E501
    GET_KUBE_CONFIG = Behavior(name=KUBE_CONFIG_BEHAVIOR_INTERFACE_NAME,
                               id=KUBE_CONFIG_BEHAVIOR_INTERFACE_ID)

