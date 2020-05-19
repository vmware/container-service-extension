# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass

from container_service_extension.cloudapi.constants import DEF_ENTITY_TYPE_ID_PREFIX # noqa: E501
from container_service_extension.cloudapi.constants import DEF_INTERFACE_ID_PREFIX # noqa: E501

# TODO Below models will not be needed once we integrate new pythonSDK into CSE


@dataclass()
class DefInterface(init=True, repr=True, eq=True, order=False,
                   unsafe_hash=False, frozen=True):
    """Provides interface for the defined entity type."""

    name: str
    id: str
    vendor: str
    nss: str
    version: str
    readonly: bool = False

    def get_id(self):
        """Get interface id : "urn:vcloud:interface:cse.native:1.0.0."""
        if self.id is None:
            return f"{DEF_INTERFACE_ID_PREFIX}:{self.vendor}.{self.nss}:" \
                f"{self.version}"
        else:
            return self.id


@dataclass()
class DefEntityType(init=True, repr=True, eq=True, order=False,
                    unsafe_hash=False, frozen=True):
    """Represents the schema for Defined Entities."""

    name: str
    description: str
    id: str
    vendor: str
    nss: str
    version: str
    schema: dict
    interfaces: list
    externalId: str = None
    readonly: bool = False

    def get_id(self):
        """Get Entity type id : "urn:vcloud:interface:cse.native:1.0.0."""
        if self.id is None:
            return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{self.vendor}.{self.nss}:" \
                f"{self.version}"
        else:
            return self.id


@dataclass
class DefEntity:
    """Represents defined entity instances."""

    name: str
    entity: dict
    id: str = None
    entityType: str = None
    externalId: str = None
    state: str = None
