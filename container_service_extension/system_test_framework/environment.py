# VMware vCloud Director Python SDK
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
from pathlib import Path

from click.testing import CliRunner
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vdc import VDC

from container_service_extension.server_constants import CSE_SERVICE_NAME
from container_service_extension.server_constants import CSE_SERVICE_NAMESPACE
import container_service_extension.system_test_framework.utils as testutils
import container_service_extension.utils as utils
"""
This module manages environment state during CSE system tests.
These variables persist through all test cases and do not change.

Module usage example:
```
import container_service_extension.system_test_framework.environment as env

env.init_environment()
# do something with env.CLIENT
```

NOTE: Imports using 'from environment import CLIENT' imports the variable to
the local module namespace, so calling 'init_environment' will change
environment.CLIENT but will not change the CLIENT that was imported.
"""
BASE_CONFIG_FILEPATH = 'base_config.yaml'
ACTIVE_CONFIG_FILEPATH = 'cse_test_config.yaml'

STATIC_PHOTON_CUST_SCRIPT = 'CUST-PHOTON.sh'
STATIC_UBUNTU_CUST_SCRIPT = 'CUST-UBUNTU.sh'
ACTIVE_PHOTON_CUST_SCRIPT = 'cust-photon-v2.sh'
ACTIVE_UBUNTU_CUST_SCRIPT = 'cust-ubuntu-16.04.sh'

PHOTON_TEMPLATE_NAME = 'photon-v2'
SCRIPTS_DIR = 'scripts'
SSH_KEY_FILEPATH = str(Path.home() / '.ssh' / 'id_rsa.pub')
CLI_RUNNER = CliRunner()

# if True, then the person testing would like to keep all artifacts that
# were made during testing.
DEV_MODE = False

AMQP_USERNAME = None
AMQP_PASSWORD = None
CLIENT = None
ORG_HREF = None
VDC_HREF = None
CATALOG_NAME = None


def init_environment(config_filepath=BASE_CONFIG_FILEPATH):
    """Set up module variables according to config dict.

    :param str config_filepath:
    """
    global AMQP_USERNAME, AMQP_PASSWORD, CLIENT, ORG_HREF, VDC_HREF, \
        CATALOG_NAME, DEV_MODE

    config = testutils.yaml_to_dict(config_filepath)
    CLIENT = Client(config['vcd']['host'],
                    api_version=config['vcd']['api_version'],
                    verify_ssl_certs=config['vcd']['verify'])
    credentials = BasicLoginCredentials(config['vcd']['username'],
                                        utils.SYSTEM_ORG_NAME,
                                        config['vcd']['password'])
    CLIENT.set_credentials(credentials)

    org = utils.get_org(CLIENT, org_name=config['broker']['org'])
    vdc = utils.get_vdc(CLIENT, config['broker']['vdc'], org=org)
    ORG_HREF = org.href
    VDC_HREF = vdc.href
    CATALOG_NAME = config['broker']['catalog']
    AMQP_USERNAME = config['amqp']['username']
    AMQP_PASSWORD = config['amqp']['password']

    try:
        DEV_MODE = config['test']['developer_mode']
    except KeyError:
        pass


def cleanup_environment():
    if CLIENT is not None:
        CLIENT.logout()


def setup_active_config():
    """Set up the active config file from BASE_CONFIG_FILEPATH.

    'test' section is removed if it exists in base config, active config is
    created at ACTIVE_CONFIG_FILEPATH.

    :returns: config dict without 'test' key

    :rtype: dict
    """
    config = testutils.yaml_to_dict(BASE_CONFIG_FILEPATH)
    if 'test' in config:
        del config['test']

    testutils.dict_to_yaml_file(config, ACTIVE_CONFIG_FILEPATH)
    os.chmod(ACTIVE_CONFIG_FILEPATH, 0o600)

    return config


def teardown_active_config():
    """Delete the active config file if it exists."""
    try:
        Path(ACTIVE_CONFIG_FILEPATH).unlink()
    except FileNotFoundError:
        pass


def delete_catalog_item(item_name):
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.delete_catalog_item(CATALOG_NAME, item_name)
        utils.wait_for_catalog_item_to_resolve(CLIENT, CATALOG_NAME, item_name,
                                               org=org)
        org.reload()
    except EntityNotFoundException:
        pass


def delete_vapp(vapp_name):
    vdc = VDC(CLIENT, href=VDC_HREF)
    try:
        task = vdc.delete_vapp(vapp_name, force=True)
        CLIENT.get_task_monitor().wait_for_success(task)
        vdc.reload()
    except EntityNotFoundException:
        pass


def delete_catalog(catalog_name=None):
    if catalog_name is None:
        catalog_name = CATALOG_NAME
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.delete_catalog(catalog_name)
        # TODO() no way currently to wait for catalog deletion.
        # https://github.com/vmware/pyvcloud/issues/334
        # below causes EntityNotFoundException, catalog not found.
        # time.sleep(15)
        # org.reload()
    except EntityNotFoundException:
        pass


def unregister_cse():
    try:
        APIExtension(CLIENT).delete_extension(CSE_SERVICE_NAME,
                                              CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        pass


def prepare_customization_scripts():
    """Copy real customization scripts to the active customization scripts.

    Copy 'CUST-PHOTON.sh' to 'cust-photon-v2.sh'
    Copy 'CUST-UBUNTU.sh' to 'cust-ubuntu-16.04.sh'

    :raises FileNotFoundError: if script files cannot be found.
    """
    scripts_filepaths = {
        f"{SCRIPTS_DIR}/{STATIC_PHOTON_CUST_SCRIPT}":
            f"{SCRIPTS_DIR}/{ACTIVE_PHOTON_CUST_SCRIPT}",
        f"{SCRIPTS_DIR}/{STATIC_UBUNTU_CUST_SCRIPT}":
            f"{SCRIPTS_DIR}/{ACTIVE_UBUNTU_CUST_SCRIPT}",
    }

    for src, dst in scripts_filepaths.items():
        Path(dst).write_text(Path(src).read_text())


def blank_customizaton_scripts():
    """Blanks out 'cust-photon-v2.sh' and 'cust-ubuntu-16.04.sh'.

    :raises FileNotFoundError: if script files cannot be found.
    """
    scripts_paths = [
        Path(f"{SCRIPTS_DIR}/{ACTIVE_PHOTON_CUST_SCRIPT}"),
        Path(f"{SCRIPTS_DIR}/{ACTIVE_UBUNTU_CUST_SCRIPT}")
    ]

    for path in scripts_paths:
        path.write_text('')


def catalog_item_exists(catalog_item, catalog_name=None):
    if catalog_name is None:
        catalog_name = CATALOG_NAME
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.get_catalog_item(catalog_name, catalog_item)
        return True
    except EntityNotFoundException:
        return False


def vapp_exists(vapp_name):
    vdc = VDC(CLIENT, href=VDC_HREF)
    try:
        vdc.get_vapp(vapp_name)
        return True
    except EntityNotFoundException:
        return False


def is_cse_registered():
    try:
        APIExtension(CLIENT).get_extension(CSE_SERVICE_NAME,
                                           namespace=CSE_SERVICE_NAMESPACE)
        return True
    except MissingRecordException:
        return False


def is_cse_registration_valid(routing_key, exchange):
    try:
        ext = APIExtension(CLIENT).get_extension(CSE_SERVICE_NAME,
                                                 namespace=CSE_SERVICE_NAMESPACE)  # noqa
    except MissingRecordException:
        return False

    if ext['routingKey'] != routing_key or ext['exchange'] != exchange:
        return False

    return True
