import logging
import requests
from pathlib import Path

from click.testing import CliRunner
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vdc import VDC

import container_service_extension.system_test_framework.utils as testutils
import container_service_extension.utils as utils
from container_service_extension.config import CSE_NAME
from container_service_extension.config import CSE_NAMESPACE
from container_service_extension.config import SAMPLE_TEMPLATE_PHOTON_V2
from container_service_extension.config import SAMPLE_TEMPLATE_UBUNTU_16_04
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
        CATALOG_NAME

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


def cleanup_environment():
    if CLIENT is not None:
        CLIENT.logout()


def delete_cse_entities(config):
    """Deletes ovas, templates, temp vapps, cse catalog, and unregisters CSE.
    """
    catalog_name = config['broker']['catalog']
    org = Org(CLIENT, href=ORG_HREF)
    vdc = VDC(CLIENT, href=VDC_HREF)

    for tmpl in config['broker']['templates']:
        try:
            org.delete_catalog_item(catalog_name,
                                    tmpl['catalog_item'])
            utils.wait_for_catalog_item_to_resolve(CLIENT,
                                                   catalog_name,
                                                   tmpl['catalog_item'],
                                                   org=org)
            org.reload()
        except EntityNotFoundException:
            pass
        try:
            org.delete_catalog_item(catalog_name,
                                    tmpl['source_ova_name'])
            utils.wait_for_catalog_item_to_resolve(CLIENT,
                                                   catalog_name,
                                                   tmpl['source_ova_name'],
                                                   org=org)
            org.reload()
        except EntityNotFoundException:
            pass
        try:
            task = vdc.delete_vapp(tmpl['temp_vapp'], force=True)
            CLIENT.get_task_monitor().wait_for_success(task)
            vdc.reload()
        except EntityNotFoundException:
            pass

    try:
        org.delete_catalog(catalog_name)
        # TODO no way currently to wait for catalog deletion.
        # https://github.com/vmware/pyvcloud/issues/334
        # below causes EntityNotFoundException, catalog not found.
        # time.sleep(15)
        # org.reload()
    except EntityNotFoundException:
        pass

    unregister_cse()


def unregister_cse():
    try:
        APIExtension(CLIENT).delete_extension(CSE_NAME, CSE_NAMESPACE)
    except MissingRecordException:
        pass


def prepare_customization_scripts():
    """Copies real customization scripts to the active customization scripts.
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
        APIExtension(CLIENT).get_extension(CSE_NAME, namespace=CSE_NAMESPACE)
        return True
    except MissingRecordException:
        return False


def is_cse_registration_valid(routing_key, exchange):
    try:
        ext = APIExtension(CLIENT).get_extension(CSE_NAME,
                                                 namespace=CSE_NAMESPACE)
    except MissingRecordException:
        return False

    if ext['routingKey'] != routing_key or ext['exchange'] != exchange:
        return False

    return True


# TODO currently unused. maybe remove
class Environment(object):
    """Hold configuration details of the vCD testbed.

    Also acts as a single point for management of logging for tests.
    """

    _logger = None
    _install_config = None
    _test_config = None

    @classmethod
    def init(cls, config_dict):
        """Initialize Environment class attributes.

        :param dict config_dict: contains the yaml representation of
            configuration data read from the configuration file.
        """
        cls._install_config = config_dict
        if 'test' in config_dict:
            cls._test_config = config_dict['test']
            if not cls._test_config['connection']['verify'] and \
               cls._test_config['connection']['disable_ssl_warnings']:
                requests.packages.urllib3.disable_warnings()

            # get rid of test specific configurations from installation config
            del cls._install_config['test']

        if 'broker' in cls._install_config:
            if 'templates' not in cls._install_config['broker']:
                cls._install_config['broker']['templates'] = \
                    [SAMPLE_TEMPLATE_PHOTON_V2, SAMPLE_TEMPLATE_UBUNTU_16_04]
            if 'default_template' not in cls._install_config['broker']:
                cls._install_config['broker']['default_template'] = \
                    SAMPLE_TEMPLATE_PHOTON_V2['name']

        cls._logger = cls.get_default_logger()

    @classmethod
    def get_install_config(cls):
        """Get test configuration parameter dictionary.

        :return: a dict containing configuration information.

        :rtype: dict
        """
        return cls._install_config

    @classmethod
    def get_default_logger(cls):
        """Get a handle to the logger for system_tests.

        :return: default logger instance.

        :rtype: logging.Logger
        """
        if cls._logger is not None:
            return cls._logger

        cls._logger = logging.getLogger('cse.server.installation.tests')
        cls._logger.setLevel(logging.DEBUG)
        if not cls._logger.handlers:
            try:
                log_file = cls._test_config['logging']['default_log_filename']
                handler = logging.FileHandler(log_file)
            except (TypeError, KeyError):
                handler = logging.NullHandler()

            formatter = logging.Formatter('%(asctime)-23.23s | '
                                          '%(levelname)-5.5s | '
                                          '%(name)-15.15s | '
                                          '%(module)-15.15s | '
                                          '%(funcName)-30.30s | '
                                          '%(message)s')
            handler.setFormatter(formatter)
            cls._logger.addHandler(handler)

        return cls._logger

    @classmethod
    def cleanup(cls):
        """Clean up the environment."""
        pass
