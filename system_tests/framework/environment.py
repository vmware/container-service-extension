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


def developerModeAware(function):
    """A decorator function to skip execution of decorated function.

    To be used on test teardown methods.

    :param function function: decorated function.

    :return: a function that either executes the decorated function or skips
        it, based on the value of a particular param in the environment
        configuration.

    :rtype: function
    """
    def wrapper(self):
        if not Environment._config['test']['developer_mode']:
            function(self)
        else:
            Environment.get_default_logger().debug(
                f'Skipping {function.__name__} because developer mode is on.')

    return wrapper


class Environment(object):
    _config = None
    _logger = None

    @classmethod
    def init(cls, config_data):
        """Initializer for Environment class.

        :param object config_data: a PyYAML object that contains the yaml
            representation of configuration data read from the configuration
            file.
        """
        cls._config = config_data
        if not cls._config['test']['connection']['verify'] and \
           cls._config['test']['connection']['disable_ssl_warnings']:
            requests.packages.urllib3.disable_warnings()
        cls._logger = cls.get_default_logger()

    @classmethod
    def get_config(cls):
        """Get test configuration parameter dictionary.

        :return: a dict containing configuration information.

        :rtype: dict
        """
        return cls._config

    @classmethod
    def get_default_logger(cls):
        """Get a handle to the logger for system_tests.

        :return: default logger instance.

        :rtype: logging.Logger
        """
        if cls._logger is None:
            cls._logger = logging.getLogger('cse.server.installation.tests')
            cls._logger.setLevel(logging.DEBUG)
            if not cls._logger.handlers:
                log_file = \
                    cls._config['test']['logging']['default_log_filename']
                if log_file is not None:
                    handler = logging.FileHandler(log_file)
                else:
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
        """Cleans up the environment."""
        pass
