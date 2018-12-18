# VMware vCloud Director Python SDK
# Copyright (c) 2018 VMware, Inc. All Rights Reserved.
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

import logging

import requests

from container_service_extension.config import SAMPLE_TEMPLATE_PHOTON_V2
from container_service_extension.config import SAMPLE_TEMPLATE_UBUNTU_16_04

SCRIPTS_DIR = 'scripts'
ACTIVE_PHOTON_CUST_SCRIPT = 'cust-photon-v2.sh'
ACTIVE_UBUNTU_CUST_SCRIPT = 'cust-ubuntu-16.04.sh'
STATIC_PHOTON_CUST_SCRIPT = 'CUST-PHOTON.sh'
STATIC_UBUNTU_CUST_SCRIPT = 'CUST-UBUNTU.sh'
PHOTON_TEMPLATE_NAME = 'photon-v2'
BASE_CONFIG_FILENAME = 'base_config.yaml'
ACTIVE_CONFIG_FILENAME = 'cse_test_config.yaml'


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
