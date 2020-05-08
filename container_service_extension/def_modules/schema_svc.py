# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException
from requests.exceptions import HTTPError

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CLOUDAPI_VERSION_1_0_0 # noqa: E501
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import DEF_CSE_VENDOR
from container_service_extension.cloudapi.constants import DEF_ENTITY_TYPE_ID_PREFIX # noqa: E501
from container_service_extension.cloudapi.constants import DEF_INTERFACE_ID_PREFIX # noqa: E501
from container_service_extension.cloudapi.constants import DEF_NATIVE_ENTITY_TYPE_NSS # noqa: E501
from container_service_extension.cloudapi.constants import DEF_NATIVE_ENTITY_TYPE_VERSION # noqa: E501
from container_service_extension.cloudapi.constants import DEF_NATIVE_INTERFACE_NSS # noqa: E501
from container_service_extension.cloudapi.constants import DEF_NATIVE_INTERFACE_VERSION # noqa: E501
from container_service_extension.def_modules.models import DefEntityType, DefInterface # noqa: E501
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.shared_constants import RequestMethod


class DefSchemaSvc():
    """Manages lifecycle of defined entity interfaces and entity types."""

    def __init__(self, client):
        """Initialize DefSchemaSvc Object.

        :param pyvcloud.vcd.client client:

        :raises: OperationNotSupportedException: If cloudapi endpoint is not
        found in session.
        :raises: ValueError: If non sys admin client is passed during
        initialization.
        """
        if not client.is_sysadmin():
            raise ValueError("Only Sys admin clients should be used to "
                             "initialize ComputePolicyManager.")
        self._vcd_client = client

        token = self._vcd_client.get_access_token()
        is_jwt_token = True
        if not token:
            token = self._vcd_client.get_xvcloud_authorization_token()
            is_jwt_token = False

        self._session = self._vcd_client.get_vcloud_session()

        try:
            self._cloudapi_client = CloudApiClient(
                base_url=self._vcd_client.get_cloudapi_uri(),
                token=token,
                is_jwt_token=is_jwt_token,
                api_version=self._vcd_client.get_api_version(),
                verify_ssl=self._vcd_client._verify_ssl_certs)
            # Since the /cloudapi endpoint was added before the defined entity
            # endpoint. Mere presence of the /cloudapi uri is not enough, we
            # need to make sure that this cloud api client will be of actual
            # use to us.
            self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.INTERFACES}")  # noqa: E501
        except HTTPError as err:
            LOGGER.error(err)
            raise OperationNotSupportedException(
                "Cloudapi endpoint unavailable at current api version.")

    def list_interfaces(self) -> list:
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

    def construct_native_interface_id(self) -> str:
        """Return the interface Id of CSE's interface.

        example: "urn:vcloud:interface:cse.native:1.0.0"

        :return: Id of the interface
        :rtype: str
        """
        return f"{DEF_INTERFACE_ID_PREFIX}:{DEF_CSE_VENDOR}:" \
            f"{DEF_NATIVE_INTERFACE_NSS}:{DEF_NATIVE_INTERFACE_VERSION}"

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
            payload=interface._asdict())
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
            payload=interface._asdict())
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
            payload=entity_type._asdict())
        return DefEntityType(**response_body)

    def construct_native_entity_type_id(self) -> str:
        """Return the entity type Id of CSE's Native cluster.

        example: "urn:vcloud:type:cse.nativeCluster:1.0.0"

        :return: Id of the interface
        :rtype: str
        """
        return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{DEF_CSE_VENDOR}:" \
            f"{DEF_NATIVE_ENTITY_TYPE_NSS}:{DEF_NATIVE_ENTITY_TYPE_VERSION}"

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

    def list_entity_types(self) -> list:
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
            payload=entity_type._asdict())
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
