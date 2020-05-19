# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
from typing import List

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CLOUDAPI_VERSION_1_0_0 # noqa: E501
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.def_modules.models import DefEntityType, DefInterface # noqa: E501
from container_service_extension.shared_constants import RequestMethod


class DefSchemaService():
    """Manages lifecycle of defined entity interfaces and entity types.

    TODO Add API version check at the appropriate place. This class needs to
     be used if and only if vCD API version >= 35
    """

    def __init__(self, sysadmin_cloudapi_client: CloudApiClient):
        if not sysadmin_cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        self._cloudapi_client = sysadmin_cloudapi_client

    def list_interfaces(self) -> List[DefInterface]:
        """List defined entity interfaces.

        :return: list of interfaces
        :rtype: list
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}")
        return [DefInterface(**value) for value in response_body['values']]

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

    def list_entity_types(self) -> List[DefEntityType]:
        """List Entity types.

        :return: List of entity types
        :rtype: list of DefEntityType
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.ENTITY_TYPES}")
        return [DefEntityType(**value) for value in response_body['values']]

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
