import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.api_client import ApiClient

import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.shared_constants import RequestMethod
import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.logger as logger
from lxml import etree
import requests
import pyvcloud.vcd.api_extension as api_extension

MQTT_MIN_API_VERSION = 34.0
MQTT_ENDPOINT_PATH = '/api/clockTime/test6'
EXTENSION_SERVICE_PATH = '/extension/service/'
API_FILTER_PATH = '/extension/service/apifilter/'


def get_id_from_link(link, id_path):
    ext_service_ind = link.find(id_path)
    if ext_service_ind == -1:
        return None
    start_ind = ext_service_ind + len(id_path)
    end_offset = link[start_ind:].find('/')
    if end_offset == -1: # if link ends in id
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
        if client_api_version < MQTT_MIN_API_VERSION:
            raise ValueError(f'API version {client_api_version} is less than required' \
                             f' version {MQTT_MIN_API_VERSION} to use MQTT')

        self._sysadmin_client: vcd_client.Client = sysadmin_client
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(self._sysadmin_client)
        # TODO retrieve other fields e.g., extension and token info

    def create_extension(self, ext_name, ext_version, ext_vendor,
                         priority, ext_enabled, auth_enabled):
        """Makes a request to create an extension
        Note: vendor-name-version combination must be unique

        :param str ext_name: Name for the extension
        :param str ext_version: Extension version; must follow semantic versioning rules
        :param str ext_vendor: Vendor name for the extension
        :param int priority: extension priority (0-100); 50 is a neutral priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for the extension

        :return a dictionary with the extension info
        :rtype: dict with keys "listen_topic", "respond_topic", and "ext_id"
        """
        payload = {
            "name": ext_name,
            "version": ext_version,
            "vendor": ext_vendor,
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
            print(f"extension response body: {response_body}")
            mqtt_topics = response_body['mqttTopics']
            ext_info = {
                'listen_topic': mqtt_topics['monitor'],
                'respond_topic': mqtt_topics['respond'],
                'ext_id': response_body['id']
            }

        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
        return ext_info

    def get_all_extension_info(self):
        """Lists all extensions

        :return a list of all extension info
        :rtype: list[dict]
        """
        ext_info_arr = []
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                resource_url_relative_path="extensions/api")
            ext_info_arr = response_body['values']
        except requests.exceptions.HTTPError as err:
            print(f"error in get_all_extension_info: {err}")
        return ext_info_arr

    def get_extension_urn_id(self, ext_name, ext_version, ext_vendor):
        ext_info_arr = self.get_all_extension_info()

        # Since the combination of extension name, version, and vendor is unique,
        # we can identify the extension by matching these three fields.
        for ext_info in ext_info_arr:
            if ext_info['name'] == ext_name and ext_info['version'] == ext_version \
                    and ext_info['vendor'] == ext_vendor:
                return ext_info['id']
        return None

    def get_extension_response_body(self, ext_urn_id):
        """Gets the extension with the specified id

        :param str ext_urn_id:urn id of the extension
        :return:
        """
        if not ext_urn_id:
            return None
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            resource_url_relative_path=f"extensions/api/{ext_urn_id}")
        return response_body

    def get_extension_uuid(self, ext_name, ext_version, ext_vendor):
        """ Retrieves the extension uuid

        :param str ext_name: Name for the extension
        :param str ext_version: Extension version; must follow semantic versioning rules
        :param str ext_vendor: Vendor name for the extension
        :return: the extension uuid
        :rtype: str
        """
        # retrieve string of links
        ext_urn_id = self.get_extension_urn_id(ext_name, ext_version, ext_vendor)
        _ = self.get_extension_response_body(ext_urn_id)  # ensure request is last response
        ext_response_headers = self._cloudapi_client.get_last_response_headers()
        links_str = ext_response_headers['Link']
        return get_id_from_link(links_str, EXTENSION_SERVICE_PATH)

    def update_extension(self, ext_id, ext_name, ext_version, ext_vendor,
                         priority, ext_enabled, auth_enabled):
        """Updates extension; extension name, version, and vendor cannot be updated

        :param str ext_id: extension id, e.g. "urn:vcloud:extension:VMWare_TEST.ClockExtension_TEST:1.2.3"
        :param str ext_name: Name for the extension
        :param str ext_version: Extension version; must follow semantic versioning rules
        :param str ext_vendor: Vendor name for the extension
        :param int priority: extension priority (0-100); 50 is a neutral priority
        :param bool ext_enabled: indicates if extension is enabled
        :param bool auth_enabled: indicates if authorization is enabled for the extension
        """
        if not ext_id:
            return None
        payload = {
            "name": ext_name,
            "version": ext_version,
            "vendor": ext_vendor,
            "priority": priority,
            "enabled": "true" if ext_enabled else "false",
            "authorizationEnabled": "true" if auth_enabled else "false"
        }

        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.PUT,
            resource_url_relative_path=f"extensions/api/{ext_id}",
            payload=payload)
        print(f"updated extension: {response_body}")
        return response_body

    def delete_extension(self, ext_id):
        """Deletes the extension. The extension must be disabled.

        :param str ext_id: id of the extension
        :return:
        """
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                resource_url_relative_path=f"extensions/api/{ext_id}")
        except requests.exceptions.HTTPError as err:
            print(f"exception: {err}")

    def create_extension_token(self, token_name, ext_urn_id):
        """Creates a long live token

        :param str token_name: name of token
        :param str ext_urn_id: extension id
        :return: token as a str
        :rtype: str
        """
        payload = {
            "name": token_name,
            "type": "EXTENSION",
            "extensionId": ext_urn_id
        }
        token = ""
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.POST,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path="tokens",
                payload=payload)
            token = response_body["token"]
        except requests.exceptions.HTTPError as err:
            print(f"received error for creating extension token {err}")
        return token

    def get_all_extension_token_ids(self, ext_name, ext_version, ext_vendor):
        owner_name = f"{ext_vendor}/{ext_name}/{ext_version}"
        token_ids = []
        try:
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path="tokens")
            for token_info in response_body['values']:
                if token_info['owner']['name'] == owner_name:
                    token_ids.append(token_info['id'])
        except requests.exceptions.HTTPError as err:
            # TODO change printing errors to logging errors
            print(f"received error in getting all tokens: {err}")
        return token_ids

    def delete_extension_token(self, token_id):
        try:
            self._cloudapi_client.do_request(
                method=RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"tokens/{token_id}")
        except requests.exceptions.HTTPError as err:
            print(f"received error in deleting token: {err}")

    def delete_all_extension_tokens(self, ext_name, ext_version, ext_vendor):
        token_ids = self.get_all_extension_token_ids(ext_name, ext_version, ext_vendor)
        for tok_id in token_ids:
            self.delete_extension_token(tok_id)

    def add_api_filter(self, ext_name, ext_version, ext_vendor):
        ext_uuid = self.get_extension_uuid(ext_name, ext_version, ext_vendor)
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                         f"/admin/extension/service/{ext_uuid}" \
                         f"/apifilters"
        # xml_str = f'<vmext:ApiFilter xmlns:vmext = "http://www.vmware.com/vcloud/extension/v1.5">' \
        #           f'<vmext:UrlPattern>{MQTT_ENDPOINT_PATH}</vmext:UrlPattern >' \
        #           f'</vmext:ApiFilter >'
        # xml_etree = etree.fromstring(xml_str)
        xml_etree = etree.XML(
            f"""
            <vmext:ApiFilter xmlns:vmext = "http://www.vmware.com/vcloud/extension/v1.5">
                <vmext:UrlPattern>{MQTT_ENDPOINT_PATH}</vmext:UrlPattern >
            </vmext:ApiFilter>
            """)
        try:
            response_body = self._sysadmin_client.post_resource(
                uri=absolute_api_filters_url,
                contents=xml_etree,
                media_type=vcd_client.EntityType.API_FILTER.value)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)

    def get_api_filter_ids(self, ext_name, ext_version, ext_vendor):
        ext_uuid = self.get_extension_uuid(ext_name, ext_version, ext_vendor)
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/{ext_uuid}" \
                                   f"/apifilters"

        filter_ids = []
        try:
            response_body = self._sysadmin_client.get_resource(uri=absolute_api_filters_url)
            api_filters = response_body['ApiFilterRecord']
            for filter in api_filters:
                if filter.attrib['urlPattern'] == MQTT_ENDPOINT_PATH:
                    filter_ids.append(get_id_from_link(filter.attrib['href'], API_FILTER_PATH))
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
        return filter_ids

    def get_api_filter_info(self, filter_id):
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/apifilter/{filter_id}"
        filter_info = None
        try:
            response_body = self._sysadmin_client.get_resource(uri=absolute_api_filters_url)
            print(response_body.attrib)
            filter_info = {
                'endpoint_path': response_body['UrlPattern'].text,
                'content type': response_body.attrib['type']
            }
        except Exception as err:
            logger.SERVER_LOGGER.error(err)
        return filter_info

    def delete_api_filter(self, filter_id):
        absolute_api_filters_url = f"{self._sysadmin_client.get_api_uri()}" \
                                   f"/admin/extension/service/apifilter/{filter_id}"
        try:
            self._sysadmin_client.delete_resource(absolute_api_filters_url)
        except Exception as err:
            logger.SERVER_LOGGER.error(err)

    def delete_all_api_filters(self, ext_name, ext_version, ext_vendor):
        filter_ids = self.get_api_filter_ids(ext_name, ext_version, ext_vendor)
        for filter_id in filter_ids:
            self.delete_api_filter(filter_id)
