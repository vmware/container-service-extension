import logging
import requests
from pathlib import Path

from click.testing import CliRunner
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from vcd_cli.utils import to_dict

import container_service_extension.system_test_framework.utils as testutils
import container_service_extension.utils as utils
from container_service_extension.config import configure_vcd_amqp
from container_service_extension.config import SAMPLE_TEMPLATE_PHOTON_V2
from container_service_extension.config import SAMPLE_TEMPLATE_UBUNTU_16_04
"""
This module manages environment state during CSE system tests.

These variables persist through all test cases and do not change.
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

DEFAULT_AMQP_SETTINGS = None
AMQP_USERNAME = None
AMQP_PASSWORD = None
CLIENT = None
ORG_HREF = None
VDC_HREF = None


def init_environment(config_filepath=BASE_CONFIG_FILEPATH):
    """Set up module variables according to config dict.

    :param str config_filepath:
    """
    global DEFAULT_AMQP_SETTINGS, AMQP_USERNAME, AMQP_PASSWORD, CLIENT, \
        ORG_HREF, VDC_HREF

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

    amqp_service = AmqpService(CLIENT)
    configure_vcd_amqp(CLIENT, 'vcdext', config['amqp']['host'],
                       config['amqp']['port'], 'vcd',
                       config['amqp']['ssl_accept_all'],
                       config['amqp']['ssl'], '/',
                       config['amqp']['username'],
                       config['amqp']['password'], quiet=True)
    DEFAULT_AMQP_SETTINGS = to_dict(amqp_service.get_settings())
    AMQP_USERNAME = config['amqp']['username']
    AMQP_PASSWORD = config['amqp']['password']

    _init_vcd()


def cleanup_environment():
    _cleanup_vcd()
    if CLIENT is not None:
        CLIENT.logout()


def _init_vcd():
    """Set up VCD constructs if they do not already exist.

    Tasks (in order):
        - Create external network
        - Create org
            - Create org vdc
            - Create org vdc network
    """
    # TODO
    pass


def _cleanup_vcd():
    """Destroys VCD constructs set up by init_vcd() if they exist."""
    # TODO
    pass


def developerModeAware(function):
    """Skip execution of decorated function.

    To be used on test teardown methods.

    :param function function: decorated function.

    :return: a function that either executes the decorated function or skips
        it, based on the value of a particular param in the environment
        configuration.

    :rtype: function
    """
    def wrapper(self):
        if Environment._test_config is not None and \
                Environment._test_config['developer_mode']:
            function(self)
        else:
            Environment.get_default_logger().debug(
                f'Skipping {function.__name__} because developer mode is on.')

    return wrapper


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
