# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict, dataclass
from typing import List

from container_service_extension.common.constants import shared_constants as shared_constants  # noqa: E501
from container_service_extension.rde import constants as def_constants, utils as def_utils  # noqa: E501
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
from container_service_extension.rde.models.rde_factory import get_rde_model


@dataclass(frozen=True)
class DefInterface:
    """Provides interface for the defined entity type."""

    name: str
    vendor: str = def_constants.DEF_VMWARE_VENDOR
    nss: str = def_constants.DEF_VMWARE_INTERFACE_NSS
    version: str = def_constants.DEF_VMWARE_INTERFACE_VERSION
    id: str = None
    readonly: bool = False

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


@dataclass(frozen=True)
class DefEntityType:
    """Represents the schema for Defined Entities."""

    name: str
    description: str
    schema: dict
    interfaces: list
    vendor: str = def_constants.DEF_CSE_VENDOR
    nss: str = def_constants.DEF_NATIVE_ENTITY_TYPE_NSS
    version: str
    id: str = None
    externalId: str = None
    readonly: bool = False

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


@dataclass()
class Owner:
    name: str = None
    id: str = None


@dataclass()
class Org:
    name: str = None
    id: str = None


@dataclass()
class DefEntity:
    """Represents defined entity instance.

    If dictionaries are passed as arguments, the constructor auto-converts
    them into the expected class instances.
    """

    name: str
    entity: AbstractNativeEntity
    id: str = None
    entityType: str = None
    externalId: str = None
    state: str = None
    owner: Owner = None
    org: Org = None

    def __init__(self, entity: AbstractNativeEntity, entityType: str,
                 name: str = None, id: str = None,
                 externalId: str = None, state: str = None,
                 owner: Owner = None, org: Org = None):
        self.id = id
        self.entityType = entityType

        # Get the entity type version from entity type urn
        entity_type_version = self.entityType.split(":")[-1]
        # Parse the enitty to the right entity class
        NativeEntityClass = get_rde_model(entity_type_version)
        self.entity: AbstractNativeEntity = \
            NativeEntityClass(**entity) if isinstance(entity, dict) else entity

        self.name = name or self.entity.metadata.cluster_name
        self.externalId = externalId
        self.state = state
        self.owner = Owner(**owner) if isinstance(owner, dict) else owner
        self.org = Org(**org) if isinstance(org, dict) else org


@dataclass()
class Ovdc:
    k8s_runtime: List[str]
    ovdc_name: str = None
    ovdc_id: str = None
    org_name: str = None
    remove_cp_from_vms_on_disable: bool = False


@dataclass()
class ClusterAclEntry:
    accessLevelId: str = None
    memberId: str = None
    id: str = None
    grantType: str = None
    objectId: str = None
    username: str = None

    def construct_filtered_dict(self, include=None):
        if include is None:
            include = []
        orig_dict = asdict(self)
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
    # Properties being used for List operation attributes representiing them
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
    name: str = None
    org: Org = None
    entity = None
    owner: Owner = None

    def __init__(self, name: str, org: Org, entityType: str, entity,
                 owner: Owner, **kwargs):
        self.name = name
        self.org = Org(**org) if isinstance(org, dict) else org
        self.entityType = entityType
        entity_dict = asdict(entity) if not isinstance(entity, dict) else entity  # noqa: E501
        if entity_dict['kind'] in \
                [shared_constants.ClusterEntityKind.NATIVE.value,
                 shared_constants.ClusterEntityKind.TKG_PLUS.value]:
            # Get the entity type version from entity type urn
            entity_type_version = self.entityType.split(":")[-1]
            # Parse the enitty to the right entity class
            NativeEntityClass = get_rde_model(entity_type_version)
            self.entity: AbstractNativeEntity = \
                NativeEntityClass(**entity_dict) if isinstance(entity, dict) else entity  # noqa: E501
        elif entity_dict['kind'] == \
                shared_constants.ClusterEntityKind.TKG.value:
            self.entity = TKGEntity(**entity) if isinstance(entity, dict) else entity  # noqa: E501
        else:
            raise Exception("Invalid cluster kind")
        self.owner = Owner(**owner) if isinstance(owner, dict) else owner


@dataclass()
class TKGDistribution:
    version: str = None

    def __init__(self, version: str, **kwargs):
        self.version = version


@dataclass()
class TKGSpec:
    distribution: TKGDistribution = None

    def __init__(self, distribution: TKGDistribution, **kwargs):
        self.distribution = TKGDistribution(**distribution) \
            if isinstance(distribution, dict) else distribution


@dataclass()
class TKGStatus:
    phase: str = None

    def __init__(self, phase: str, **kwargs):
        self.phase = phase


@dataclass()
class TKGMetadata:
    virtualDataCenterName: str = None

    def __init__(self, virtualDataCenterName: str, **kwargs):
        self.virtualDataCenterName = virtualDataCenterName


@dataclass()
class TKGEntity:
    kind: str = None
    spec: TKGSpec = None
    status: TKGStatus = None
    metadata: TKGMetadata = None

    def __init__(self, kind: str, spec: TKGSpec, status: TKGStatus,
                 metadata: TKGMetadata, **kwargs):
        self.kind = kind
        self.spec = TKGSpec(**spec) if isinstance(spec, dict) else spec
        self.status = TKGStatus(**status) \
            if isinstance(status, dict) else status
        self.metadata = TKGMetadata(**metadata) \
            if isinstance(metadata, dict) else metadata
