# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
from typing import List

import container_service_extension.exceptions as exceptions
from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import \
    CLOUDAPI_VERSION_1_0_0  # noqa: E501
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.def_modules.models import DefEntity
import container_service_extension.def_modules.utils as def_utils
from container_service_extension.shared_constants import RequestMethod


class DefEntityService():
    """Manages lifecycle of entities.

    TODO Add API version check at the appropriate place. This class needs to
     be used if and only if vCD API version >= v35.
    """

    def __init__(self, cloudapi_client: CloudApiClient):
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    def create_entity(self, entity_type_id: str, entity: DefEntity) -> None:
        """Create defined entity instance of an entity type.

        :param str entity_type_id: ID of the DefEntityType
        :param DefEntity entity: Defined entity instance
        :return: None
        """
        self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/"
                                       f"{entity_type_id}",
            payload=asdict(entity))

    def list_entities(self):
        """List all defined entities of all entity types.

        :return: Generator of defined entities
        :rtype: Generator[DefEntity]
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}?"
                                           f"page={page_num}")
            if len(response_body['values']) > 0:
                for entity in response_body['values']:
                    yield DefEntity(**entity)
            else:
                break

    def list_entities_by_interface(self, vendor: str, nss: str, version: str):
        """List entities of a given interface.

        An interface is uniquely identified by properties vendor, nss and
        version.

        :param str vendor: Vendor of the interface
        :param str nss: nss of the interface
        :param str version: version of the interface
        :return: Generator of entities of that interface type
        :rtype: Generator[DefEntity]
        """
        # TODO Yet to be verified. Waiting for the build from Extensibility
        #  team.
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                           f"{CloudApiResource.INTERFACES}/{vendor}/{nss}/{version}?"
                                           f"page={page_num}")
            if len(response_body['values']) > 0:
                for entity in response_body['values']:
                    yield DefEntity(**entity)
            else:
                break

    def list_entities_by_entity_type(self, vendor: str, nss: str,
                                     version: str) -> List[DefEntity]:
        """List entities of a given entity type.

        An entity type is uniquely identified by properties vendor, nss and
        version.

        :param str vendor: Vendor of the entity type
        :param str nss: nss of the entity type
        :param str version: version of the entity type
        :return: List of entities of that entity type
        :rtype: List[DefEntity]
        """
        # TODO Yet to be verified. Waiting for the build from
        #  Extensibility team.
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                           f"{vendor}/{nss}/{version}?page={page_num}")
            if len(response_body['values']) > 0:
                for entity in response_body['values']:
                    yield DefEntity(**entity)
            else:
                break

    def update_entity(self, entity_id: str, entity: DefEntity) -> DefEntity:
        """Update entity instance.

        :param str entity_id: Id of the entity to be updated.
        :param DefEntity entity: Modified entity to be updated.
        :return: Updated entity
        :rtype: DefEntity
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.PUT,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}",
            payload=asdict(entity))
        return DefEntity(**response_body)

    def get_entity(self, entity_id: str) -> DefEntity:
        """Get the defined entity given entity id.

        :param str entity_id: Id of the entity.
        :return: Details of the entity.
        :rtype: DefEntity
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}")
        return DefEntity(**response_body)

    def get_entity_by_name(self, name: str) -> DefEntity:
        # TODO Below call should add another filter field 'entity.kind==native'.
        #  It should not get entities if non-native clusters.
        #  Awaiting on dependency from Extensibility team."
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}?filter=name=={name}")
        entity = response_body['values'][0]
        return DefEntity(**entity)

    def delete_entity(self, entity_id: str) -> None:
        """Delete the defined entity.

        :param str entity_id: Id of the entity.
        :return: None
        """
        self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}")

    def resolve_entity(self, entity_id: str) -> DefEntity:
        """Resolve the entity.

        Validates the entity against the schema. Based on the result, entity
        state will be either changed to "RESOLVED" (or) "RESOLUTION ERROR".

        :param str entity_id: Id of the entity
        :return: Defined entity with its state updated.
        :rtype: DefEntity
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}/{CloudApiResource.ENTITY_RESOLVE}")
        msg = response_body['message']
        del response_body['message']
        entity = DefEntity(**response_body)
        if entity.state != 'RESOLVED':
            raise exceptions.DefEntityResolutionErrorException(id=entity.id,
                                                               state=entity.state,  # noqa: E501
                                                               msg=msg)

    def filter_entities_by_property(self):
        # TODO Yet to be implemented. Waiting for the build from extensibility
        return None
