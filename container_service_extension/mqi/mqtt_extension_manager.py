# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from lxml import etree
import pyvcloud.vcd.client as vcd_client
import requests

import container_service_extension.common.constants.server_constants as constants  # noqa: E501
from container_service_extension.common.constants.server_constants import \
    MQTTExtKey, MQTTExtTokenKey
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.lib.cloudapi.constants as cloudapi_constants
import container_service_extension.logging.logger as logger


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


class MQTTExtensionManager:
    """Manages the extension, token, and api filter for the MQTT extension.

    This manager is also stateless; this is why multiple functions require the
    extension name, version, and vendor.

    Note: This extension can only be used with VCD API Version 35.0 and above.
    """

    def __init__(self, sysadmin_client: vcd_client.Client,
                 debug_logger=logger.SERVER_LOGGER, log_wire=True):
        # Ensure correct credentials and api version
        vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
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
        raises: HTTPError if unable to make the GET request for the extension
            of if unable to create the extension
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
            MQTTExtKey.EXT_ENABLED: response_body['enabled'],
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
                    MQTTExtKey.EXT_ENABLED: curr_info['enabled'],
                    MQTTExtKey.EXT_DESCRIPTION: curr_info['description']
                }
                break
        return ext_info

    def get_extension_response_body_by_urn(self, ext_urn_id):
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
        :raises: HTTPError if unable to make the GET request for the extension
            info
        """
        # retrieve string of links and get id from the string of links
        # First, ensure that the GET for the extension is the last request
        _ = self.get_extension_response_body_by_urn(ext_urn_id)
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
            _ = self.get_extension_response_body_by_urn(ext_urn_id)
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
        return self._create_extension_token(token_name, ext_urn_id)

    def _create_extension_token(self, token_name, ext_urn_id):
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
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
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
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
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
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
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
                cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                resource_url_relative_path=f"{constants.TOKEN_PATH}/"
                                           f"{token_id}")
        except requests.exceptions.HTTPError:
            active = False
        return active

    def setup_api_filter_patterns(self, ext_uuid, patterns):
        """Set up all of the specified api filter patterns.

        Note: function assumes that all patterns are unique.

        :param str ext_uuid: the extension uuid
        :param list patterns: list of api filter patterns

        :return: dict of filter pattern keys mapped to id values
        :rtype: dict of str keys and str values
        """
        pattern_to_ids = self.get_api_filter_ids_for_patterns(ext_uuid,
                                                              patterns)
        if not pattern_to_ids:
            return self.create_api_filter_patterns(ext_uuid, patterns)
        elif len(pattern_to_ids) == len(patterns):
            # Ensure each filter only has one id
            pattern_to_one_id = {}
            for pattern in patterns:
                filter_ids = pattern_to_ids[pattern]
                pattern_to_one_id[pattern] = filter_ids[0]
                self.delete_extra_api_filters(filter_ids)
            return pattern_to_one_id
        else:
            # Fewer patterns created than needed, so add the needed filters,
            # and ensure the created filters only have one id
            pattern_to_one_id = {}
            for pattern in patterns:
                filter_ids = pattern_to_ids.get(pattern)
                if not filter_ids:
                    pattern_to_one_id[pattern] = self.create_api_filter(
                        ext_uuid, pattern)
                else:
                    pattern_to_one_id[pattern] = filter_ids[0]
                    self.delete_extra_api_filters(filter_ids)
            return pattern_to_one_id

    def delete_extra_api_filters(self, api_filter_ids):
        """Delete any extra API filters.

        :param list api_filter_ids: list of api filter ids
        """
        if len(api_filter_ids) > 1:
            for filter_id in api_filter_ids[1:]:
                self.delete_api_filter_by_id(filter_id)

    def create_api_filter(self, ext_uuid, api_filter_pattern):
        """Create the api filter for the extension endpoint.

        :param str ext_uuid: The extension uuid
        :param str api_filter_pattern: api filter pattern

        :return: id of the api filter. In case of any error, the empty string
            is returned.
        :rtype: str
        :raises: Exception if error in making POST request
        """
        xml_str = \
            f"<vmext:ApiFilter xmlns:vmext =" \
            f"\"http://www.vmware.com/vcloud/extension/v1.5\">" \
            f"<vmext:UrlPattern>{api_filter_pattern}" \
            f"</vmext:UrlPattern ></vmext:ApiFilter>"
        xml_etree = etree.XML(xml_str)
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

    def create_api_filter_patterns(self, ext_uuid, patterns):
        """Create all the api filters in the given list.

        Note: function assumes that all patterns are unique.

        :param str ext_uuid: the extension uuid
        :param list patterns: list of api filter patterns

        :return: dict of filter pattern keys mapped to filter ids
        :rtype: dict of str keys and str values
        """
        filter_ids = {}
        for pattern in patterns:
            filter_id = self.create_api_filter(ext_uuid, pattern)
            filter_ids[pattern] = filter_id
        return filter_ids

    def get_api_filter_ids_for_patterns(self, ext_uuid, patterns):
        """Retrieve the api filters.

        Note: function assumes that all patterns are unique.

        :param str ext_uuid: the extension uuid
        :param list patterns: list of api filter patterns

        :return: dict of filter pattern keys mapped to list of ids
        :rtype: dict of str keys and list values
        :raises: Exception if error in making GET request
        """
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/{constants.ADMIN_EXT_SERVICE_PATH}/" \
                                   f"{ext_uuid}/{constants.API_FILTERS_PATH}"
        pattern_to_ids = {}
        response_body = self._sysadmin_client.get_resource(
            uri=absolute_api_filters_url)

        # Because response_body is an ObjectifiedElement and not a dict,
        # we need to use a try-except to see if it has an api filter record
        try:
            api_filters = response_body.ApiFilterRecord
        except AttributeError:
            return pattern_to_ids
        patterns_set = set(patterns)
        for filter_info in api_filters:
            curr_pattern = filter_info.attrib['urlPattern']
            if curr_pattern in patterns_set:
                filter_id = _get_id_from_api_filter_link(
                    filter_info.attrib['href'])

                # Init or add to current array of ids
                curr_ids = pattern_to_ids.get(curr_pattern, [])
                curr_ids.append(filter_id)
                pattern_to_ids[curr_pattern] = curr_ids
        return pattern_to_ids

    def delete_api_filter_by_id(self, filter_id):
        """Delete the api filter.

        :param str filter_id: filter id

        :raises: Exception if error in making DELETE request
        """
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/{constants.ADMIN_EXT_SERVICE_PATH}/" \
                                   f"{constants.API_FILTER_PATH}/{filter_id}"
        self._sysadmin_client.delete_resource(absolute_api_filters_url)

    def delete_api_filter_patterns(self, ext_uuid, patterns):
        """Delete the api filter patterns for the extension.

        :param str ext_uuid: the extension uuid
        :param list patterns: list of api filter patterns
        """
        pattern_to_ids = self.get_api_filter_ids_for_patterns(ext_uuid,
                                                              patterns)
        for filter_ids in pattern_to_ids.values():
            for filter_id in filter_ids:
                self.delete_api_filter_by_id(filter_id)

    def check_api_filter_id_exists(self, api_filter_id):
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

    def check_api_filters_setup(self, ext_uuid, patterns):
        """Check if the api filters passed in are set up.

        Note: function assumes that all patterns are unique.

        :param str ext_uuid: the extension uuid
        :param list patterns: list of api filter patterns

        :return: true if the filters are set up and false if not
        :rtype: bool
        """
        pattern_to_ids = self.get_api_filter_ids_for_patterns(ext_uuid,
                                                              patterns)
        # filter_ids have at most one entry (list) per pattern
        return len(patterns) == len(pattern_to_ids)
