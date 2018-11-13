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

import os
import unittest

import yaml

from container_service_extension.system_test_framework.environment \
    import Environment


class BaseServerInstallTestCase(unittest.TestCase):
    _config_file = 'base_config.yaml'

    @classmethod
    def setUpClass(cls):
        if 'CSE_INSTALL_TEST_BASE_CONFIG_FILE' in os.environ:
            cls._config_file = os.environ['CSE_INSTALL_TEST_BASE_CONFIG_FILE']
        with open(cls._config_file, 'r') as f:
            config_dict = yaml.safe_load(f)
        Environment.init(config_dict)

    @classmethod
    def tearDownClass(cls):
        Environment.cleanup()
