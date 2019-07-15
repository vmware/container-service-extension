# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from unittest.mock import Mock

from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
import requests

from container_service_extension.logger import configure_server_logger
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_LOGGER
from container_service_extension.remote_template_manager import \
    download_all_template_scripts
from container_service_extension.remote_template_manager import \
    get_remote_template_cookbook
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.template_builder import TemplateBuilder
from container_service_extension.utils import ConsoleMessagePrinter
from container_service_extension.vsphere_utils import populate_vsphere_list


if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings()
    configure_server_logger()

    get_server_runtime_config = Mock()  # noqa
    get_server_runtime_config.return_value = {
        'vcd': {
            'api_version': '32.0',
            'host': '10.150.199.221',
            'password': 'ca$hc0w',
            'username': 'administrator',
            'verify': False,
        },
        'vcs': [
            {
                'name': 'vc1',
                'password': 'Welcome@123',
                'username': 'administrator@vsphere.local',
                'verify': False
            }
        ],
        'broker': {
            'catalog': 'cse-cat',
            'ip_allocation_mode': 'pool',
            'network': 'cse-orgvdc-net',
            'org': 'cse-org',
            'remote_template_cookbook_url': 'https://raw.githubusercontent.com/rocknes/container-service-extension/remote_template/template.yaml',  # noqa
            'storage_profile': '*',
            'vdc': 'cse-orgvdc'
        }
    }

    server_config = get_server_runtime_config()
    populate_vsphere_list(server_config['vcs'])

    remote_template_cookbook = get_remote_template_cookbook()
    download_all_template_scripts(remote_template_cookbook)

    client = Client(
        uri=server_config['vcd']['host'],
        api_version=server_config['vcd']['api_version'],
        verify_ssl_certs=server_config['vcd']['verify'],
        log_file=SERVER_DEBUG_WIRELOG_FILEPATH,
        log_requests=True,
        log_headers=True,
        log_bodies=True)
    credentials = BasicLoginCredentials(server_config['vcd']['username'],
                                        SYSTEM_ORG_NAME,
                                        server_config['vcd']['password'])
    client.set_credentials(credentials)

    count = 0
    for template in remote_template_cookbook['templates']:
        count = count + 1
        build_params = {
            'template_name': template['name'],
            'template_revision': template['revision'],
            'source_ova_name': template['source_ova_name'],
            'source_ova_href': template['source_ova'],
            'source_ova_sha256': template['sha256_ova'],
            'org_name': server_config['broker']['org'],
            'vdc_name': server_config['broker']['vdc'],
            'catalog_name': server_config['broker']['catalog'],
            'catalog_item_name': f"test_{count}",
            'catalog_item_description': template['description'],
            'temp_vapp_name': template['name'] + '_temp',
            'cpu': template['cpu'],
            'memory': template['mem'],
            'network_name': server_config['broker']['network'],
            'ip_allocation_mode': server_config['broker']['ip_allocation_mode'], # noqa
            'storage_profile': server_config['broker']['storage_profile']
        }
        builder = TemplateBuilder(client, client, build_params,
                                  logger=SERVER_LOGGER,
                                  msg_update_callback=ConsoleMessagePrinter())
        builder.build()
