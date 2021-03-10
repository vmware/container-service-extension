# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from enum import Enum
from enum import unique

from container_service_extension.common.constants.server_constants import AclAccessLevelId, ExtensionType, MQTT_EXTENSION_URN   # noqa: E501
from container_service_extension.rde.constants import Nss, Vendor

BEHAVIOR_INTERFACE_ID_PREFIX = 'urn:vcloud:behavior-interface'
KUBE_CONFIG_BEHAVIOR_INTERFACE_NAME = 'createKubeConfig'
KUBE_CONFIG_BEHAVIOR_INTERFACE_ID = f"{BEHAVIOR_INTERFACE_ID_PREFIX}:" \
                                    f"{KUBE_CONFIG_BEHAVIOR_INTERFACE_NAME}:" \
                                    f"{Vendor.VMWARE.value}:" \
                                    f"{Nss.KUBERNETES.value}:1.0.0"
CREATE_CLUSTER_BEHAVIOR_NAME = 'createCluster'
CREATE_CLUSTER_BEHAVIOR_INTERFACE_ID = f"{BEHAVIOR_INTERFACE_ID_PREFIX}:" \
                                       f"{CREATE_CLUSTER_BEHAVIOR_NAME}:" \
                                       f"{Vendor.CSE.value}:" \
                                       f"{Nss.KUBERNETES.value}:1.0.0"
UPDATE_CLUSTER_BEHAVIOR_NAME = 'updateCluster'
UPDATE_CLUSTER_BEHAVIOR_INTERFACE_ID = f"{BEHAVIOR_INTERFACE_ID_PREFIX}:" \
                                       f"{UPDATE_CLUSTER_BEHAVIOR_NAME}:" \
                                       f"{Vendor.CSE.value}:" \
                                       f"{Nss.KUBERNETES.value}:1.0.0"
DELETE_CLUSTER_BEHAVIOR_NAME = 'deleteCluster'
DELETE_CLUSTER_BEHAVIOR_INTERFACE_ID = f"{BEHAVIOR_INTERFACE_ID_PREFIX}:" \
                                       f"{DELETE_CLUSTER_BEHAVIOR_NAME}:" \
                                       f"{Vendor.CSE.value}:" \
                                       f"{Nss.KUBERNETES.value}:1.0.0"


@dataclass()
class ExecutionProperties:
    serviceId: str = MQTT_EXTENSION_URN
    # TODO Remove this property once Extensibility team sets the default value.
    invocation_timeout: int = 216000

    def __init__(self, serviceId: str = MQTT_EXTENSION_URN,
                 invocation_timeout: int = 86400, **kwargs):
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
class BehaviorOperation(Enum):
    CREATE_CLUSTER = Behavior(name=CREATE_CLUSTER_BEHAVIOR_NAME,
                              description='Creates native cluster',
                              id=CREATE_CLUSTER_BEHAVIOR_INTERFACE_ID)
    UPDATE_CLUSTER = Behavior(name=UPDATE_CLUSTER_BEHAVIOR_NAME,
                              description='Updates native cluster',
                              id=UPDATE_CLUSTER_BEHAVIOR_INTERFACE_ID)
    DELETE_CLUSTER = Behavior(name=DELETE_CLUSTER_BEHAVIOR_NAME,
                              description='Deletes native cluster',
                              id=DELETE_CLUSTER_BEHAVIOR_INTERFACE_ID)
    GET_KUBE_CONFIG = Behavior(name=KUBE_CONFIG_BEHAVIOR_INTERFACE_NAME,
                               id=KUBE_CONFIG_BEHAVIOR_INTERFACE_ID,
                               ref=KUBE_CONFIG_BEHAVIOR_INTERFACE_ID)


@unique
class BehaviorAcl(Enum):
    CREATE_CLUSTER_ACL = BehaviorAclEntry(CREATE_CLUSTER_BEHAVIOR_INTERFACE_ID,
                                          AclAccessLevelId.AccessLevelReadWrite)  # noqa: E501
    UPDATE_CLUSTER_ACL = BehaviorAclEntry(UPDATE_CLUSTER_BEHAVIOR_INTERFACE_ID,
                                          AclAccessLevelId.AccessLevelReadWrite)  # noqa: E501
    DELETE_CLUSTER_ACL = BehaviorAclEntry(DELETE_CLUSTER_BEHAVIOR_INTERFACE_ID,
                                          AclAccessLevelId.AccessLevelFullControl)  # noqa: E501
    KUBE_CONFIG_ACL = BehaviorAclEntry(KUBE_CONFIG_BEHAVIOR_INTERFACE_ID,
                                       AclAccessLevelId.AccessLevelReadOnly)


@dataclass
class BehaviorErrorPayload:
    majorErrorCode: str = '400'
    minorErrorCode: str = None
    message: str = None
