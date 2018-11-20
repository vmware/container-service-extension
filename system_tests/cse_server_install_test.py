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

from container_service_extension.system_test_framework.base_install_test \
    import BaseServerInstallTestCase
from container_service_extension.system_test_framework.environment \
    import developerModeAware, CONFIGS_DIR
from container_service_extension.system_test_framework.utils import yaml_to_dict

from container_service_extension.config import get_validated_config


class CSEServerInstallationTest(BaseServerInstallTestCase):
    """Test CSE server installation."""

    # All tests in this module should be run as System Administrator
    _client = None

    def test_0000_setup(self):
        """."""
        pass

    def test_00x0_config_invalid_keys_or_value_types(self):
        """Tests that config file with invalid/extra keys or invalid value types do not pass config validation."""
        config_files = [
            'invalid-keys1.yaml',
            'invalid-keys2.yaml',
            'invalid-keys3.yaml',
            'invalid-keys4.yaml',
            'invalid-values1.yaml',
            'invalid-values2.yaml',
            'invalid-values3.yaml',
            'invalid-values4.yaml',
        ]

        for config_filename in config_files:
            try:
                get_validated_config(f'{CONFIGS_DIR}/{config_filename}')
            except (KeyError, ValueError):
                pass


    def test_00x0_config_valid(self):
        """Tests that config file with valid keys and value types pass config validation."""
        config_files = [
            'valid-cleanup-true.yaml',
        ]
        for config_filename in config_files:
            get_validated_config(f'{CONFIGS_DIR}/{config_filename}')


    def test_00x0_check_invalid_installation(self):
        """Tests cse check against config files that are invalid/have not been used for installaiton."""
        pass


    def test_00x0_install_no_capture_fails_without_ssh_key(self):
        """Tests that installation using --no-capture option fails if --ssh-key option is not used.
        
        command: cse install --config config-both.yaml --no-capture
        required files: config-both.yaml
        expected: display error message
        """
        pass


    def test_00x0_install_no_capture(self):
        """Tests installation options: '--config', '--template', '--amqp skip', '--ext skip', '--ssh-key', '--no-capture'.
        Tests that installation downloads/uploads ova file, creates photon temp vapp, skips amqp configuration, skips cse registration, and skips temp vapp capture.

        command: cse install --config config-both-cleanup.yaml --template photon-v2 --amqp skip --ext skip --ssh-key ssh.pub --no-capture
        required files: ssh.pub, config-both.yaml, photon-v2 init, photon-v2 cust
        expected: cse not registered, amqp not configured, catalog exists, photon-v2 ova exists, temp vapp does not exist, template does not exist.
        """
        pass


    def test_00x0_install_temp_vapp_already_exists(self):
        """Tests that installation skips amqp configuration (when answering no to prompt), skips cse registration (when answering no to prompt), captures temp vapp as template correctly.
        
        command: cse install --config config-both.yaml --template photon-v2.
        required files: ssh.pub, config-both.yaml
        expected: cse not registered, amqp not configured, temp vapp exists (can be ssh'd into), photon-v2 template exists.
        """
        pass


    def test_00x0_config_cleanup_option(self):
        """Tests config file 'cleanup' option (true and false)."""
        pass


    def test_00x0_install_update(self):
        """Tests installation option: '--update'.
        Tests that installation configures amqp (when answering yes to prompt), registers cse (when answering yes to prompt), creates all templates correctly, customized temp vapps correctly.
        
        command: cse install --config config-both.yaml --ssh-key ssh.pub --update
        expected: cse registered, amqp configured, ubuntu/photon ovas exist, temp vapps exist, templates exist.
        """
        pass


    def test_00x0_check_valid_installation(self):
        """Tests cse check against a valid installation.
        """
        pass


    @developerModeAware
    def test_9998_teardown(self):
        """Destroy all CSE Server related things we've created."""
        pass


    def test_9999_cleanup(self):
        """Release all resources held by this object for testing purposes."""
        if CSEServerInstallationTest._client is not None:
            CSEServerInstallationTest._client.logout()
