# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
import functools
import json
from typing import List

from requests.exceptions import HTTPError


from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiVersion
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.def_.models import DefEntity, DefEntityType
import container_service_extension.def_.schema_service as def_schema_svc
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as cse_exception
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.minor_error_codes import MinorErrorCode
from container_service_extension.shared_constants import RequestMethod
import container_service_extension.utils as utils


def handle_entity_service_exception(func):
    """Decorate to trap exceptions and process them.

    Raise errors of type HTTPError as DefEntityServiceError
    and raise the custom error. Re-raise any other exception as it is.

    This decorator should be applied only on method of entity_service.py

    :param method func: decorated function

    :return: reference to the function that executes the decorated function
        and traps exceptions raised by it.
    """
    @functools.wraps(func)
    def exception_handler_wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except HTTPError as error:
            response_dict = json.loads(error.response.text)
            error_message = response_dict.get('message')
            LOGGER.error(error_message)
            raise cse_exception.DefEntityServiceError(
                error_message=error_message,
                minor_error_code=MinorErrorCode.DEFAULT_ERROR_CODE)
        except Exception as error:
            LOGGER.error(error)
            raise error
        return result
    return exception_handler_wrapper


class DefEntityService():
    """Manages lifecycle of entities.

    TODO Add API version check at the appropriate place. This class needs to
     be used if and only if vCD API version >= v35.
    """

    def __init__(self, cloudapi_client: CloudApiClient):
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    @handle_entity_service_exception
    def create_entity(self, entity_type_id: str, entity: DefEntity,
                      tenant_org_context: str = None) -> None:
        """Create defined entity instance of an entity type.

        :param str entity_type_id: ID of the DefEntityType
        :param DefEntity entity: Defined entity instance
        :return: None
        """
        additional_headers = {}
        if tenant_org_context:
            additional_headers['x-vmware-vcloud-tenant-context'] = tenant_org_context  # noqa: E501
        self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/"
                                       f"{entity_type_id}",
            payload=asdict(entity),
            additional_headers=additional_headers)

    @handle_entity_service_exception
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
        :rtype: Generator[DefEntity, None, None]
        """
        filter_string = utils.construct_filter_string(filters)
        page_num = 0
        while True:
            page_num += 1
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                           f"{CloudApiResource.ENTITY_TYPES_TOKEN}/"  # noqa: E501
                                           f"{vendor}/{nss}/{version}?{query_string}")  # noqa: E501
            if len(response_body['values']) == 0:
                break
            for entity in response_body['values']:
                yield DefEntity(**entity)

    @handle_entity_service_exception
    def list_entities_by_interface(self, vendor: str, nss: str, version: str):
        """List entities of a given interface.

        An interface is uniquely identified by properties vendor, nss and
        version.

        :param str vendor: Vendor of the interface
        :param str nss: nss of the interface
        :param str version: version of the interface
        :return: Generator of entities of that interface type
        :rtype: Generator[DefEntity, None, None]
        """
        # TODO Yet to be verified. Waiting for the build from Extensibility
        #  team.
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                           f"{CloudApiResource.INTERFACES}/{vendor}/{nss}/{version}?"  # noqa: E501
                                           f"page={page_num}")
            if len(response_body['values']) == 0:
                break
            for entity in response_body['values']:
                yield DefEntity(**entity)

    @handle_entity_service_exception
    def update_entity(self, entity_id: str, entity: DefEntity) -> DefEntity:
        """Update entity instance.

        :param str entity_id: Id of the entity to be updated.
        :param DefEntity entity: Modified entity to be updated.
        :return: Updated entity
        :rtype: DefEntity
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}",
            payload=asdict(entity))
        return DefEntity(**response_body)

    @handle_entity_service_exception
    def get_entity(self, entity_id: str) -> DefEntity:
        """Get the defined entity given entity id.

        :param str entity_id: Id of the entity.
        :return: Details of the entity.
        :rtype: DefEntity
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}")
        return DefEntity(**response_body)

    @handle_entity_service_exception
    def get_native_entity_by_name(self, name: str, filters: dict = {}) -> DefEntity:  # noqa: E501
        """Get Native cluster defined entity by its name.

        :param str name: Name of the native cluster.
        :param dict filters: key-value pairs representing filter options
        :return:
        """
        filters[def_utils.ClusterEntityFilterKey.CLUSTER_NAME.value] = name
        entity_type: DefEntityType = self.get_def_entity_type()
        for entity in \
            self.list_entities_by_entity_type(vendor=entity_type.vendor,
                                              nss=entity_type.nss,
                                              version=entity_type.version,
                                              filters=filters):
            return entity

    @handle_entity_service_exception
    def delete_entity(self, entity_id: str) -> None:
        """Delete the defined entity.

        :param str entity_id: Id of the entity.
        :return: None
        """
        self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
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
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}/{CloudApiResource.ENTITY_RESOLVE}")  # noqa: E501
        msg = response_body[def_utils.DEF_ERROR_MESSAGE_KEY]
        del response_body[def_utils.DEF_ERROR_MESSAGE_KEY]
        entity = DefEntity(**response_body)
        # TODO: Just record the error message; revisit after HTTP response code
        # is good enough to decide if exception should be thrown or not
        if entity.state != def_utils.DEF_RESOLVED_STATE:
            LOGGER.error(msg)
        return entity

    def get_def_entity_type(self):
        """Fetch the native cluster entity type.

        This method is required for CSE client to make use of
        Defined entity service directly with no requirement of
        CSE server.

        :return: Defined Entity Type for the current client api version
        :rtype: DefEntityType
        """
        schema_svc = def_schema_svc.DefSchemaService(self._cloudapi_client)
        keys_map = def_utils.MAP_API_VERSION_TO_KEYS[float(self._cloudapi_client.get_api_version())]  # noqa: E501
        entity_type_id = def_utils.generate_entity_type_id(
            vendor=keys_map[def_utils.DefKey.ENTITY_TYPE_VENDOR],
            nss=keys_map[def_utils.DefKey.ENTITY_TYPE_NSS],
            version=keys_map[def_utils.DefKey.ENTITY_TYPE_VERSION])
        return schema_svc.get_entity_type(entity_type_id)

    def is_native_entity(self, entity_id: str):
        """."""
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}")
        return def_utils.DEF_NATIVE_ENTITY_TYPE_NSS in response_body['entityType']  # noqa: E501
