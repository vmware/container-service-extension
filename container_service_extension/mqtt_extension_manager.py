from lxml import etree
import pyvcloud.vcd.client as vcd_client
import requests

import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.server_constants as constants
from container_service_extension.shared_constants import RequestMethod


def get_id_from_link(link, id_path):
    """Get the id from the link.

    :param str link: url link (may be multiple links concatenated)
    :param str id_path: path before the id

    :return: the id
    :rtype: str
    """
    ext_service_ind = link.find(id_path)
    if ext_service_ind == -1:
        return None
    start_ind = ext_service_ind + len(id_path)
    end_offset = link[start_ind:].find('/')
    if end_offset == -1:  # if link ends in id
        end_offset = len(link)
    return link[start_ind:start_ind + end_offset]


def parse_url_pattern(initial_pattern):
    """Parse the url pattern from the initial pattern.

    :param str initial_pattern: the raw pattern

    :return: the parsed url pattern
    :rtype: str
    """
    pattern_start_ind = initial_pattern.find('/')
    pattern_end_ind = initial_pattern.rfind('\n')
    if pattern_end_ind == -1:
        pattern_end_ind = len(initial_pattern)
    return initial_pattern[pattern_start_ind:pattern_end_ind]


class MQTTExtensionManager:
    """Manages the extension, token, and api filter for the MQTT extension.

    This manager is also stateless; this is why multiple functions require the
    extension name, version, and vendor.

    Note: This extension can only be used with VCD API Version 35.0 and above.
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
            vcd_utils.get_cloudapi_client_from_vcd_client(
                self._sysadmin_client)

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
        """
        payload = {
            "name": ext_name,
            "version": ext_version,
            "vendor": ext_vendor,
            "priority": priority,
            "enabled": "true" if ext_enabled else "false",
            "authorizationEnabled": "true" if auth_enabled else "false",
            'description': description
        }
        ext_info = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.POST,
                resource_url_relative_path='extensions/api',
                payload=payload)
            mqtt_topics = response_body['mqttTopics']
            ext_info = {'ext_urn_id': response_body['id'],
                        'listen_topic': mqtt_topics['monitor'],
                        'respond_topic': mqtt_topics['respond'],
                        'description': response_body['description']}
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
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
        """
        ext_info = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                resource_url_relative_path="extensions/api")
            ext_info_arr = response_body['values']

            # Find extension
            for curr_info in ext_info_arr:
                if curr_info['name'] == ext_name and \
                        curr_info['version'] == ext_version \
                        and curr_info['vendor'] == ext_vendor:
                    mqtt_topics = curr_info['mqttTopics']
                    ext_info = {'ext_urn_id': curr_info['id'],
                                'listen_topic': mqtt_topics['monitor'],
                                'respond_topic': mqtt_topics['respond'],
                                'description': curr_info['description']}
                    break
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return ext_info

    def get_extension_response_body(self, ext_urn_id):
        """Get the extension with the specified id.

        :param str ext_urn_id: the extension urn id

        :return: the response body of the GET request for the extension
        :rtype: dict
        """
        response_body = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                resource_url_relative_path=f"extensions/api/"
                                           f"{ext_urn_id}")
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return response_body

    def get_extension_uuid(self, ext_urn_id):
        """Retrieve the extension uuid.

        :param str ext_urn_id: the extension urn id

        :return: the extension uuid
        :rtype: str
        """
        # retrieve string of links and get id from the string of links
        _ = self.get_extension_response_body(ext_urn_id)  # Make last response
        ext_response_headers = self._cloudapi_client.\
            get_last_response_headers()
        links_str = ext_response_headers['Link']
        return get_id_from_link(links_str, '/extension/service/')

    def update_extension(self, ext_name, ext_version, ext_vendor, ext_urn_id,
                         priority=constants.MQTT_EXTENSION_PRIORITY,
                         ext_enabled=True, auth_enabled=False,
                         description=''):
        """Update extension with the passed values.

        Note: extension name, version, and vendor cannot be updated

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        :param str ext_urn_id: the extension urn id
        :param int priority: extension priority (0-100);
            50 is a neutral priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for
            the extension
        :param str description: description of the extension

        :return: status of the update: True if successful, False otherwise
        :rtype: bool
        """
        payload = {
            "name": ext_name,
            "version": ext_version,
            "vendor": ext_vendor,
            "priority": priority,
            "enabled": "true" if ext_enabled else "false",
            "authorizationEnabled": "true" if auth_enabled else "false",
            'description': description
        }
        success = True
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.PUT,
                resource_url_relative_path=f"extensions/api/{ext_urn_id}",
                payload=payload)
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
            success = False
        return success

    def delete_extension(self, ext_name, ext_version, ext_vendor, ext_urn_id):
        """Delete the extension.

        The extension is first powered off so that it can be deleted.
        Note: deleting an extension also deletes its tokens and api filters.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        :param str ext_urn_id: the extension urn id
        """
        # Turn extension off
        update_result = self.update_extension(ext_name, ext_version,
                                              ext_vendor, ext_urn_id,
                                              ext_enabled=False)
        if not update_result:
            return False

        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                resource_url_relative_path=f"extensions/api/"
                                           f"{ext_urn_id}")
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)

    def check_extension_status(self, ext_urn_id):
        """Check if the MQTT extension is active.

        :param str ext_urn_id: the extension urn id

        :return: status of the MQTT extension
        :rtype: bool
        """
        extension_response_body = self.get_extension_response_body(ext_urn_id)
        if not extension_response_body:
            return False
        return True

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
        """
        payload = {
            "name": token_name,
            "type": "EXTENSION",
            "extensionId": ext_urn_id
        }
        token_info = None
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.POST,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path="tokens",
                payload=payload)
            token_info = {'token': response_body['token'],
                          'token_id': response_body['id']}
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return token_info

    def get_all_extension_token_ids(self, ext_name, ext_version, ext_vendor):
        """Get all of the extension's token ids.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor

        :return: list of token ids (str)
        :rtype: list of strs
        """
        token_ids = []
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path="tokens")
            ext_combine_name = f"{ext_vendor}/{ext_name}/{ext_version}"
            for token_info in response_body['values']: #
                if token_info['owner']['name'] == ext_combine_name:
                    token_ids.append(token_info['id'])
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return token_ids

    def delete_extension_token(self, token_id):
        """Delete the specified token with token_id.

        :param str token_id: the token's id
        """
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"tokens/{token_id}")
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)

    def delete_all_extension_tokens(self, ext_name, ext_version, ext_vendor):
        """Delete all of the extension's tokens.

        :param str ext_name: the extension name
        :param str ext_version: the extension version
        :param str ext_vendor: the extension vendor
        """
        token_ids = self.get_all_extension_token_ids(ext_name, ext_version,
                                                     ext_vendor)
        for token_id in token_ids:
            self.delete_extension_token(token_id)

    def check_extension_token_status(self, token_id):
        """Check if the instance's token is active by doing a GET request.

        :return: status of the token: True if active and False if not
        :rtype: bool
        """
        active = True
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"tokens/{token_id}")
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
        """
        active_api_filter_ids = self.get_api_filter_ids(api_filter_url_pattern,
                                                        ext_uuid)
        if not active_api_filter_ids:
            return self.create_api_filter(api_filter_url_pattern, ext_uuid)
        elif len(active_api_filter_ids) > 1:
            # Ensure only one api filter
            for ind in range(1, len(active_api_filter_ids)):
                self.delete_api_filter(active_api_filter_ids[ind])
        return active_api_filter_ids[0]

    def create_api_filter(self, api_filter_url_pattern, ext_uuid):
        """Create the api filter for the extension endpoint.

        :param str api_filter_url_pattern: the url pattern for the api filter,
            e.g., '/api/mqttEndpoint'
        :param str ext_uuid: The extension uuid

        :return: id of the api filter. In case of any error, the empty string
            is returned.
        :rtype: str
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
            f"/admin/extension/service/{ext_uuid}/apifilters"

        api_filter_id = ''
        try:
            response_body = self._sysadmin_client.post_resource(
                uri=absolute_api_filters_url,
                contents=xml_etree,
                media_type=vcd_client.EntityType.API_FILTER.value)
            api_filter_id = get_id_from_link(response_body.attrib['href'],
                                             '/extension/service/apifilter/')
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
        return api_filter_id

    def get_api_filter_ids(self, api_filter_url_pattern, ext_uuid):
        """Retrieve all api filter ids with the passed in path.

        :param str api_filter_url_pattern: the url pattern for the api filter,
            e.g., '/api/mqttEndpoint'
        :param str ext_uuid: the extension uuid

        :return: list of api filter ids
        :rtype: list of strs
        """
        filter_ids = []
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/" \
                                   f"{ext_uuid}/apifilters"
        try:
            response_body = self._sysadmin_client.get_resource(
                uri=absolute_api_filters_url)
            api_filters = response_body['ApiFilterRecord']
            for filter_info in api_filters:
                curr_filter_url_pattern = parse_url_pattern(
                    filter_info.attrib['urlPattern'])
                if curr_filter_url_pattern == api_filter_url_pattern:
                    filter_id = get_id_from_link(filter_info.attrib['href'],
                                                 '/extension/service/'
                                                 'apifilter/')
                    filter_ids.append(filter_id)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
        return filter_ids

    def delete_api_filter(self, filter_id):
        """Delete the api filter.

        :param str filter_id: filter id
        """
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/apifilter/" \
                                   f"{filter_id}"
        try:
            self._sysadmin_client.delete_resource(absolute_api_filters_url)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)

    def check_api_filter_status(self, api_filter_id):
        """Check if the api filter is active.

        :param str api_filter_id: the api filter id

        :return: status of the api filter
        :rtype: bool
        """
        extension_api_filter_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/apifilter/" \
                                   f"{api_filter_id}"
        active = True
        try:
            _ = self._sysadmin_client.get_resource(
                uri=extension_api_filter_url)
        except Exception:
            active = False
        return active
