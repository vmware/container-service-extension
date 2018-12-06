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
from pathlib import Path

from click.testing import CliRunner
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from vcd_cli.utils import to_dict

from container_service_extension.config import get_validated_config
from container_service_extension.config import check_cse_installation
from container_service_extension.config import configure_vcd_amqp
from container_service_extension.config import CSE_NAME
from container_service_extension.config import CSE_NAMESPACE
from container_service_extension.cse import cli
# TODO from container_service_extension.system_test_framework.base_install_test import BaseServerInstallTestCase  # noqa
from container_service_extension.system_test_framework.environment import \
    PHOTON_TEMPLATE_NAME, BASE_CONFIG_FILENAME, ACTIVE_CONFIG_FILENAME
from container_service_extension.system_test_framework.utils import \
    yaml_to_dict, dict_to_yaml_file, diff_amqp_settings, \
    restore_customizaton_scripts
from container_service_extension.utils import get_org
from container_service_extension.utils import get_vdc
from container_service_extension.utils import SYSTEM_ORG_NAME
from container_service_extension.utils import wait_for_catalog_item_to_resolve


class CSEServerInstallationTest(unittest.TestCase):
    """Test CSE server installation.
    NOTES:
        - Edit 'base_config.yaml' for your own vCD instance.
        - These tests will run in sequence, but can be run independently.
        - vCD entities related to CSE (vapps, catalog items) persist through
            test cases, and are deleted before and after tests run
            (SetUpClass and TearDownClass).
        - Unable to run these tests on Windows. We generate temporary config
            files and restrict its permissions due to the check that
            cse install/check performs. This permissions check is incompatible
            with Windows, and is a known issue.
    
    Tests these following commands:
    $ cse check --config cse_test_config.yaml (missing/invalid keys)
    $ cse check --config cse_test_config.yaml (incorrect value types)
    $ cse check --config cse_test_config.yaml -i (cse not installed yet)

    $ cse install --config cse_test_config.yaml --template photon-v2
        --amqp skip --ext skip --ssh-key ~/.ssh/id_rsa.pub --no-capture

    $ cse install --config cse_test_config.yaml --template photon-v2

    $ cse install --config cse_test_config.yaml --ssh-key ~/.ssh/id_rsa.pub
        --update --no-capture
    
    $ cse install --config cse_test_config.yaml
    $ cse check --config cse_test_config.yaml -i
    $ cse check --config cse_test_config.yaml -i (invalid templates)
    """
    _client = None
    _org = None
    _vdc = None
    _api_extension = None
    _amqp_service = None
    _runner = None
    _ssh_key_filepath = None
    _default_amqp_settings = None
    _amqp_username = None
    _amqp_password = None

    # test methods should use and modify this
    # this is reset to _base_config before each test
    _config = None

    # base config is source of truth, don't modify these during tests
    _base_config = None
    _base_config_filepath = None
    _active_config_filepath = None

    # runs once for this class, before all test methods
    @classmethod
    def setUpClass(cls):
        """."""
        cls._active_config_filepath = f'{ACTIVE_CONFIG_FILENAME}'
        cls._base_config_filepath = f'{BASE_CONFIG_FILENAME}'

        cls._base_config = yaml_to_dict(cls._base_config_filepath)
        assert cls._base_config is not None
        cls._config = yaml_to_dict(cls._base_config_filepath)

        cls._client = Client(cls._config['vcd']['host'],
                             api_version=cls._config['vcd']['api_version'],
                             verify_ssl_certs=cls._config['vcd']['verify'],
                             log_file='cse-install.log',
                             log_headers=True,
                             log_bodies=True)
        credentials = BasicLoginCredentials(cls._config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            cls._config['vcd']['password'])
        cls._client.set_credentials(credentials)
        assert cls._client is not None

        cls._org = get_org(cls._client, org_name=cls._config['broker']['org'])
        assert cls._org is not None

        cls._vdc = get_vdc(cls._client, cls._config['broker']['vdc'],
                           org=cls._org)
        assert cls._vdc is not None

        cls._api_extension = APIExtension(cls._client)
        assert cls._api_extension is not None

        cls._amqp_service = AmqpService(cls._client)
        assert cls._amqp_service is not None

        cls._runner = CliRunner()
        assert cls._runner is not None

        cls._ssh_key_filepath = f"{Path.home() / '.ssh' / 'id_rsa.pub'}"

        configure_vcd_amqp(cls._client, 'vcdext', cls._config['amqp']['host'],
                           cls._config['amqp']['port'], 'vcd',
                           cls._config['amqp']['ssl_accept_all'],
                           cls._config['amqp']['ssl'], '/',
                           cls._config['amqp']['username'],
                           cls._config['amqp']['password'], quiet=True)
        cls._default_amqp_settings = to_dict(cls._amqp_service.get_settings())
        assert cls._default_amqp_settings is not None

        cls._amqp_username = cls._config['amqp']['username']
        assert cls._amqp_username is not None

        cls._amqp_password = cls._config['amqp']['password']
        assert cls._amqp_password is not None

        try:
            cls._api_extension.delete_extension(CSE_NAME, CSE_NAMESPACE)
        except MissingRecordException:
            pass

        restore_customizaton_scripts()

        CSEServerInstallationTest.delete_cse_entities()

    # runs before each test method
    def setUp(self):
        # reset any modifications that were made to config
        self._config = yaml_to_dict(self._base_config_filepath)
        dict_to_yaml_file(self._config, self._active_config_filepath)
        os.chmod(self._active_config_filepath, 0o600)

    # runs after each test method
    def tearDown(self):
        """Resets vcd amqp settings, unregisters cse from vcd, and blanks out
        customization scripts."""
        # reset vcd amqp configuration
        configure_vcd_amqp(self._client,
                           self._default_amqp_settings['AmqpExchange'],
                           self._default_amqp_settings['AmqpHost'],
                           self._default_amqp_settings['AmqpPort'],
                           self._default_amqp_settings['AmqpPrefix'],
                           self._default_amqp_settings['AmqpSslAcceptAll'],
                           self._default_amqp_settings['AmqpUseSSL'],
                           self._default_amqp_settings['AmqpVHost'],
                           self._amqp_username,
                           self._amqp_password,
                           quiet=True)

        # remove cse as an extension from vcd
        try:
            self._api_extension.delete_extension(CSE_NAME, CSE_NAMESPACE)
        except MissingRecordException:
            pass

        restore_customizaton_scripts()

    # runs once for this class, after all test methods
    @classmethod
    def tearDownClass(cls):
        CSEServerInstallationTest.delete_cse_entities()

        # Remove active config file
        Path(cls._active_config_filepath).unlink()

        if cls._client is not None:
            cls._client.logout()

    @classmethod
    def delete_cse_entities(cls):
        """Deletes ovas, templates, temp vapps, cse catalog."""
        catalog_name = cls._base_config['broker']['catalog']
        for template in cls._base_config['broker']['templates']:
            try:
                cls._org.delete_catalog_item(catalog_name,
                                             template['catalog_item'])
                wait_for_catalog_item_to_resolve(cls._client,
                                                 catalog_name,
                                                 template['catalog_item'],
                                                 org=cls._org)
                cls._org.reload()
            except EntityNotFoundException:
                pass
            try:
                cls._org.delete_catalog_item(catalog_name,
                                             template['source_ova_name'])
                wait_for_catalog_item_to_resolve(cls._client,
                                                 catalog_name,
                                                 template['source_ova_name'],
                                                 org=cls._org)
                cls._org.reload()
            except EntityNotFoundException:
                pass
            try:
                task = cls._vdc.delete_vapp(template['temp_vapp'], force=True)
                cls._client.get_task_monitor().wait_for_success(task)
                cls._vdc.reload()
            except EntityNotFoundException:
                pass
        
        try:
            cls._org.delete_catalog(catalog_name)
            # TODO no way currently to wait for catalog deletion.
            # https://github.com/vmware/pyvcloud/issues/334
            # below causes EntityNotFoundException, catalog not found.
            # time.sleep(15)
            # cls._org.reload()
        except EntityNotFoundException:
            pass

    def test_0010_config_invalid_keys(self):
        """Tests that config file with invalid/extra keys or invalid value
        types do not pass config validation.
        """

        # 3 tests for when config file has missing or extra keys
        invalid_keys_config1 = yaml_to_dict(self._active_config_filepath)
        del invalid_keys_config1['amqp']
        invalid_keys_config1['extra_section'] = True

        invalid_keys_config2 = yaml_to_dict(self._active_config_filepath)
        del invalid_keys_config2['vcs'][0]['username']
        invalid_keys_config2['vcs'][0]['extra_property'] = 'a'

        invalid_keys_config3 = yaml_to_dict(self._active_config_filepath)
        del invalid_keys_config3['broker']['templates'][0]['mem']
        del invalid_keys_config3['broker']['templates'][0]['name']
        invalid_keys_config3['broker']['templates'][0]['extra_property'] = 0

        configs = [
            invalid_keys_config1,
            invalid_keys_config2,
            invalid_keys_config3
        ]

        for config_dict in configs:
            dict_to_yaml_file(config_dict, self._active_config_filepath)
            try:
                get_validated_config(self._active_config_filepath)
                print(f"{self._active_config_filepath} passed validation when "
                      f"it should not have")
                assert False
            except KeyError:
                pass
    
    def test_0020_config_invalid_value_types(self):
        # tests for when config file has incorrect value types
        invalid_values_config1 = yaml_to_dict(self._active_config_filepath)
        invalid_values_config1['vcd'] = True
        invalid_values_config1['vcs'] = 'a'

        invalid_values_config2 = yaml_to_dict(self._active_config_filepath) 
        invalid_values_config2['vcd']['username'] = True
        invalid_values_config2['vcd']['api_version'] = 123
        invalid_values_config2['vcd']['port'] = 'a'

        invalid_values_config3 = yaml_to_dict(self._active_config_filepath) 
        invalid_values_config3['vcs'][0]['username'] = True
        invalid_values_config3['vcs'][0]['password'] = 123
        invalid_values_config3['vcs'][0]['verify'] = 'a'

        invalid_values_config4 = yaml_to_dict(self._active_config_filepath) 
        invalid_values_config4['broker']['templates'][0]['cpu'] = 'a'
        invalid_values_config4['broker']['templates'][0]['name'] = 123

        configs = [
            invalid_values_config1,
            invalid_values_config2,
            invalid_values_config3,
            invalid_values_config4
        ]

        for config_dict in configs:
            dict_to_yaml_file(config_dict, self._active_config_filepath)
            try:
                get_validated_config(self._active_config_filepath)
                print(f"{self._active_config_filepath} passed validation when "
                      f"it should not have")
                assert False
            except ValueError:
                pass

    def test_0030_config_valid(self):
        """Tests that config file with valid keys and value types pass
        config validation.
        """
        try:
            get_validated_config(self._active_config_filepath)
        except (KeyError, ValueError):
            print(f"{self._active_config_filepath} did not pass validation "
                  f"when it should have")
            assert False


    def test_0040_check_invalid_installation(self):
        """Tests cse check against config files that are invalid/have not been
        used for installation.
        """
        try:
            check_cse_installation(self._config)
            print("cse check passed when it should have failed.")
            assert False
        except EntityNotFoundException: 
            # TODO should use CSE specific exception
            pass

    def test_0050_install_no_capture(self):
        """Tests installation options: '--config', '--template', '--amqp skip',
         '--ext skip', '--ssh-key', '--no-capture'.
        Tests that installation downloads/uploads ova file,
        creates photon temp vapp,
        skips amqp configuration,
        skips cse registration,
        and skips temp vapp capture.

        command: cse install --config cse_test_config.yaml --template photon-v2
            --amqp skip --ext skip --ssh-key ~/.ssh/id_rsa.pub --no-capture
        required files: ~/.ssh/id_rsa.pub, cse_test_config.yaml,
            photon-v2 init, photon-v2 cust (blank)
        expected: cse not registered, amqp not configured, catalog exists,
            photon-v2 ova exists, temp vapp does not exist,
            template does not exist.
        """
        template_config = None
        for template_dict in self._config['broker']['templates']:
            if template_dict['name'] == PHOTON_TEMPLATE_NAME:
                template_config = template_dict
                break
        if template_config is None:
            print('Target template not found in config file')
            assert False

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', self._active_config_filepath, 
                                      '--ssh-key', self._ssh_key_filepath,
                                      '--template', PHOTON_TEMPLATE_NAME,
                                      '--amqp', 'skip',
                                      '--ext', 'skip',
                                      '--no-capture'],
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # reloads required due to inability to wait for catalog deletion.
        # vdc can't find vapp unless we reload
        self._org.reload()
        self._vdc.reload()

        # check that amqp was not configured
        assert diff_amqp_settings(self._amqp_service, self._config['amqp'])
        
        # check that cse was not registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
            print('CSE is registered as an extension when it should not be.')
            assert False
        except MissingRecordException:
            pass
        
        # check that source ova file exists in catalog
        try:
            self._org.get_catalog_item(self._config['broker']['catalog'],
                                       template_config['source_ova_name'])
        except EntityNotFoundException:
            print('Source ova files do not exist when they should.')
            assert False

        # check that vapp templates do not exist
        try:
            self._org.get_catalog_item(self._config['broker']['catalog'],
                                       template_config['catalog_item'])
            print('vApp templates should not exist (--no-capture was used).')
            assert False
        except EntityNotFoundException:
            pass

        # check that temp vapp exists (--no-capture)
        try:
            self._vdc.get_vapp(template_config['temp_vapp'])
        except EntityNotFoundException:
            print('vApp does not exist when it should (--no-capture)')
            assert False

    def test_0060_install_temp_vapp_already_exists(self):
        """Tests installation when temp vapp already exists.
        Tests that installation skips amqp configuration (when answering no
        to prompt),
        skips cse registration (when answering no to prompt),
        captures temp vapp as template correctly,
        does not delete temp_vapp when config file 'cleanup' property is false.
        
        command: cse install --config cse_test_config.yaml
            --template photon-v2
        required files: cse_test_config.yaml
        expected: cse not registered, amqp not configured,
            photon-v2 template exists, temp-vapp exists
        """
        template_config = None
        for i, template_dict in enumerate(self._config['broker']['templates']):
            # set cleanup to false for this test
            self._config['broker']['templates'][i]['cleanup'] = False
            if template_dict['name'] == PHOTON_TEMPLATE_NAME:
                template_config = template_dict
                break
        if template_config is None:
            print('Target template not found in config file')
            assert False
        
        dict_to_yaml_file(self._config, self._active_config_filepath)

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', self._active_config_filepath, 
                                      '--template', PHOTON_TEMPLATE_NAME],
                                     input='N\nN',
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # reloads required due to inability to wait for catalog deletion.
        # vdc can't find vapp unless we reload
        self._org.reload()
        self._vdc.reload()

        # check that amqp was not configured
        assert diff_amqp_settings(self._amqp_service, self._config['amqp'])
        
        # check that cse was not registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
            print('CSE is registered as an extension when it should not be.')
            assert False
        except MissingRecordException:
            pass
        
        # check that vapp template exists in catalog
        try:
            self._org.get_catalog_item(self._config['broker']['catalog'],
                                       template_config['catalog_item'])
        except EntityNotFoundException:
            print('vApp template does not exist when it should')
            assert False

        # check that temp vapp exists (cleanup: false)
        try:
            self._vdc.get_vapp(template_config['temp_vapp'])
        except EntityNotFoundException:
            print('vApp does not exist when it should (cleanup: false)')
            assert False

    def test_0070_install_update(self):
        """Tests installation option: '--update'.
        Tests that installation configures amqp (when answering yes to prompt),
        registers cse (when answering yes to prompt),
        creates all templates correctly,
        customizes temp vapps correctly.
        
        command: cse install --config cse_test_config.yaml
            --ssh-key ~/.ssh/id_rsa.pub --update --no-capture
        required files: cse_test_config.yaml, ~/.ssh/id_rsa.pub,
            ubuntu/photon init/cust scripts
            TODO uses blank customization scripts for now.
        expected: cse registered, amqp configured, ubuntu/photon ovas exist,
            temp vapps exist, templates exist.
        """
        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', self._active_config_filepath,
                                      '--ssh-key', self._ssh_key_filepath,
                                      '--update',
                                      '--no-capture'],
                                     input='y\ny',
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # reloads required due to inability to wait for catalog deletion.
        # vdc can't find vapp unless we reload
        self._org.reload()
        self._vdc.reload()

        # check that amqp was configured
        assert not diff_amqp_settings(self._amqp_service, self._config['amqp'])
        
        # check that cse was registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
        except MissingRecordException:
            print('CSE is not registered as an extension when it should be.')
            assert False
        
        # check that ova files and temp vapps exist
        for template_config in self._config['broker']['templates']:
            try:
                self._org.get_catalog_item(self._config['broker']['catalog'],
                                           template_config['source_ova_name'])
            except EntityNotFoundException:
                print('Source ova files do not exist when they should')
                assert False
            try:
                self._vdc.get_vapp(template_config['temp_vapp'])
            except EntityNotFoundException:
                print('vApp does not exist when it should (--no-capture)')
                assert False

        # TODO ssh into vapps here to check for customization

    def test_0080_install_cleanup_true(self):
        """Tests that installation deletes temp vapps when 'cleanup' is True.
        Tests that '--amqp/--ext config' configures vcd amqp and registers cse.
        
        command: cse install --config cse_test_config.yaml
        expected: temp vapps are deleted
        """
        template_config = None
        for template_dict in self._config['broker']['templates']:
            if template_dict['name'] == PHOTON_TEMPLATE_NAME:
                template_config = template_dict
                assert template_config['cleanup']
                break
        if template_config is None:
            print('Target template not found in config file')
            assert False

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', self._active_config_filepath,
                                      '--template', PHOTON_TEMPLATE_NAME,
                                      '--amqp', 'config',
                                      '--ext', 'config'],
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # reloads required due to inability to wait for catalog deletion.
        # vdc can't find vapp unless we reload
        self._org.reload()
        self._vdc.reload()

        # check that amqp was configured
        assert not diff_amqp_settings(self._amqp_service, self._config['amqp'])
        
        # check that cse was registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
        except MissingRecordException:
            print('CSE is not registered as an extension when it should be.')
            assert False

        # check that vapp template exist
        try:
            self._org.get_catalog_item(self._config['broker']['catalog'],
                                       template_config['catalog_item'])
        except EntityNotFoundException:
            print('vApp template does not exist when it should')
            assert False

        # check that temp vapp does not exist (cleanup: true)
        try:
            self._vdc.get_vapp(template_config['temp_vapp'])
            print('Temp vapp should not exist (cleanup: True')
            assert False
        except EntityNotFoundException:
            pass

        # sub-test to make sure `cse check` works for valid installation
        try:
            check_cse_installation(self._config,
                                   check_template=PHOTON_TEMPLATE_NAME)
        except EntityNotFoundException:
            print("cse check failed when it should have passed.")
            assert False
        
        # sub-test to make sure `cse check` fails for config file with
        # invalid templates.
        # change config file to make template names invalid
        for i, template_dict in enumerate(self._config['broker']['templates']):
            self._config['broker']['templates'][i]['catalog_item'] = f"_bad{i}"

        try:
            check_cse_installation(self._config)
            print("cse check passed when it should have failed.")
            assert False
        except EntityNotFoundException:
            pass
