# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.server_constants import CSE_SERVICE_NAME
from container_service_extension.server_constants import CSE_SERVICE_NAMESPACE
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.telemetry.constants import COLLECTOR_ID
from container_service_extension.telemetry.constants import VAC_URL


def store_telemetry_url_in_config(telemetry):
    """Store the value of telemetry url in config.

    Store this value under config[service][telemetry][vac_url].
    Do not overwrite any existing value.

    :param dict telemetry: 'service->telemetry' section of config as dict.

    """
    if 'vac_url' not in telemetry:
        telemetry['vac_url'] = VAC_URL


def store_telemetry_collector_id_in_config(telemetry):
    """Store the default value of collector id in config.

    Store this value under config[service][telemetry][collector_id]

    :param dict telemetry: 'service->telemetry' section of config as dict.
    """
    telemetry['collector_id'] = COLLECTOR_ID


def store_telemetry_instance_id_in_config(telemetry, vcd):
    """Get CSE extension id and store it in config[service][telemetry].

    Store this value under config[service][telemetry][instance_id].

    Any exception is logged as error. No exception is leaked out
    of this method and does not affect the server startup.

    :param dict telemetry: 'service->telemetry' section of config as dict.
    :param dict vcd: 'vcd' section of config file as a dict.
    """
    try:
        if telemetry['enable'] is True:
            client = Client(vcd['host'],
                            api_version=vcd['api_version'],
                            verify_ssl_certs=vcd['verify'])
            client.set_credentials(
                BasicLoginCredentials(vcd['username'],
                                      SYSTEM_ORG_NAME, vcd['password']))
            ext = APIExtension(client)
            cse_info = ext.get_extension_info(CSE_SERVICE_NAME,
                                              namespace=CSE_SERVICE_NAMESPACE)
            telemetry['instance_id'] = cse_info.get('id')
    except Exception as err:
        LOGGER.error("Cannot retrieve telemetry instance id" + err)
    finally:
        if client is not None:
            print(telemetry)
            client.logout()
