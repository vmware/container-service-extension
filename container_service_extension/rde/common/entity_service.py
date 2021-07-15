# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import json
from typing import List, Tuple, Union

from pyvcloud.vcd.client import ApiVersion
from requests.exceptions import HTTPError

import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE, PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.common.constants.shared_constants import HttpResponseHeader  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.exception.exceptions as cse_exception
from container_service_extension.exception.minor_error_codes import MinorErrorCode  # noqa: E501
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.lib.cloudapi.constants import CloudApiResource
from container_service_extension.lib.cloudapi.constants import CloudApiVersion
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.rde.constants as def_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
from container_service_extension.rde.models.common_models import DefEntity
from container_service_extension.rde.models.common_models import DefEntityType
from container_service_extension.rde.models.common_models import GenericClusterEntity  # noqa: E501
from container_service_extension.rde.models.common_models import TKGEntity
import container_service_extension.rde.utils as def_utils


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


class DefEntityService:
    """Manages lifecycle of entities.

    TODO Add API version check at the appropriate place. This class needs to
     be used if and only if vCD API version >= v35.
    """

    def __init__(self, cloudapi_client: CloudApiClient):
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    @handle_entity_service_exception
    def create_entity(self, entity_type_id: str, entity: DefEntity,
                      tenant_org_context: str = None,
                      delete_status_from_payload=True,
                      is_request_async=False) -> Union[dict, Tuple[dict, dict]]:  # noqa: E501
        """Create defined entity instance of an entity type.

        :param str entity_type_id: ID of the DefEntityType
        :param DefEntity entity: Defined entity instance
        :param str tenant_org_context:
        :param bool delete_status_from_payload: should delete status from payload?  # noqa: E501
        :param bool is_request_async: The request is intended to be asynchronous
            if this flag is set, href of the task is returned in addition to
            the response body

        :return: created entity or created entity with response headers
        :rtype: Union[dict, Tuple[dict, dict]]
        """
        additional_request_headers = {}
        if tenant_org_context:
            additional_request_headers['x-vmware-vcloud-tenant-context'] = tenant_org_context  # noqa: E501

        payload: dict = entity.to_dict()
        if delete_status_from_payload:
            payload.get('entity', {}).pop('status', None)

        resource_url_relative_path = f"{CloudApiResource.ENTITY_TYPES}/{entity_type_id}"  # noqa: E501
        # response will be a tuple (response_body, response_header) if
        # is_request_async is true. Else, it will be just response_body
        response = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=resource_url_relative_path,
            payload=payload,
            additional_request_headers=additional_request_headers,
            return_response_headers=is_request_async)

        if is_request_async:
            # if request is async, return the location header as well
            # TODO: Use the Http response status code to decide which
            #   header name to use for task_href
            #   202 - location header,
            #   200 - xvcloud-task-location needs to be used
            return response[0], response[1][HttpResponseHeader.LOCATION.value]
        return response

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
    def get_entities_per_page_by_entity_type(self, vendor: str, nss: str, version: str,  # noqa: E501
                                             filters: dict = None, page_number: int = CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                             page_size: int = CSE_PAGINATION_DEFAULT_PAGE_SIZE):  # noqa: E501
        """List all the entities per page and entity type.

        :param str vendor: entity type vendor name
        :param str nss: entity type namespace
        :param str version: entity type version
        :param dict filters: additional filters
        :param int page_number: page to return
        :param int page_size: number of records per page
        :rtype: Generator[(List[DefEntity], int), None, None]
        """
        filter_string = utils.construct_filter_string(filters)
        query_string = f"page={page_number}&pageSize={page_size}"
        if filter_string:
            query_string = f"filter={filter_string}&{query_string}"
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{CloudApiResource.ENTITY_TYPES_TOKEN}/"  # noqa: E501
                                       f"{vendor}/{nss}/{version}?{query_string}")  # noqa: E501
        result = {}
        entity_list: List[DefEntity] = []
        for v in response_body['values']:
            entity_list.append(DefEntity(**v))
        result[PaginationKey.RESULT_TOTAL] = int(response_body['resultTotal'])
        result[PaginationKey.VALUES] = entity_list
        return result

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

    def get_all_entities_per_page_by_interface(self, vendor: str, nss: str, version: str,  # noqa: E501
                                               filters: dict = None,
                                               page_number: int = CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                               page_size: int = CSE_PAGINATION_DEFAULT_PAGE_SIZE):  # noqa: E501
        """Get a page of entities belonging to an interface.

        An interface is uniquely identified by properties vendor, nss and
        version.

        :param str vendor: Vendor of the interface
        :param str nss: nss of the interface
        :param str version: version of the interface
        :param dict filters:
        :param int page_number:
        :param int page_size:

        :return: Generator of entities of that interface type
        :rtype: Generator[List, None, None]
        """
        filter_string = utils.construct_filter_string(filters)
        query_string = f"page={page_number}&pageSize={page_size}"
        if filter_string:
            query_string = f"filter={filter_string}&{query_string}"
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{CloudApiResource.INTERFACES}/"
                                       f"{vendor}/{nss}/{version}?{query_string}")  # noqa: E501
        result = {}
        entity_list = []
        for entity in response_body['values']:
            entity_list.append(GenericClusterEntity(**entity))
        result[PaginationKey.RESULT_TOTAL] = int(response_body['resultTotal'])
        result[PaginationKey.PAGE_COUNT] = int(response_body['pageCount'])
        result[PaginationKey.PAGE_NUMBER] = page_number
        result[PaginationKey.PAGE_SIZE] = page_size
        result[PaginationKey.VALUES] = entity_list
        return result

    @handle_entity_service_exception
    def update_entity(self, entity_id: str, entity: DefEntity,
                      invoke_hooks=False,
                      is_request_async=False) -> Union[DefEntity, Tuple[DefEntity, dict]]:  # noqa: E501
        """Update entity instance.

        :param str entity_id: Id of the entity to be updated.
        :param DefEntity entity: Modified entity to be updated.
        :param bool invoke_hooks: Value indicating whether
             hook-based-behaviors need to be triggered or not.
        :param bool is_request_async: The request is intended to be
            asynchronous if this flag is set, href of the task is returned
            in addition to the response body

        :return: Updated entity or Updated entity and response headers
        :rtype: Union[DefEntity, Tuple[DefEntity, dict]]
        """
        resource_url_relative_path = f"{CloudApiResource.ENTITIES}/{entity_id}"
        vcd_api_version = self._cloudapi_client.get_api_version()
        # TODO Float conversions must be changed to Semantic versioning.
        # TODO: Also include any persona having Administrator:FullControl
        #  on CSE:nativeCluster
        if float(vcd_api_version) >= float(ApiVersion.VERSION_36.value) and \
                self._cloudapi_client.is_sys_admin and not invoke_hooks:
            resource_url_relative_path += f"?invokeHooks={str(invoke_hooks).lower()}"  # noqa: E501

        payload: dict = entity.to_dict()

        # Prevent users with rights <= EDIT/VIEW on CSE:NATIVECLUSTER from
        # updating "private" property of RDE "status" section
        # TODO: Replace sys admin check with FULL CONTROL rights check on
        #  CSE:NATIVECLUSTER. Users with no FULL CONTROL rights cannot update
        #  private property of entity->status.
        if not self._cloudapi_client.is_sys_admin:
            payload.get('entity', {}).get('status', {}).pop('private', None)

        if is_request_async:
            # if request is async, return the task href in
            # x_vmware_vcloud_task_location header
            # TODO: Use the Http response status code to decide which
            #   header name to use for task_href
            #   202 - location header,
            #   200 - xvcloud-task-location needs to be used
            response_body, headers = self._cloudapi_client.do_request(
                method=RequestMethod.PUT,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=resource_url_relative_path,
                payload=payload,
                return_response_headers=is_request_async)
            return DefEntity(**response_body), headers[HttpResponseHeader.X_VMWARE_VCLOUD_TASK_LOCATION.value]  # noqa: E501
        else:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.PUT,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=resource_url_relative_path,
                payload=payload)
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
    def get_tkg_or_def_entity(self, entity_id: str) -> DefEntity:
        """Get the tkg or def entity given entity id.

        :param str entity_id: Id of the entity.

        :return: Details of the entity.
        :rtype: DefEntity
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}")
        entity: dict = response_body['entity']
        entity_kind: dict = entity['kind']
        if entity_kind in [shared_constants.ClusterEntityKind.NATIVE.value,
                           shared_constants.ClusterEntityKind.TKG_PLUS.value]:
            return DefEntity(**response_body)
        elif entity_kind == shared_constants.ClusterEntityKind.TKG_S.value:
            return TKGEntity(**entity)
        raise Exception("Invalid cluster kind.")

    @handle_entity_service_exception
    def create_acl_for_entity(self,
                              id: str,
                              grant_type: str,
                              access_level_id: str,
                              member_id: str):
        """Create ACL Rule for the Entity.

        :param str id: Id of the Entity
        :param str grant_type: if acl grant is based on memberships or
            entitlements
        :param str access_level_id: level of access which the
            subject will be granted.
        :param str member_id: member id, this access control grant applies to
        """
        acl_details = {
            'grantType': grant_type,
            'accessLevelId': access_level_id,
            'memberId': member_id
        }

        self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{id}/"
                                       f"{CloudApiResource.ACL}/",
            payload=acl_details)
        return

    @handle_entity_service_exception
    def get_native_rde_by_name_and_rde_version(self, name: str, version: str,
                                               filters: dict = None) -> DefEntity:  # noqa: E501
        """Get native RDE given its name and RDE version.

        This function is used commonly by CSE CLI client and CSE server

        :param str name: Name of the native cluster.
        :param str version: RDE version
        :param dict filters: dictionary representing filters
        :rtype: DefEntity
        :return: Native cluster RDE
        """
        if not filters:
            filters = {}
        filters[def_constants.RDEFilterKey.NAME.value] = name
        native_entity_type: DefEntityType = \
            def_utils.get_rde_metadata(version)[def_constants.RDEMetadataKey.ENTITY_TYPE]  # noqa: E501
        for entity in \
            self.list_entities_by_entity_type(vendor=native_entity_type.vendor,
                                              nss=native_entity_type.nss,
                                              version=native_entity_type.version,  # noqa: E501
                                              filters=filters):
            return entity

    @handle_entity_service_exception
    def delete_entity(self, entity_id: str, invoke_hooks: bool = False, is_request_async=False) -> Union[dict, Tuple[dict, dict]]:  # noqa: E501
        """Delete the defined entity.

        :param str entity_id: Id of the entity.
        :param bool invoke_hooks: set to true if hooks need to be invoked
        :param bool is_request_async: The request is intended to be
            asynchronous if this flag is set, href of the task is returned
            in addition to the response body

        :return: response body or response body and response headers
        :rtype: Union[dict, Tuple[dict, dict]]
        """
        # response will be a tuple (response_body, response_header) if
        # is_request_async is true. Else, it will be just response_body
        vcd_api_version = self._cloudapi_client.get_api_version()
        resource_url_relative_path = f"{CloudApiResource.ENTITIES}/{entity_id}"

        # TODO: Also include any persona having Administrator:FullControl
        #  on CSE:nativeCluster
        if float(vcd_api_version) >= float(ApiVersion.VERSION_36.value) and \
                self._cloudapi_client.is_sys_admin and not invoke_hooks:
            resource_url_relative_path += f"?invokeHooks={str(invoke_hooks).lower()}"  # noqa: E501

        response = self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=resource_url_relative_path,  # noqa: E501
            return_response_headers=is_request_async)
        if is_request_async:
            # if request is async, return the location header as well
            # TODO: Use the Http response status code to decide which
            #   header name to use for task_href
            #   202 - location header,
            #   200 - xvcloud-task-location needs to be used
            return response[0], response[1][HttpResponseHeader.LOCATION.value]
        return response

    @handle_entity_service_exception
    def resolve_entity(self, entity_id: str, entity_type_id: str = None) -> DefEntity:  # noqa: E501
        """Resolve the entity.

        Validates the entity against the schema. Based on the result, entity
        state will be either changed to "RESOLVED" (or) "RESOLUTION ERROR".

        :param str entity_id: Id of the entity
        :param str entity_type_id: Entity type ID of the entity being resolved
        :return: Defined entity with its state updated.
        :rtype: DefEntity
        """
        if not entity_type_id:
            rde: DefEntity = self.get_entity(entity_id)
            entity_type_id = rde.entityType
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}/{CloudApiResource.ENTITY_RESOLVE}")  # noqa: E501
        msg = response_body[def_constants.DEF_ERROR_MESSAGE_KEY]
        del response_body[def_constants.DEF_ERROR_MESSAGE_KEY]
        entity = DefEntity(entityType=entity_type_id, **response_body)
        # TODO: Just record the error message; revisit after HTTP response code
        # is good enough to decide if exception should be thrown or not
        if entity.state != def_constants.DEF_RESOLVED_STATE:
            LOGGER.error(msg)
        return entity

    def is_native_entity(self, entity_id: str):
        """."""
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}/"
                                       f"{entity_id}")
        return def_constants.DEF_NATIVE_ENTITY_TYPE_NSS in response_body['entityType']  # noqa: E501

    @handle_entity_service_exception
    def upgrade_entity(self, entity_id: str,
                       upgraded_native_entity: AbstractNativeEntity,
                       target_entity_type_id: str):
        """Upgrade entity type of the entity to the specified one.

        :param str entity_id: ID of the entity to upgrade
        :param str upgraded_native_entity: dataclass representing the native
            entity with upgraded fields.
        :param str target_entity_type_id: target entity type version to which
            the defined entity should be upgraded to.
        :return: DefEntity representing the upgraded defined entity
        :rtype: DefEntity
        """
        rde = self.get_entity(entity_id)
        rde.entity = upgraded_native_entity

        # Update only the entityType property
        rde.entityType = target_entity_type_id

        return self.update_entity(entity_id, rde, invoke_hooks=False)
