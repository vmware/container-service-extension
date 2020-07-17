import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.api_client import ApiClient

import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.shared_constants import RequestMethod
import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.logger as logger
from lxml import etree
import requests
import container_service_extension.server_constants as constants

EXTENSION_SERVICE_PATH = '/extension/service/'


def get_id_from_link(link, id_path):
    ext_service_ind = link.find(id_path)
    if ext_service_ind == -1:
        return None
    start_ind = ext_service_ind + len(id_path)
    end_offset = link[start_ind:].find('/')
    if end_offset == -1:  # if link ends in id
        end_offset = len(link)
    return link[start_ind:start_ind + end_offset]


class MQTTExtensionManager:
    """Manages setting up the extension for MQTT, including
    handling token creation and deletion
    """

    def __init__(self, sysadmin_client: vcd_client.Client):
        # Ensure correct credentials and api version
        vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
        client_api_version = float(sysadmin_client.get_api_version())
        if client_api_version < constants.MQTT_MIN_API_VERSION:
            raise ValueError(f'API version {client_api_version} '
                             f'is less than required version '
                             f'{constants.MQTT_MIN_API_VERSION} to use MQTT')

        self._sysadmin_client: vcd_client.Client = sysadmin_client
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(self._sysadmin_client)
        # TODO retrieve other fields e.g., extension and token info
        self._ext_name = constants.CSE_SERVICE_NAME
        self._ext_version = constants.MQTT_EXTENSION_VERSION
        self._ext_vendor = constants.MQTT_EXTENSION_VENDOR
        self._ext_combine_name = f"{self._ext_vendor}/{self._ext_name}/" \
                                 f"{self._ext_version}"

        # Setup extension info
        ext_info = self._setup_extension()
        self._ext_urn_id, self._listen_topic, self._respond_topic = ext_info
        self._ext_uuid = self._get_extension_uuid()
        # TODO handle extension, token, or api filter not setting up properly

        # TODO make getter functions

        self._token, self._token_id = self._setup_extension_token()

        # api filter setup
        self._absolute_api_filters_url = \
            f"{self._sysadmin_client.get_api_uri()}" \
            f"/admin/extension/service/{self._ext_uuid}/apifilters"
        self._api_filter_id = self._setup_api_filter()

    def _setup_extension(self):
        """Handles setting up the extension.

        If the extension is not created, this function handles
        creating it.

        :return: a tuple of urn_id, listen topic, and respond topic,
            each of type str
        :rtype: tuple
        """
        ext_info = self._get_extension_info()
        if not ext_info:
            ext_info = self._create_extension()
        return ext_info

    def _create_extension(self, priority=constants.MQTT_EXTENSION_PRIORITY,
                          ext_enabled=True, auth_enabled=False):
        # TODO: check if authorization should be enabled
        """Makes a request to create an extension
        Note: vendor-name-version combination must be unique

        :param int priority: extension priority (0-100); 50 is a neutral
            priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for
            the extension

        :return: a tuple of urn_id, listen topic, and respond topic,
            each of type str
        :rtype: tuple
        """
        payload = {
            "name": self._ext_name,
            "version": self._ext_version,
            "vendor": self._ext_vendor,
            "priority": priority,
            "enabled": "true" if ext_enabled else "false",
            "authorizationEnabled": "true" if auth_enabled else "false"
        }
        ext_info = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.POST,
                resource_url_relative_path='extensions/api',
                payload=payload)
            mqtt_topics = response_body['mqttTopics']
            ext_info = (response_body['id'], mqtt_topics['monitor'],
                        mqtt_topics['respond'])
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return ext_info

    def _get_extension_info(self):
        """Retrieves extension info.

        :return: a tuple of urn_id, listen topic, and respond topic,
            each of type str
        :rtype: tuple
        """
        ext_info = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                resource_url_relative_path="extensions/api")
            ext_info_arr = response_body['values']

            # Find extension
            for curr_info in ext_info_arr:
                if curr_info['name'] == self._ext_name and \
                        curr_info['version'] == self._ext_version \
                        and curr_info['vendor'] == self._ext_vendor:
                    mqtt_topics = curr_info['mqttTopics']
                    ext_info = (curr_info['id'], mqtt_topics['monitor'],
                                mqtt_topics['respond'])
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return ext_info

    def _get_extension_response_body(self):
        """Gets the extension with the specified id

        :return: the response body of the GET request for the extension
        :rtype: dict
        """
        response_body = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                resource_url_relative_path=f"extensions/api/{self._ext_urn_id}")
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return response_body

    def _get_extension_uuid(self):
        """ Retrieves the extension uuid

        :return: the extension uuid
        :rtype: str
        """
        # retrieve string of links and get id from the string of links
        _ = self._get_extension_response_body()  # ensure the last response
        ext_response_headers = self._cloudapi_client.get_last_response_headers()
        links_str = ext_response_headers['Link']
        return get_id_from_link(links_str, EXTENSION_SERVICE_PATH)

    def _update_extension(self, priority=constants.MQTT_EXTENSION_PRIORITY,
                          ext_enabled=True, auth_enabled=False):
        """Updates extension with the passed values.

        Note: extension name, version, and vendor cannot be updated

        :param int priority: extension priority (0-100);
            50 is a neutral priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for
            the extension

        :return: status of the update: True if successful, False otherwise
        :rtype: bool
        """
        payload = {
            "name": self._ext_name,
            "version": self._ext_version,
            "vendor": self._ext_vendor,
            "priority": priority,
            "enabled": "true" if ext_enabled else "false",
            "authorizationEnabled": "true" if auth_enabled else "false"
        }
        success = True
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.PUT,
                resource_url_relative_path=f"extensions/api/{self._ext_urn_id}",
                payload=payload)
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
            success = False
        return success

    def delete_extension(self):
        """Deletes the extension.

        The extension is first powered off so that it can be deleted.
        Note: deleting an extension also deletes its tokens and api filters.

        :return: status of the deletion
        :rtype: bool
        """
        # Turn extension off
        update_result = self._update_extension(ext_enabled=False)
        if not update_result:
            return False
        success = True
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                resource_url_relative_path=f"extensions/api/{self._ext_urn_id}")

            # Set fields of self to None
            for attr in self.__dict__.keys():  # may be self.__dict__.keys()
                setattr(self, attr, None)

        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
            success = False
        return success

    def _setup_extension_token(self):
        """Wrapper function that handles setting up a single extension token.

        Ensures that there is only one token for the extension,
        so all tokens are deleted first.

        :return: tuple of token and token id, in that order, each of type str
        :rtype: tuple of strs
        """
        self._delete_all_extension_tokens()
        return self._create_extension_token()

    def _create_extension_token(self):
        """Creates a long live token with the name based on the constant
        MQTT_TOKEN_NAME.

        :return: tuple of token and token id, in that order, each of type str
        :rtype: tuple of strs
        """
        payload = {
            "name": constants.MQTT_TOKEN_NAME,
            "type": "EXTENSION",
            "extensionId": self._ext_urn_id
        }
        token_tuple = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.POST,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path="tokens",
                payload=payload)
            token_tuple = (response_body['token'], response_body['id'])
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return token_tuple

    def _get_all_extension_token_ids(self):
        """Gets all of the extension's token ids

        :return: list of token ids (str)
        :rtype: list of strs
        """
        token_ids = []
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path="tokens")
            for token_info in response_body['values']:
                if token_info['owner']['name'] == self._ext_combine_name:
                    token_ids.append(token_info['id'])
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return token_ids

    def _delete_extension_token(self, token_id):
        """Deletes the specified token with token_id

        :param str token_id: the token's id
        """
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"tokens/{token_id}")
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)

    def _delete_all_extension_tokens(self):
        """Deletes all of the extension's tokens"""
        token_ids = self._get_all_extension_token_ids()
        for tok_id in token_ids:
            self._delete_extension_token(tok_id)

    def check_extension_token_status(self):
        """Checks if the instance's token is active by doing a GET request.

        :return: status of the token: True if active and False if not
        :rtype: bool
        """
        active = True
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"tokens/{self._token_id}")
        except requests.exceptions.HTTPError:
            active = False
        return active

    def _setup_api_filter(self):
        """Handles setting up api filter and returns its id.

        Creates the filter if it has not been created. Also handles
        possibility of more than one api filter being created with the same
        endpoint path. Deletes any extra api filters. R

        :return: id of api filter
        :rtype: str
        """
        active_api_filter_ids = self._get_api_filter_ids()
        # self._delete_api_filter(active_api_filter_ids[0])
        if not active_api_filter_ids:
            return self._create_api_filter()
        elif len(active_api_filter_ids) > 1:
            for filter_id in range(1, len(active_api_filter_ids)):
                self._delete_api_filter(filter_id)
        return active_api_filter_ids[0]

    def _create_api_filter(self):  # TODO: check type of id: urn vs no urn
        """Create the api filter for the extension endpoint.

        :return: id of the api filter
        :rtype: str
        """
        xml_etree = etree.XML(
            f"""
            <vmext:ApiFilter xmlns:vmext = 
                "http://www.vmware.com/vcloud/extension/v1.5">
                <vmext:UrlPattern>
                    {constants.MQTT_ENDPOINT_PATH}
                </vmext:UrlPattern >
            </vmext:ApiFilter>
            """)
        api_filter_id = None
        try:
            response_body = self._sysadmin_client.post_resource(
                uri=self._absolute_api_filters_url,
                contents=xml_etree,
                media_type=vcd_client.EntityType.API_FILTER.value)
            api_filter_id = get_id_from_link(response_body.attrib['href'],
                                             constants.API_FILTER_PATH)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
        return api_filter_id

    def _get_api_filter_ids(self):
        """Retrieves all api filter ids with the MQTT endpoint path.

        :return: list of api filter ids
        :rtype: list of strs
        """
        filter_ids = []
        try:
            response_body = self._sysadmin_client.get_resource(
                uri=self._absolute_api_filters_url)
            api_filters = response_body['ApiFilterRecord']
            for filter_info in api_filters:
                if filter_info.attrib['urlPattern'] == \
                        constants.MQTT_ENDPOINT_PATH:
                    filter_id = get_id_from_link(filter_info.attrib['href'])
                    filter_ids.append(filter_id, constants.API_FILTER_PATH)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
        return filter_ids

    def check_api_filter_status(self):
        extension_api_filter_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/apifilter/" \
                                   f"{self._api_filter_id}"
        active = True
        try:
            _ = self._sysadmin_client.get_resource(
                uri=extension_api_filter_url)
        except _:
            active = False
        return active

    def _delete_api_filter(self, filter_id):
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/apifilter/" \
                                   f"{filter_id}"
        try:
            self._sysadmin_client.delete_resource(absolute_api_filters_url)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
