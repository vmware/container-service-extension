import re

from lxml import etree
import pyvcloud.vcd.client as vcd_client
import requests

import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.server_constants as constants
from container_service_extension.server_constants import \
    MQTTExtKey, MQTTExtTokenKey
from container_service_extension.shared_constants import RequestMethod


def _get_id_from_extension_link(ext_link):
    """Get the id from an extension link.

    Expects the id to come after the "/extension/service/" parts of
        the link
    Example ext_link: '/admin/extension/service/12345/'
    Example return: '12345'

    :param str ext_link: the extension link to extract the id from

    :return: the extension id
    :rtype: str
    """
    link_dirs = ext_link.split('/')
    num_dirs = len(link_dirs)
    ind = 0
    while ind < num_dirs:
        # Ensure that the id comes after /extension/service
        if link_dirs[ind] == 'extension' and ind < num_dirs - 2 and \
                link_dirs[ind + 1] == 'service':
            return link_dirs[ind + 2]
        ind += 1
    return ''


def _get_id_from_api_filter_link(filter_link):
    """Get the id from an api filter link.

    Expects the id to come after the "/service/apifilter/" part of the link.
    Example filter_link: '/admin/service/apifilter/12345/'
    Example return: '12345'

    :return: the api filter id
    :rtype: str
    """
    link_dirs = filter_link.split('/')
    num_dirs = len(link_dirs)
    ind = 0
    while ind < num_dirs:
        if link_dirs[ind] == 'service' and ind < num_dirs - 2 and \
                link_dirs[ind + 1] == 'apifilter':
            return link_dirs[ind + 2]
        ind += 1
    return ''


def _parse_api_filter_pattern(initial_pattern):
    """Parse the url pattern from the initial api filter pattern.

    Example: initial_pattern = '\n     /api/endpoint\n      '
    The expected return would be: '/api/endpoint'.

    :param str initial_pattern: the raw api filter pattern

    :return: the parsed url pattern
    :rtype: str
    """
    return re.findall(pattern='/.+', string=initial_pattern)[0]


class MQTTExtensionManager:
    """Manages the extension, token, and api filter for the MQTT extension.

    This manager is also stateless; this is why multiple functions require the
    extension name, version, and vendor.

    Note: This extension can only be used with VCD API Version 35.0 and above.
    """

    def __init__(self, sysadmin_client: vcd_client.Client,
                 debug_logger=logger.SERVER_LOGGER, log_wire=True):
        # Ensure correct credentials and api version
        vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
        client_api_version = float(sysadmin_client.get_api_version())
        if client_api_version < constants.MQTT_MIN_API_VERSION:
            raise ValueError(f'API version {client_api_version} '
                             f'is less than required version '
                             f'{constants.MQTT_MIN_API_VERSION} to use MQTT')

        self._sysadmin_client: vcd_client.Client = sysadmin_client
        wire_logger = logger.NULL_LOGGER
        if log_wire:
            wire_logger = logger.SERVER_CLOUDAPI_WIRE_LOGGER
        self._wire_logger = wire_logger
        self._debug_logger = debug_logger
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                self._sysadmin_client, self._debug_logger, self._wire_logger)

    def setup_extension(self, ext_name, ext_version, ext_vendor,
                        priority=constants.MQTT_EXTENSION_PRIORITY,
                        ext_enabled=True, auth_enabled=False,
                        description=''):
        """Handle setting up the extension.

        If the extension is not created, this function handles
        creating it.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        :param int priority: extension priority (0-100); 50 is a neutral
            priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for
            the extension
        :param str description: description of the extension

        :return: a dictionary containing the extension urn id, listen topic,
            respond topic, and description
        :rtype: dict with fields: ext_urn_id, listen_topic, respond_topic,
            description

        :return: a tuple of urn_id, listen topic, and respond topic,
            each of type str. In case of any error, None is returned.
        :rtype: tuple
        """
        ext_info = self.get_extension_info(ext_name, ext_version, ext_vendor)
        if not ext_info:
            ext_info = self.create_extension(ext_name, ext_version,
                                             ext_vendor, priority,
                                             ext_enabled, auth_enabled,
                                             description)
        return ext_info

    def create_extension(self, ext_name, ext_version, ext_vendor,
                         priority=constants.MQTT_EXTENSION_PRIORITY,
                         ext_enabled=True, auth_enabled=False,
                         description=''):
        # TODO: check if authorization should be enabled as default
        """Create the MQTT extension.

        Note: vendor-name-version combination must be unique

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        :param int priority: extension priority (0-100); 50 is a neutral
            priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for
            the extension
        :param str description: description of the extension

        :return: a dictionary containing the extension urn id, listen topic,
            respond topic, and description
        :rtype: dict with fields: ext_urn_id, listen_topic, respond_topic,
            description
        :raises: HTTPError if unable to create the extension
        """
        payload = {
            MQTTExtKey.EXT_NAME: ext_name,
            MQTTExtKey.EXT_VERSION: ext_version,
            MQTTExtKey.EXT_VENDOR: ext_vendor,
            MQTTExtKey.EXT_PRIORITY: priority,
            MQTTExtKey.EXT_ENABLED: "true" if ext_enabled else "false",
            MQTTExtKey.EXT_AUTH_ENABLED: "true" if auth_enabled else "false",
            MQTTExtKey.EXT_DESCRIPTION: description
        }
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            resource_url_relative_path=constants.EXTENSIONS_API_PATH,
            payload=payload)
        mqtt_topics = response_body['mqttTopics']
        ext_info = {
            MQTTExtKey.EXT_URN_ID: response_body['id'],
            MQTTExtKey.EXT_LISTEN_TOPIC: mqtt_topics['monitor'],
            MQTTExtKey.EXT_RESPOND_TOPIC: mqtt_topics['respond'],
            MQTTExtKey.EXT_DESCRIPTION: response_body['description']
        }
        return ext_info

    def get_extension_info(self, ext_name, ext_version, ext_vendor):
        """Retrieve extension info.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor

        :return: a dictionary containing the extension urn id, listen topic,
            respond topic, and description
        :rtype: dict with fields: ext_urn_id, listen_topic, respond_topic,
            description
        :raises: HTTPError if unable to make the GET request
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            resource_url_relative_path=constants.EXTENSIONS_API_PATH)
        all_ext_info_arr = response_body['values']

        # Find extension
        ext_info = None
        for curr_info in all_ext_info_arr:
            if curr_info['name'] == ext_name and \
                    curr_info['version'] == ext_version \
                    and curr_info['vendor'] == ext_vendor:
                mqtt_topics = curr_info['mqttTopics']
                ext_info = {
                    MQTTExtKey.EXT_URN_ID: curr_info['id'],
                    MQTTExtKey.EXT_LISTEN_TOPIC: mqtt_topics['monitor'],
                    MQTTExtKey.EXT_RESPOND_TOPIC: mqtt_topics['respond'],
                    MQTTExtKey.EXT_DESCRIPTION: curr_info['description']
                }
                break
        return ext_info

    def get_extension_info_by_urn(self, ext_urn_id):
        """Get the extension with the specified id.

        :param str ext_urn_id: the extension urn id

        :return: the response body of the GET request for the extension
        :rtype: dict
        :raises: HTTPError if unable to make the GET request
        """
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            resource_url_relative_path=f"{constants.EXTENSIONS_API_PATH}/"
                                       f"{ext_urn_id}")
        return response_body

    def get_extension_uuid(self, ext_urn_id):
        """Retrieve the extension uuid.

        :param str ext_urn_id: the extension urn id

        :return: the extension uuid
        :rtype: str
        """
        # retrieve string of links and get id from the string of links
        _ = self.get_extension_info_by_urn(ext_urn_id)  # Make last response
        ext_response_headers = self._cloudapi_client.\
            get_last_response_headers()
        links_str = ext_response_headers['Link']
        return _get_id_from_extension_link(links_str)

    def update_extension(self, ext_name, ext_version, ext_vendor,
                         priority=constants.MQTT_EXTENSION_PRIORITY,
                         ext_enabled=True, auth_enabled=False,
                         description=''):
        """Update extension with the passed values.

        Note: extension name, version, and vendor cannot be updated

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        :param int priority: extension priority (0-100);
            50 is a neutral priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for
            the extension
        :param str description: description of the extension

        :raises: HTTPError if unable to make the PUT request or the GET request
            when getting the extension info
        """
        ext_info = self.get_extension_info(ext_name, ext_version, ext_vendor)
        if not ext_info:
            self._debug_logger.error('No extension found in update_extension')
            return
        ext_urn_id = ext_info[MQTTExtKey.EXT_URN_ID]
        payload = {
            MQTTExtKey.EXT_NAME: ext_name,
            MQTTExtKey.EXT_VERSION: ext_version,
            MQTTExtKey.EXT_VENDOR: ext_vendor,
            MQTTExtKey.EXT_PRIORITY: priority,
            MQTTExtKey.EXT_ENABLED: "true" if ext_enabled else "false",
            MQTTExtKey.EXT_AUTH_ENABLED: "true" if auth_enabled else "false",
            MQTTExtKey.EXT_DESCRIPTION: description
        }
        self._cloudapi_client.do_request(
            method=RequestMethod.PUT,
            resource_url_relative_path=f"{constants.EXTENSIONS_API_PATH}/"
                                       f"{ext_urn_id}",
            payload=payload)

    def delete_extension(self, ext_name, ext_version, ext_vendor, ext_urn_id):
        """Delete the extension.

        The extension is first powered off so that it can be deleted.
        Note: deleting an extension also deletes its tokens and api filters.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        :param str ext_urn_id: the extension urn id

        :raises: HTTPError if unable to turn the extension off or
            make the DELETE request
        """
        # Turn extension off before deleting
        self.update_extension(ext_name, ext_version, ext_vendor,
                              ext_enabled=False)

        self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            resource_url_relative_path=f"{constants.EXTENSIONS_API_PATH}/"
                                       f"{ext_urn_id}")

    def check_extension_exists(self, ext_urn_id):
        """Check if the MQTT extension exists.

        :param str ext_urn_id: the extension urn id

        :return: status of the MQTT extension
        :rtype: bool
        """
        try:
            _ = self.get_extension_info_by_urn(ext_urn_id)
            return True
        except requests.exceptions.HTTPError:
            last_response = self._cloudapi_client.get_last_response()
            self._debug_logger.debug(last_response.text)
            return False

    def setup_extension_token(self, token_name, ext_name, ext_version,
                              ext_vendor, ext_urn_id):
        """Handle setting up a single extension token.

        Ensures that there is only one token for the extension,
        so all tokens are deleted first.

        :return: dictionary containing the token and token id
        :rtype: dict with fields: token and token_id
        """
        self.delete_all_extension_tokens(ext_name, ext_version, ext_vendor)
        return self.create_extension_token(token_name, ext_urn_id)

    def create_extension_token(self, token_name, ext_urn_id):
        """Create a long live token.

        Note: the token can only be retrieved upon creation. Following GET
        calls for the token will show the token censored. Therefore, a new
        token must be recreated each time.

        :param str token_name: token name
        :param str ext_urn_id: the extension urn id

        :return: dictionary containing the token and token id
        :rtype: dict with fields: token and token_id
        :raises: HTTPError if unable to make the POST request
        """
        payload = {
            MQTTExtTokenKey.TOKEN_NAME: token_name,
            MQTTExtTokenKey.TOKEN_TYPE: "EXTENSION",
            MQTTExtTokenKey.TOKEN_EXT_ID: ext_urn_id
        }
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=constants.TOKEN_PATH,
            payload=payload)
        token_info = {
            MQTTExtTokenKey.TOKEN: response_body['token'],
            MQTTExtTokenKey.TOKEN_ID: response_body['id']
        }
        return token_info

    def get_all_extension_token_ids(self, ext_name, ext_version, ext_vendor):
        """Get all of the extension's token ids.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor

        :return: list of token ids (str)
        :rtype: list of strs
        :raises: HTTPError if unable to make the GET request
        """
        token_ids = []
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=constants.TOKEN_PATH)
        ext_combine_name = f"{ext_vendor}/{ext_name}/{ext_version}"
        for token_info in response_body['values']:
            if token_info['owner']['name'] == ext_combine_name:
                token_ids.append(token_info['id'])
        return token_ids

    def delete_extension_token(self, token_id):
        """Delete the specified token with token_id.

        :param str token_id: the token's id
        :raises: HTTPError if unable to make the delete request
        """
        self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=f"{constants.TOKEN_PATH}/"
                                       f"{token_id}")

    def delete_all_extension_tokens(self, ext_name, ext_version, ext_vendor):
        """Delete all of the extension's tokens.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor

        :raises: HTTPError if unable to delete any of the tokens
        """
        token_ids = self.get_all_extension_token_ids(ext_name, ext_version,
                                                     ext_vendor)
        for token_id in token_ids:
            self.delete_extension_token(token_id)

    def check_extension_token_exists(self, token_id):
        """Check if the instance's token is active by doing a GET request.

        :return: status of the token: True if active and False if not
        :rtype: bool
        """
        active = True
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{constants.TOKEN_PATH}/"
                                           f"{token_id}")
        except requests.exceptions.HTTPError:
            active = False
        return active

    def setup_api_filter(self, api_filter_url_pattern, ext_uuid):
        """Handle setting up api filter and returns its id.

        Creates the filter if it has not been created. Also handles
        possibility of more than one api filter being created with the same
        endpoint path. Deletes any extra api filters.

        :param str api_filter_url_pattern: the url pattern for the api filter,
            e.g., '/api/mqttEndpoint'
        :param str ext_uuid: the extension uuid

        :return: id of api filter. In case of any error, the empty string
            is returned.
        :rtype: str
        :raises: Exception if error in creating api filter or deleting extra
            api filters
        """
        active_api_filter_ids = self.get_api_filter_ids(api_filter_url_pattern,
                                                        ext_uuid)
        if not active_api_filter_ids:
            return self.create_api_filter(api_filter_url_pattern, ext_uuid)
        elif len(active_api_filter_ids) > 1:
            # Ensure only one api filter
            for filter_id in active_api_filter_ids[1:]:
                self.delete_api_filter(filter_id)
        return active_api_filter_ids[0]

    def create_api_filter(self, api_filter_url_pattern, ext_uuid):
        """Create the api filter for the extension endpoint.

        :param str api_filter_url_pattern: the url pattern for the api filter,
            e.g., '/api/mqttEndpoint'
        :param str ext_uuid: The extension uuid

        :return: id of the api filter. In case of any error, the empty string
            is returned.
        :rtype: str
        :raises: Exception if error in making POST request
        """
        xml_etree = etree.XML(
            f"""
            <vmext:ApiFilter xmlns:vmext =
                "http://www.vmware.com/vcloud/extension/v1.5">
                <vmext:UrlPattern>
                    {api_filter_url_pattern}
                </vmext:UrlPattern >
            </vmext:ApiFilter>
            """)
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
            f"/{constants.ADMIN_EXT_SERVICE_PATH}/{ext_uuid}" \
            f"/{constants.API_FILTERS_PATH}"

        response_body = self._sysadmin_client.post_resource(
            uri=absolute_api_filters_url,
            contents=xml_etree,
            media_type=vcd_client.EntityType.API_FILTER.value)
        api_filter_id = _get_id_from_api_filter_link(
            response_body.attrib['href'])
        return api_filter_id

    def get_api_filter_ids(self, api_filter_url_pattern, ext_uuid):
        """Retrieve all api filter ids with the passed in path.

        :param str api_filter_url_pattern: the url pattern for the api filter,
            e.g., '/api/mqttEndpoint'
        :param str ext_uuid: the extension uuid

        :return: list of api filter ids
        :rtype: list of strs
        :raises: Exception if error in making GET request
        """
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/{constants.ADMIN_EXT_SERVICE_PATH}/" \
                                   f"{ext_uuid}/{constants.API_FILTERS_PATH}"
        filter_ids = []
        response_body = self._sysadmin_client.get_resource(
            uri=absolute_api_filters_url)

        # Because response_body is an ObjectifiedElement and not a dict,
        # we need to use a try-except to see if it has an api filter record
        try:
            api_filters = response_body.ApiFilterRecord
        except AttributeError:
            return filter_ids
        for filter_info in api_filters:
            curr_filter_url_pattern = _parse_api_filter_pattern(
                filter_info.attrib['urlPattern'])
            if curr_filter_url_pattern == api_filter_url_pattern:
                filter_id = _get_id_from_api_filter_link(
                    filter_info.attrib['href'])
                filter_ids.append(filter_id)
        return filter_ids

    def delete_api_filter(self, filter_id):
        """Delete the api filter.

        :param str filter_id: filter id
        :raises: Exception if error in making DELETE request
        """
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/{constants.ADMIN_EXT_SERVICE_PATH}/" \
                                   f"{constants.API_FILTER_PATH}/{filter_id}"
        self._sysadmin_client.delete_resource(absolute_api_filters_url)

    def check_api_filter_exists(self, api_filter_id):
        """Check if the api filter is active.

        :param str api_filter_id: the api filter id

        :return: status of the api filter
        :rtype: bool
        """
        extension_api_filter_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/{constants.ADMIN_EXT_SERVICE_PATH}/" \
                                   f"{constants.API_FILTER_PATH}/" \
                                   f"{api_filter_id}"
        active = True
        try:
            _ = self._sysadmin_client.get_resource(
                uri=extension_api_filter_url)
        except Exception:
            active = False
        return active
