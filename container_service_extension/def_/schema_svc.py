# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CLOUDAPI_VERSION_1_0_0 # noqa: E501
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.def_.models import DefEntityType
from container_service_extension.def_.models import DefInterface
from container_service_extension.def_.utils import raise_error_if_def_not_supported # noqa: E501
from container_service_extension.shared_constants import RequestMethod


# TODO(DEF) Exception handling.
class DefSchemaService():
    """Manages lifecycle of defined entity interfaces and entity types."""

    def __init__(self, cloudapi_client: CloudApiClient):
        if not cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    def list_interfaces(self):
        """List defined entity interfaces.

        :return: Generator of interfaces
        :rtype: Generator
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.INTERFACES}?"
                f"page={page_num}")
            if len(response_body['values']) > 0:
                for interface in response_body['values']:
                    yield DefInterface(**interface)
            else:
                break

    def get_interface(self, id: str) -> DefInterface:
        """Get the interface given an id.

        :param str id: Id if the interface.
        :return: Interface
        :rtype: DefInterface
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}/{id}")
        return DefInterface(**response_body)

    def create_interface(self, interface: DefInterface) -> DefInterface:
        """Create the Defined entity interface.

        :param DefInterface interface: body of the interface
        :return: Interface that is just created
        :rtype: DefInterface
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}",
            payload=asdict(interface))
        return DefInterface(**response_body)

    def update_interface(self, interface: DefInterface) -> DefInterface:
        """Update the Defined entity interface.

        As of May 2020, only name of the interface can be updated.

        :param DefInterface interface: Interface to be updated.
        :return: Interface that is just updated.
        :rtype: DefInterface
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.PUT,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}/"
            f"{interface.id}",
            payload=asdict(interface))
        return DefInterface(**response_body)

    def delete_interface(self, id: str) -> None:
        """Delete the defined entity interface.

        :param str id: Id of the interface.
        :return: None
        """
        return self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}/{id}")

    def create_entity_type(self, entity_type: DefEntityType) -> DefEntityType:
        """Create the Defined entity type.

        :param DefEntityType interface: body of the entity type
        :return: DefEntityType that is just created
        :rtype: DefEntityType
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}",
            payload=asdict(entity_type))
        return DefEntityType(**response_body)

    def get_entity_type(self, id: str) -> DefEntityType:
        """Get the entity type given an id.

        :param str id: Id of the interface.
        :return: Entity type
        :rtype: DefEntityType
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/{id}")
        return DefEntityType(**response_body)

    def list_entity_types(self):
        """List Entity types.

        :return: Generator of entity types
        :rtype: Generator[DefEntityType]
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}?"
                f"page={page_num}")
            if len(response_body['values']) > 0:
                for entityType in response_body['values']:
                    yield DefEntityType(**entityType)
            else:
                break

    def update_entity_type(self, entity_type: DefEntityType) -> DefEntityType:
        """Update the entity type.

        As of May 2020, only name and schema of the entity type can be
        updated.

        :param entity_type: Entity type to be updated.
        :return: Updated entity type
        :rtype: DefEntityType
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.PUT,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/"
            f"{entity_type.id}",
            payload=asdict(entity_type))
        return DefEntityType(**response_body)

    def delete_entity_type(self, id: str) -> None:
        """Delete the entity type given an id.

        :param str id: Id of the entity type to be deleted.
        :return: None
        """
        self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}/{id}")
