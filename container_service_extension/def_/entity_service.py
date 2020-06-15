# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
from typing import List

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CLOUDAPI_VERSION_1_0_0  # noqa: E501
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.def_.models import DefEntity, DefEntityType
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as cse_exception
from container_service_extension.shared_constants import RequestMethod


# TODO(DEF) Exception handling
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

    def list_entities(self, filters: dict = None) -> List[DefEntity]:
        """List all defined entities of all entity types.

        vCD's behavior when invalid filter keys are passed:
            * It will throw a 400 if invalid first-level filter keys are passed
            Valid keys : [name, id, externalId, entityType, entity, state].
            * It will simply ignore any invalid nested properties and will
            simply return empty list.

        :param dict filters: Key-value pairs representing filter options
        :return: Generator of defined entities
        :rtype: Generator[DefEntity]
        """
        filter_string = None
        if filters:
            filter_string = ";".join([f"{k}=={v}" for (k, v) in filters.items()])  # noqa: E501
        page_num = 0
        while True:
            page_num += 1
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}?{query_string}")  # noqa: E501
            if len(response_body['values']) == 0:
                break
            for entity in response_body['values']:
                yield DefEntity(**entity)

    def list_entities_by_entity_type(self, vendor: str, nss: str, version: str,
                                     filters: dict = None) -> List[DefEntity]:
        """List entities of a given entity type.

        vCD's behavior when invalid filter keys are passed:
            * It will throw a 400 if invalid first-level filter keys are passed
            Valid keys : [name, id, externalId, entityType, entity, state].
            * It will simply return empty list on passing any invalid nested
             properties.

        :param str vendor: Vendor of the entity type
        :param str nss: nss of the entity type
        :param str version: version of the entity type
        :param dict filters: Key-value pairs representing filter options
        :return: List of entities of that entity type
        :rtype: List[DefEntity]
        """
        filter_string = None
        if filters:
            filter_string = ";".join(
                [f"{k}=={v}" for (k, v) in filters.items()])  # noqa: E501
        page_num = 0
        while True:
            page_num += 1
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                           f"{vendor}/{nss}/{version}?{query_string}")  # noqa: E501
            if len(response_body['values']) == 0:
                break
            for entity in response_body['values']:
                yield DefEntity(**entity)

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
                                           f"{CloudApiResource.INTERFACES}/{vendor}/{nss}/{version}?"  # noqa: E501
                                           f"page={page_num}")
            if len(response_body['values']) == 0:
                break
            for entity in response_body['values']:
                yield DefEntity(**entity)

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

    def get_native_entity_by_name(self, name: str) -> DefEntity:
        """Get Native cluster defined entity by its name.

        :param str name: Name of the native cluster.
        :return:
        """
        filter_by_name = {def_utils.ClusterEntityFilterKey.CLUSTER_NAME: name}
        entity_type: DefEntityType = def_utils.get_registered_def_entity_type()
        return self.list_entities_by_entity_type(vendor=entity_type.vendor,
                                                 nss=entity_type.nss,
                                                 version=entity_type.version,
                                                 filters=filter_by_name)

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
                                       f"{entity_id}/{CloudApiResource.ENTITY_RESOLVE}")  # noqa: E501
        msg = response_body[def_utils.DEF_ERROR_MESSAGE_KEY]
        del response_body[def_utils.DEF_ERROR_MESSAGE_KEY]
        entity = DefEntity(**response_body)
        if entity.state != def_utils.DEF_RESOLVED_STATE:
            raise cse_exception.DefEntityResolutionError(id=entity.id,
                                                         state=entity.state,
                                                         msg=msg)
        return entity
