# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import functools
import json
from typing import Iterator, List

from requests.exceptions import HTTPError

import container_service_extension.common.constants.shared_constants as cse_shared_constants  # noqa: E501
import container_service_extension.exception.exceptions as cse_exceptions
from container_service_extension.exception.minor_error_codes import MinorErrorCode  # noqa: E501
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.lib.cloudapi.constants import CloudApiResource
from container_service_extension.lib.cloudapi.constants import CloudApiVersion
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
from container_service_extension.rde.behaviors.behavior_model import Behavior, BehaviorAclEntry  # noqa: E501
import container_service_extension.rde.utils as def_utils


def handle_behavior_service_exception(func):
    """Decorate to trap exceptions and process them.

    Raise errors of type HTTPError as DefSchemaServiceError.
    Re-raise any other exception as it is.

    This decorator should be applied only on method of schema_service.py

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
            raise cse_exceptions.BehaviorServiceError(
                error_message=error_message,
                minor_error_code=MinorErrorCode.DEFAULT_ERROR_CODE)
        except Exception as error:
            LOGGER.error(error)
            raise error
        return result
    return exception_handler_wrapper


class BehaviorService:
    def __init__(self, cloudapi_client: CloudApiClient):
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    @handle_behavior_service_exception
    def create_behavior_on_interface(self, behavior: Behavior, interface_id) -> Behavior:  # noqa: E501
        """Create Behavior on the specified Interface.

        :param behavior: Behavior to be created.
        :param interface_id: Interface Id on which behavior is supposed to be
        created.
        :return: The created behavior object.
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}",
            payload=asdict(behavior))
        return Behavior(**response_body)

    @handle_behavior_service_exception
    def update_behavior_on_interface(self, behavior: Behavior, interface_id) -> Behavior:  # noqa: E501
        """Update the behavior on the specified interface Id.

        :param behavior: Behavior to be updated.
        :param interface_id: Interface Id on which the behavior to be updated
        is present.
        :return: The updated behavior object.
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior.id}",
            payload=asdict(behavior))
        return Behavior(**response_body)

    @handle_behavior_service_exception
    def list_behaviors_on_interface(self, interface_id) -> Iterator[Behavior]:
        """List all the behaviors on the specified interface.

        :param interface_id: Interface Id.
        :return: List of behaviors on the interface.
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=cse_shared_constants.RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                           f"/{interface_id}"
                                           f"/{CloudApiResource.BEHAVIORS}?"
                                           f"page={page_num}")
            if len(response_body['values']) > 0:
                for behavior in response_body['values']:
                    yield Behavior(**behavior)
            else:
                break

    @handle_behavior_service_exception
    def get_behavior_on_interface_by_id(self, behavior_id, interface_id) -> Behavior:  # noqa: E501
        """Get the behavior details by its ID on the given interface.

        :param behavior_id: Id of the behavior.
        :param interface_id: Id of the interface.
        :return: The behavior details.
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior_id}")
        return Behavior(**response_body)

    @handle_behavior_service_exception
    def get_behavior_on_interface_by_name(self, behavior_name, interface_id) -> Behavior:  # noqa: E501
        """Get the behavior details by its name on the given interface.

        :param behavior_name: Name of the behavior.
        :param interface_id: Id of the interface.
        :return: The behavior details.
        """
        # TODO Check with Extensibility team to ensure there canno exist
        #  duplicates.
        behaviors = self.list_behaviors_on_interface(interface_id=interface_id)
        for behavior in behaviors:
            if behavior.name == behavior_name:
                return behavior

    @handle_behavior_service_exception
    def delete_behavior_on_interface(self, behavior_id: str, interface_id: str):  # noqa: E501
        """Delete the behavior by its Id on the specified interface.

        :param behavior_id: Id of the behavior.
        :param interface_id: Id of the interface.
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        return self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior_id}")

    @handle_behavior_service_exception
    def create_behavior_on_entity_type(self, behavior: Behavior, entity_type_id) -> Behavior:  # noqa: E501
        """Create a behavior directly on the entity type.

        This method is non-functional. Under discussion with the Extensibility
        team on the error.
        TODO: Either update the docstring (or) remove the method.

        :param behavior:
        :param entity_type_id:
        :return:
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                       f"/{entity_type_id}"
                                       f"/{CloudApiResource.BEHAVIORS}",
            payload=asdict(behavior))
        return Behavior(**response_body)

    @handle_behavior_service_exception
    def override_behavior_on_entity_type(self, behavior: Behavior, entity_type_id) -> Behavior:  # noqa: E501
        """Override the behavior-interface on the specified entity type.

        Only Execution portion of the Behavior can be overridden.

        :param behavior: The updated behavior to be overridden on the entity-type.  # noqa: E501
        :param entity_type_id: Id of the entity type
        :return: Overridden behavior on the entity type.
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                       f"/{entity_type_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior.ref}",
            payload=asdict(behavior))
        return Behavior(**response_body)

    @handle_behavior_service_exception
    def list_behaviors_on_entity_type(self, entity_type_id) -> Iterator[Behavior]:  # noqa: E501
        """List behaviors on the specified entity type.

        :param entity_type_id: Id of the entity type.
        :return: List of behaviors.
        """
        # TODO Test this later, there is pagination issue on the entity types
        #  endpoint.
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=cse_shared_constants.RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                           f"/{entity_type_id}"
                                           f"/{CloudApiResource.BEHAVIORS}?"
                                           f"page={page_num}")
            if len(response_body['values']) > 0:
                for behavior in response_body['values']:
                    yield Behavior(**behavior)
            else:
                break

    @handle_behavior_service_exception
    def get_behavior_on_entity_type_by_id(self, behavior_interface_id, entity_type_id) -> Behavior:  # noqa: E501
        """Get the behavior on the entity type id.

        Note: Passing behavior-type id will not be accepted.

        :param behavior_interface_id: Id of the behavior-interface.
        :param entity_type_id: Id of the entity type.
        :return: The behavior details.
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                       f"/{entity_type_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior_interface_id}")
        return Behavior(**response_body)

    @handle_behavior_service_exception
    def get_behavior_on_entity_type_by_name(self, behavior_name, entity_type_id) -> Behavior:  # noqa: E501
        """Get the behavior by it's name on the specified entity type.

        :param behavior_name: Name of the behavior
        :param entity_type_id: Id of the entity type.
        :return: Behavior details
        """
        # TODO Test this later, there is pagination issue on the entity types
        #  endpoint. Ensure there cannot exist duplicates.
        behaviors = self.list_behaviors_on_entity_type(entity_type_id=entity_type_id)  # noqa: E501
        for behavior in behaviors:
            if behavior.name == behavior_name:
                return behavior

    @handle_behavior_service_exception
    def delete_behavior_on_entity_type(self, behavior_interface_id, entity_type_id):  # noqa: E501
        """Delete the behavior on the entity type.

        Note: Passing behavior-type id will not be accepted.

        :param behavior_interface_id: Id of the behavior interface.
        :param entity_type_id: Id of the entity type.
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        return self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                       f"/{entity_type_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior_interface_id}")

    @handle_behavior_service_exception
    def list_behavior_acls_on_entity_type(self, entity_type_id: str) -> Iterator[BehaviorAclEntry]:  # noqa: E501
        """Get the list of access controls of the individual behaviors.

        Get the list of access controls of the individual behaviors on the
        specified entity type.

        :param entity_type_id: Id of the entity type.
        :return: List of Behavior access controls.
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=cse_shared_constants.RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                           f"/{entity_type_id}"
                                           f"/{CloudApiResource.BEHAVIOR_ACLS}")  # noqa: E501
            if len(response_body['values']) > 0:
                for acl in response_body['values']:
                    yield BehaviorAclEntry(**acl)
            else:
                break

    @handle_behavior_service_exception
    def update_behavior_acls_on_entity_type(self, entity_type_id: str,
                                            behavior_acl_list: List[BehaviorAclEntry]):  # noqa: E501
        """Update the list of behavior access controls.

        Update the list of behavior access controls on the specified entity
        type. It is strictly recommended to retrieve the current list before
        updating it. Any missing records in the payload will be deleted.

        :param entity_type_id: Id of the entity type.
        :param behavior_acl_list: The updated list of behavior access controls.
        :return: List of updated behavior access controls.
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}"
                                       f"/{entity_type_id}"
                                       f"/{CloudApiResource.BEHAVIOR_ACLS}",
            payload={"values": [asdict(acl) for acl in behavior_acl_list]})
        return [BehaviorAclEntry(**acl) for acl in response_body['values']]

    @handle_behavior_service_exception
    def invoke_behavior(self, entity_id: str, behavior_interface_id: str,
                        arguments: dict = None) -> str:
        """Invoke behavior on the RDE.

        Below is the optional sample payload for the behavior invocation.
        {
            "arguments": {
                "argument1": "argument1"
            }
        }
        :param entity_id: Id of the entity
        :param behavior_interface_id: Id of the behavior interface
        :param arguments: Arguments to the behavior
        :return: task href in the Location header
        :rtype: str
        """
        # TODO Invocation of the behavior must return the taskID retrieved from
        #  the response headers. This is yet to be done by Extensibility team.
        payload = None
        if arguments:
            payload = {
                "arguments": arguments
            }
        _, response_headers = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITIES}"
                                       f"/{entity_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior_interface_id}"
                                       f"/{CloudApiResource.BEHAVIOR_INVOCATION}",  # noqa: E501
            payload=payload,
            return_response_headers=True)
        return response_headers[cse_shared_constants.HttpResponseHeader.LOCATION]  # noqa: E501
