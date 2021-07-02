# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass
from enum import Enum
from enum import unique
from typing import List, Optional

from dataclasses_json import dataclass_json, Undefined

from container_service_extension.common.constants import shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
from container_service_extension.rde import utils as def_utils
from container_service_extension.rde.behaviors.behavior_model import BehaviorAcl, BehaviorOperation  # noqa: E501
from container_service_extension.rde.constants import \
    DEF_ENTITY_TYPE_ID_PREFIX, DEF_INTERFACE_ID_PREFIX, Nss, RDEMetadataKey, \
    RDEVersion, RuntimeRDEVersion, SchemaFile, Vendor
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
from container_service_extension.rde.models.rde_factory import get_rde_model
from container_service_extension.rde.utils import load_rde_schema


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True)
class DefInterface:
    """Provides interface for the defined entity type."""

    name: str
    id: Optional[str] = None
    readonly: bool = False
    vendor: str = Vendor.CSE.value
    nss: str = Nss.KUBERNETES.value
    version: str = '1.0.0'

    def get_id(self):
        """Get or generate interface id.

        Example: urn:vcloud:interface:cse.native:1.0.0.

        By no means, id generation in this method, guarantees the actual
        interface registration with vCD.
        """
        if self.id is None:
            return def_utils.\
                generate_interface_id(self.vendor, self.nss, self.version)
        else:
            return self.id


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True)
class DefEntityType:
    """Defined Entity type schema for the apiVersion = 35.0."""

    name: str
    description: str
    schema: dict
    interfaces: List[str]
    version: str
    id: Optional[str] = None
    externalId: Optional[str] = None
    readonly: bool = False
    vendor: str = Vendor.CSE.value
    nss: str = Nss.NATIVE_CLUSTER.value

    def get_id(self):
        """Get or generate entity type id.

        Example : "urn:vcloud:interface:cse.native:1.0.0

        By no means, id generation in this method, guarantees the actual
        entity type registration with vCD.
        """
        if self.id is None:
            return def_utils.\
                generate_entity_type_id(self.vendor, self.nss, self.version)
        else:
            return self.id


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True)
class DefEntityType2_0:
    """Defined Entity type schema for the apiVersion = 36.0."""

    name: str
    description: str
    schema: dict
    interfaces: List[str]
    version: str
    id: str = None
    externalId: Optional[str] = None
    readonly: bool = False
    vendor: str = Vendor.CSE.value
    nss: str = Nss.NATIVE_CLUSTER.value
    hooks: dict = None

    def get_id(self):
        """Get or generate entity type id.

        Example : "urn:vcloud:interface:cse.native:1.0.0

        By no means, id generation in this method, guarantees the actual
        entity type registration with vCD.
        """
        if self.id is None:
            return def_utils.\
                generate_entity_type_id(self.vendor, self.nss, self.version)
        else:
            return self.id


@dataclass_json
@dataclass
class Owner:
    name: Optional[str] = None
    id: Optional[str] = None


@dataclass_json
@dataclass
class Org:
    name: Optional[str] = None
    id: Optional[str] = None


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class DefEntity:
    """Represents defined entity instance.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    name: str
    entity: AbstractNativeEntity
    id: Optional[str] = None
    entityType: Optional[str] = None
    externalId: Optional[str] = None
    state: Optional[str] = None
    owner: Optional[Owner] = None
    org: Optional[Org] = None

    def __init__(self, entity: AbstractNativeEntity, entityType: str,
                 name: str = None, id: str = None,
                 externalId: str = None, state: str = None,
                 owner: Owner = None, org: Org = None):
        self.id = id
        self.entityType = entityType

        # Get the entity type version from entity type urn
        entity_type_version = self.entityType.split(":")[-1]
        self.entity = entity
        if isinstance(entity, dict):
            # Parse the entity to the right entity class
            NativeEntityClass = get_rde_model(entity_type_version)
            self.entity = NativeEntityClass.from_dict(entity)

        self.name = name

        if not self.name:
            if entity_type_version == RDEVersion.RDE_1_0_0:
                self.name = self.entity.metadata.cluster_name
            else:
                self.name = self.entity.metadata.name

        self.externalId = externalId
        self.state = state
        self.owner = Owner(**owner) if isinstance(owner, dict) else owner
        self.org = Org(**org) if isinstance(org, dict) else org


@dataclass()
class Ovdc:
    k8s_runtime: List[str]
    ovdc_name: Optional[str] = None
    ovdc_id: Optional[str] = None
    org_name: Optional[str] = None
    remove_cp_from_vms_on_disable: bool = False


@dataclass()
class Tenant:
    name: Optional[str] = None
    id: Optional[str] = None


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=False)
class ClusterAclEntry:
    accessLevelId: Optional[server_constants.AclAccessLevelId] = None
    memberId: Optional[str] = None
    id: Optional[str] = None
    grantType: Optional[str] = None
    objectId: Optional[str] = None
    username: Optional[str] = None
    tenant: Optional[Tenant] = None

    def construct_filtered_dict(self, include=None):
        if include is None:
            include = []
        orig_dict = self.to_dict()
        include_set = set(include)
        filtered_dict = {}
        for key, value in orig_dict.items():
            if key in include_set:
                filtered_dict[key] = value
        return filtered_dict


# NOTE: Only used for cluster list operation to get entities by interface
# include the following properties:
@dataclass()
class GenericClusterEntity:
    # Properties being used for List operation attributes representing them
    # for native and TKG clusters:
    # name:
    #   def_entity.name
    # vdc:
    #   def_entity.entity.metadata.ovdc_name for native
    #   de_entity.entity.metadata.virtualDataCenterName for TKG
    # org:
    #   def_entity.org.name for both native and TKG
    # runtime:
    #   def_entity.entity.kind for both native and TKG
    # version:
    #   def_entity.entity.status.kubernetes for native,
    #   def_entity.entity.spec.distribution.version for TKG
    # status:
    #   def_entity.entity.status.phase for both native and TKG
    # owner:
    #   def_entity.owner.name for both native and TKG
    name: Optional[str] = None
    org: Optional[Org] = None
    entity = None
    owner: Optional[Owner] = None

    def __init__(self, name: str, org: Org, entityType: str, entity,
                 owner: Owner, **kwargs):
        self.name = name
        self.org = Org(**org) if isinstance(org, dict) else org
        self.entityType = entityType
        entity_dict = entity.to_dict() if not isinstance(entity, dict) else entity  # noqa: E501
        if entity_dict['kind'] in \
                [shared_constants.ClusterEntityKind.NATIVE.value,
                 shared_constants.ClusterEntityKind.TKG_PLUS.value]:
            # Get the entity type version from entity type urn
            entity_type_version = self.entityType.split(":")[-1]
            # Parse the entity to the right entity class
            NativeEntityClass = get_rde_model(entity_type_version)
            self.entity: AbstractNativeEntity = \
                NativeEntityClass.from_dict(entity_dict) if isinstance(entity, dict) else entity  # noqa: E501
        elif entity_dict['kind'] == \
                shared_constants.ClusterEntityKind.TKG_S.value:
            self.entity = TKGEntity(**entity) if isinstance(entity, dict) else entity  # noqa: E501
        else:
            raise Exception("Invalid cluster kind")
        self.owner = Owner(**owner) if isinstance(owner, dict) else owner


@dataclass()
class TKGDistribution:
    version: Optional[str] = None

    def __init__(self, version: str, **kwargs):
        self.version = version


@dataclass()
class TKGSpec:
    distribution: Optional[TKGDistribution] = None

    def __init__(self, distribution: TKGDistribution, **kwargs):
        self.distribution = TKGDistribution(**distribution) \
            if isinstance(distribution, dict) else distribution


@dataclass()
class TKGStatus:
    phase: Optional[str] = None

    def __init__(self, phase: str, **kwargs):
        self.phase = phase


@dataclass()
class TKGMetadata:
    virtualDataCenterName: Optional[str] = None

    def __init__(self, virtualDataCenterName: str, **kwargs):
        self.virtualDataCenterName = virtualDataCenterName


@dataclass()
class TKGEntity:
    kind: Optional[str] = None
    spec: Optional[TKGSpec] = None
    status: Optional[TKGStatus] = None
    metadata: Optional[TKGMetadata] = None

    def __init__(self, kind: str, spec: TKGSpec, status: TKGStatus,
                 metadata: TKGMetadata, **kwargs):
        self.kind = kind
        self.spec = TKGSpec(**spec) if isinstance(spec, dict) else spec
        self.status = TKGStatus(**status) \
            if isinstance(status, dict) else status
        self.metadata = TKGMetadata(**metadata) \
            if isinstance(metadata, dict) else metadata


@unique
class K8Interface(Enum):
    VCD_INTERFACE = DefInterface(name='Kubernetes', vendor=Vendor.VMWARE.value,
                                 nss=Nss.KUBERNETES.value, version='1.0.0',
                                 id=f"{DEF_INTERFACE_ID_PREFIX}:{Vendor.VMWARE.value}:{Nss.KUBERNETES.value}:1.0.0")  # noqa: E501
    CSE_INTERFACE = DefInterface(name='CSE_K8s_interface', vendor=Vendor.CSE.value,  # noqa: E501
                                 nss=Nss.KUBERNETES.value, version='1.0.0',
                                 id=f"{DEF_INTERFACE_ID_PREFIX}:{Vendor.CSE.value}:{Nss.KUBERNETES.value}:1.0.0")  # noqa: E501


@unique
class EntityType(Enum):
    NATIVE_ENTITY_TYPE_1_0_0 = DefEntityType(name='nativeClusterEntityType',
                                             id=f"{DEF_ENTITY_TYPE_ID_PREFIX}:{Vendor.CSE.value}:{Nss.NATIVE_CLUSTER}:1.0.0",  # noqa: E501
                                             schema=load_rde_schema(SchemaFile.SCHEMA_1_0_0),  # noqa: E501
                                             interfaces=[K8Interface.VCD_INTERFACE.value.id],  # noqa: E501
                                             version='1.0.0',
                                             vendor=Vendor.CSE.value,
                                             nss=Nss.NATIVE_CLUSTER.value,
                                             description='')
    NATIVE_ENTITY_TYPE_2_0_0 = DefEntityType2_0(name='nativeClusterEntityType',
                                                id=f"{DEF_ENTITY_TYPE_ID_PREFIX}:{Vendor.CSE.value}:{Nss.NATIVE_CLUSTER}:2.0.0",  # noqa: E501
                                                schema=load_rde_schema(SchemaFile.SCHEMA_2_0_0),  # noqa: E501
                                                interfaces=[
                                                    K8Interface.VCD_INTERFACE.value.id,  # noqa: E501
                                                    K8Interface.CSE_INTERFACE.value.id],  # noqa: E501
                                                version='2.0.0',
                                                vendor=Vendor.CSE.value,
                                                nss=Nss.NATIVE_CLUSTER.value,
                                                description='',
                                                hooks={
                                                    'PostCreate': BehaviorOperation.CREATE_CLUSTER.value.id,  # noqa: E501
                                                    'PostUpdate': BehaviorOperation.UPDATE_CLUSTER.value.id,  # noqa: E501
                                                    'PreDelete': BehaviorOperation.DELETE_CLUSTER.value.id}  # noqa: E501
                                                )
    TKG_ENTITY_TYPE_1_0_0 = DefEntityType(name='TKG Cluster',
                                          id=f"{DEF_ENTITY_TYPE_ID_PREFIX}:{Vendor.VMWARE.value}:{Nss.TKG}:1.0.0",  # noqa: E501
                                          schema={},
                                          interfaces=[K8Interface.VCD_INTERFACE.value.id],  # noqa: E501
                                          version='1.0.0',
                                          vendor=Vendor.VMWARE.value,
                                          nss=Nss.TKG.value,
                                          description='')


# Key: Represents the Runtime RDE version used by CSE server for any given environment.  # noqa: E501
# Value: Details about all of the RDE constructs related to the specified RDE version.  # noqa: E501
MAP_RDE_VERSION_TO_ITS_METADATA = {

    RuntimeRDEVersion.RDE_1_X: {
        RDEMetadataKey.INTERFACES: [K8Interface.VCD_INTERFACE.value],
        RDEMetadataKey.ENTITY_TYPE: EntityType.NATIVE_ENTITY_TYPE_1_0_0.value,
    },

    RuntimeRDEVersion.RDE_2_X: {
        RDEMetadataKey.INTERFACES: [K8Interface.VCD_INTERFACE.value,
                                    K8Interface.CSE_INTERFACE.value],
        RDEMetadataKey.ENTITY_TYPE: EntityType.NATIVE_ENTITY_TYPE_2_0_0.value,

        RDEMetadataKey.INTERFACE_TO_BEHAVIORS_MAP: {
            K8Interface.CSE_INTERFACE.value.id:
                [BehaviorOperation.CREATE_CLUSTER.value,
                 BehaviorOperation.UPDATE_CLUSTER.value,
                 BehaviorOperation.DELETE_CLUSTER.value,
                 BehaviorOperation.DELETE_NFS_NODE.value]
        },
        RDEMetadataKey.ENTITY_TYPE_TO_OVERRIDABLE_BEHAVIORS_MAP: {
            EntityType.NATIVE_ENTITY_TYPE_2_0_0.value.id:
                [BehaviorOperation.GET_KUBE_CONFIG.value]
        },
        RDEMetadataKey.BEHAVIOR_TO_ACL_MAP: {
            EntityType.NATIVE_ENTITY_TYPE_2_0_0.value.id:
                [BehaviorAcl.CREATE_CLUSTER_ACL.value,
                 BehaviorAcl.UPDATE_CLUSTER_ACL.value,
                 BehaviorAcl.DELETE_CLUSTER_ACL.value,
                 BehaviorAcl.KUBE_CONFIG_ACL.value,
                 BehaviorAcl.DELETE_NFS_NODE_ACL.value]
        }
    }
}
