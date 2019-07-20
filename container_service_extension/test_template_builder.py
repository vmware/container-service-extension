# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
import requests

from container_service_extension.local_template_manager import \
    get_all_metadata_on_catalog_item
from container_service_extension.local_template_manager import \
    set_metadata_on_catalog_item
from container_service_extension.logger import configure_server_logger
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_LOGGER
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.remote_template_manager import \
    get_revisioned_template_name
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.template_builder import TemplateBuilder
from container_service_extension.utils import ConsoleMessagePrinter
from container_service_extension.vsphere_utils import populate_vsphere_list


# sample server runtime/install config
server_config = {
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


def build_all_templates(client):
    # read remote template cookbook, download all scripts
    rtm = RemoteTemplateManager(
        remote_template_cookbook_url=server_config['broker']['remote_template_cookbook_url'], # noqa
        logger=SERVER_LOGGER, msg_update_callback=ConsoleMessagePrinter())
    remote_template_cookbook = rtm.get_remote_template_cookbook()
    rtm.download_all_template_scripts()

    org_name = server_config['broker']['org']
    catalog_name = server_config['broker']['catalog']
    # create all templates mentioned in cookbook
    for template in remote_template_cookbook['templates']:
        catalog_item_name = get_revisioned_template_name(
            template['name'], template['revision'])
        build_params = {
            'template_name': template['name'],
            'template_revision': template['revision'],
            'source_ova_name': template['source_ova_name'],
            'source_ova_href': template['source_ova'],
            'source_ova_sha256': template['sha256_ova'],
            'org_name': org_name,
            'vdc_name': server_config['broker']['vdc'],
            'catalog_name': catalog_name,
            'catalog_item_name': catalog_item_name,
            'catalog_item_description': template['description'],
            'temp_vapp_name': template['name'] + '_temp',
            'cpu': template['cpu'],
            'memory': template['mem'],
            'network_name': server_config['broker']['network'],
            'ip_allocation_mode': server_config['broker']['ip_allocation_mode'], # noqa: E501
            'storage_profile': server_config['broker']['storage_profile']
        }
        builder = TemplateBuilder(client, client, build_params,
                                  logger=SERVER_LOGGER,
                                  msg_update_callback=ConsoleMessagePrinter())
        builder.build()

        set_metadata_on_catalog_item(
            client=client,
            catalog_name=server_config['broker']['catalog'],
            catalog_item_name=catalog_item_name,
            data=template,
            org_name=org_name)


def read_templates(client):
    org_name = server_config['broker']['org']
    catalog_name = server_config['broker']['catalog']
    org = get_org(client, org_name=org_name)
    catalog_item_names = [
        entry['name'] for entry in org.list_catalog_items(catalog_name)]
    result = []
    for catalog_item_name in catalog_item_names:
        md = get_all_metadata_on_catalog_item(
            client, catalog_name, catalog_item_name, org=org)
        if md:
            result.append(md)

    return result


if __name__ == '__main__':
    # disable insecure warnings
    requests.packages.urllib3.disable_warnings()

    # configure the loggers
    configure_server_logger()

    # intialize the vsphere list variable for get_vsphere to work properly
    populate_vsphere_list(server_config['vcs'])

    # create sys admin client to talk to vCD
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

    build_all_templates(client)
    dikt = read_templates(client)
    print(dikt)
