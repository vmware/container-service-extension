# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import json

from requests.exceptions import HTTPError
import semantic_version

import container_service_extension.common.constants.shared_constants as cse_shared_constants  # noqa: E501
import container_service_extension.exception.exceptions as cse_exceptions
from container_service_extension.exception.minor_error_codes import MinorErrorCode  # noqa: E501
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.lib.cloudapi.constants import CloudApiResource
from container_service_extension.lib.cloudapi.constants import CloudApiVersion
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.rde.models.common_models as common_models
from container_service_extension.rde.utils import raise_error_if_def_not_supported # noqa: E501


def handle_schema_service_exception(func):
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
            raise cse_exceptions.DefSchemaServiceError(
                error_message=error_message,
                minor_error_code=MinorErrorCode.DEFAULT_ERROR_CODE)
        except Exception as error:
            LOGGER.error(error)
            raise error
        return result
    return exception_handler_wrapper


class DefSchemaService():
    """Manages lifecycle of defined entity interfaces and entity types."""

    def __init__(self, cloudapi_client: CloudApiClient):
        raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    @handle_schema_service_exception
    def list_interfaces(self):
        """List defined entity interfaces.

        :return: Generator of interfaces
        :rtype: Generator
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=cse_shared_constants.RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.INTERFACES}?"
                f"page={page_num}")
            if len(response_body['values']) > 0:
                for interface in response_body['values']:
                    yield common_models.DefInterface.from_dict(interface)
            else:
                break

    @handle_schema_service_exception
    def get_interface(self, id: str) -> common_models.DefInterface:
        """Get the interface given an id.

        :param str id: Id if the interface.
        :return: Interface
        :rtype: DefInterface
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}/{id}")
        return common_models.DefInterface.from_dict(response_body)

    @handle_schema_service_exception
    def create_interface(self, interface: common_models.DefInterface) -> common_models.DefInterface:  # noqa: E501
        """Create the Defined entity interface.

        :param DefInterface interface: body of the interface
        :return: Interface that is just created
        :rtype: DefInterface
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}",
            payload=interface.to_dict())
        return common_models.DefInterface.from_dict(response_body)

    @handle_schema_service_exception
    def update_interface(self, interface: common_models.DefInterface) -> common_models.DefInterface:  # noqa: E501
        """Update the Defined entity interface.

        As of May 2020, only name of the interface can be updated.

        :param DefInterface interface: Interface to be updated.
        :return: Interface that is just updated.
        :rtype: DefInterface
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}/"
            f"{interface.id}",
            payload=interface.to_dict())
        return common_models.DefInterface.from_dict(response_body)

    @handle_schema_service_exception
    def delete_interface(self, id: str) -> None:
        """Delete the defined entity interface.

        :param str id: Id of the interface.
        :return: None
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        return self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}/{id}")

    @handle_schema_service_exception
    def create_entity_type(self, entity_type: common_models.DefEntityType) -> common_models.DefEntityType:  # noqa: E501
        """Create the Defined entity type.

        :param DefEntityType interface: body of the entity type
        :return: DefEntityType that is just created
        :rtype: DefEntityType
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}",
            payload=entity_type.to_dict())
        return common_models.DefEntityType.from_dict(response_body)

    @handle_schema_service_exception
    def get_entity_type(self, id: str) -> common_models.DefEntityType:
        """Get the entity type given an id.

        :param str id: Id of the interface.
        :return: Entity type
        :rtype: DefEntityType
        """
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/{id}")
        return common_models.DefEntityType.from_dict(response_body)

    @handle_schema_service_exception
    def list_entity_types(self):
        """List Entity types.

        :return: Generator of entity types
        :rtype: Generator[DefEntityType]
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=cse_shared_constants.RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}?"
                f"page={page_num}")
            if len(response_body['values']) > 0:
                for entityType in response_body['values']:
                    yield common_models.DefEntityType.from_dict(entityType)
            else:
                break

    @handle_schema_service_exception
    def get_latest_registered_schema_version(self) -> str:
        """Get the latest registered schema version.

        :return: string representing the latest schema version registered.
        :rtype: str
        """
        max_entity_type_version = semantic_version.Version('0.0.0')
        for entity_type in self.list_entity_types():
            entity_type_version = semantic_version.Version(entity_type.version)
            if max_entity_type_version < entity_type_version:  # noqa: E501
                max_entity_type_version = entity_type_version
        return str(max_entity_type_version)

    @handle_schema_service_exception
    def update_entity_type(self, entity_type: common_models.DefEntityType) -> common_models.DefEntityType:  # noqa: E501
        """Update the entity type.

        As of May 2020, only name and schema of the entity type can be
        updated.

        :param entity_type: Entity type to be updated.
        :return: Updated entity type
        :rtype: DefEntityType
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/"
            f"{entity_type.id}",
            payload=entity_type.to_dict())
        return common_models.DefEntityType.from_dict(response_body)

    @handle_schema_service_exception
    def delete_entity_type(self, id: str) -> None:
        """Delete the entity type given an id.

        :param str id: Id of the entity type to be deleted.
        :return: None
        """
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.DELETE,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/{id}")
