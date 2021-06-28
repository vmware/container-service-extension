# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import hashlib

from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
import requests

from container_service_extension.common.constants.server_constants import CSE_SERVICE_NAME  # noqa: E501
from container_service_extension.common.constants.server_constants import CSE_SERVICE_NAMESPACE  # noqa: E501
from container_service_extension.common.constants.server_constants import MQTT_EXTENSION_VENDOR  # noqa: E501
from container_service_extension.common.constants.server_constants import MQTT_EXTENSION_VERSION  # noqa: E501
from container_service_extension.common.constants.server_constants import MQTTExtKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import SYSTEM_ORG_NAME  # noqa: E501
from container_service_extension.common.utils.core_utils import NullPrinter
from container_service_extension.common.utils.server_utils import should_use_mqtt_protocol  # noqa: E501
from container_service_extension.lib.telemetry.constants import COLLECTOR_ID
from container_service_extension.lib.telemetry.constants import VAC_URL
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.mqi.mqtt_extension_manager import \
    MQTTExtensionManager


CEIP_HEADER_NAME = "x-vmware-vcloud-ceip-id"


def uuid_hash(uuid):
    """Return SHA1 hash as hex digest of an uuid.

    Requirement from VAC team : You should apply SHA1 hashing over the data as
    a text. More specifically you should have the text data as a UTF8 encoded
    string then convert the string to byte array and digest it into a SHA1
    hash. The resulting SHA1 hash must be converted to text by displaying each
    byte of the hashcode as a HEX char (first byte displayed leftmost in the
    output). The hash must be lowercase.

    No checks are made to determine if the input uuid is valid or not. Dashes
    in the uuid are ignored while computing the hash.

    :param str uuid: uuid to be hashed

    :returns: SHA1 hash as hex digest of the provided uuid.
    """
    uuid_no_dash = uuid.replace('-', '')
    m = hashlib.sha1()
    m.update(bytes(uuid_no_dash, 'utf-8'))
    return m.hexdigest()


def get_vcd_ceip_id(vcd_host, verify_ssl=True, logger_debug=NULL_LOGGER):
    """."""
    response = None
    try:
        if not verify_ssl:
            requests.packages.urllib3.disable_warnings()
        uri = f"https://{vcd_host}"
        response = requests.get(uri, verify=verify_ssl)
        return response.headers.get(CEIP_HEADER_NAME)
    except Exception as err:
        logger_debug.error(f"Unable to get vCD CEIP id : {str(err)}")
    finally:
        if response:
            response.close()


def get_telemetry_instance_id(config_dict, logger_debug=NULL_LOGGER,
                              msg_update_callback=NullPrinter()):
    """Get CSE AMQP or MQTT extension id which is used as instance id.

    Any exception is logged as error. No exception is leaked out
    of this method and does not affect the server startup.

    :param dict config_dict: CSE configuration
    :param logging.logger logger_debug: logger instance to log any error
    in retrieving CSE extension id.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :return instance id to use for sending data to Vmware telemetry server

    :rtype str (unless no instance id found)
    """
    vcd = config_dict['vcd']
    client = None
    try:
        client = Client(vcd['host'], verify_ssl_certs=vcd['verify'])
        client.set_credentials(BasicLoginCredentials(
            vcd['username'], SYSTEM_ORG_NAME, vcd['password']))
        if should_use_mqtt_protocol(config_dict):
            # Get MQTT extension uuid
            mqtt_ext_manager = MQTTExtensionManager(client)
            ext_info = mqtt_ext_manager.get_extension_info(
                ext_name=CSE_SERVICE_NAME,
                ext_version=MQTT_EXTENSION_VERSION,
                ext_vendor=MQTT_EXTENSION_VENDOR)
            if not ext_info:
                logger_debug.debug("Failed to retrieve telemetry instance id")
                return None
            logger_debug.debug("Retrieved telemetry instance id")
            return mqtt_ext_manager.get_extension_uuid(
                ext_info[MQTTExtKey.EXT_URN_ID])
        else:
            # Get AMQP extension id
            ext = APIExtension(client)
            cse_info = ext.get_extension_info(CSE_SERVICE_NAME,
                                              namespace=CSE_SERVICE_NAMESPACE)
            logger_debug.debug("Retrieved telemetry instance id")
            return cse_info.get('id')
    except Exception as err:
        msg = f"Cannot retrieve telemetry instance id:{err}"
        msg_update_callback.general(msg)
        logger_debug.error(msg, exc_info=True)
    finally:
        if client is not None:
            client.logout()


def store_telemetry_settings(config_dict):
    """Populate telemetry instance id, url and collector id in config.

    :param dict config_dict: CSE configuration
    """
    if 'vac_url' not in config_dict['service']['telemetry']:
        config_dict['service']['telemetry']['vac_url'] = VAC_URL

    config_dict['service']['telemetry']['collector_id'] = COLLECTOR_ID

    vcd_ceip_id = None
    instance_id = None
    if config_dict['service']['telemetry']['enable']:
        vcd_ceip_id = get_vcd_ceip_id(config_dict['vcd']['host'],
                                      verify_ssl=config_dict['vcd']['verify'])
        instance_id = get_telemetry_instance_id(config_dict)
    config_dict['service']['telemetry']['vcd_ceip_id'] = vcd_ceip_id
    config_dict['service']['telemetry']['instance_id'] = instance_id
