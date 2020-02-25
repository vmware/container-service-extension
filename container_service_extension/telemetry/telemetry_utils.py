# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import hashlib

from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client

from container_service_extension.server_constants import CSE_SERVICE_NAME
from container_service_extension.server_constants import CSE_SERVICE_NAMESPACE
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.telemetry.constants import COLLECTOR_ID
from container_service_extension.telemetry.constants import VAC_URL


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


def get_telemetry_instance_id(vcd, logger_instance=None,
                              msg_update_callback=None):
    """Get CSE extension id which is used as instance id.

    Any exception is logged as error. No exception is leaked out
    of this method and does not affect the server startup.

    :param dict vcd: 'vcd' section of config file as a dict.
    :param logging.logger logger_instance: logger instance to log any error
    in retrieving CSE extension id.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
    that writes messages onto console.

    :return instance id to use for sending data to Vmware telemetry server

    :rtype str

    :raises Exception: if any exception happens while retrieving CSE
    extension id
    """
    try:
        client = Client(vcd['host'], api_version=vcd['api_version'],
                        verify_ssl_certs=vcd['verify'])
        client.set_credentials(BasicLoginCredentials(
            vcd['username'], SYSTEM_ORG_NAME, vcd['password']))
        ext = APIExtension(client)
        cse_info = ext.get_extension_info(CSE_SERVICE_NAME,
                                          namespace=CSE_SERVICE_NAMESPACE)
        if logger_instance:
            logger_instance.info("Retrieved telemetry instance id")
        return cse_info.get('id')
    except Exception as err:
        msg = f"Cannot retrieve telemetry instance id:{err}"
        if msg_update_callback:
            msg_update_callback.general(msg)
        if logger_instance:
            logger_instance.error(msg)
    finally:
        if client is not None:
            client.logout()


def store_telemetry_settings(config_dict):
    """Populate telemetry instance id, url and collector id in config.

    :param dict config_dict: CSE configuration
    """
    if config_dict['service']['telemetry']['enable'] is True:
        config_dict['service']['telemetry']['instance_id'] = \
            get_telemetry_instance_id(config_dict['vcd'])

    if 'vac_url' not in config_dict['service']['telemetry']:
        config_dict['service']['telemetry']['vac_url'] = VAC_URL

    config_dict['service']['telemetry']['collector_id'] = COLLECTOR_ID
