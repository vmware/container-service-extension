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
import pathlib
import time
import unittest

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
    CONFIGS_DIR
from container_service_extension.system_test_framework.utils import \
    yaml_to_dict
from container_service_extension.system_test_framework.utils import \
    diff_amqp_settings
# TODO from container_service_extension.system_test_framework.utils import prepare_customization_scripts  # noqa
from container_service_extension.system_test_framework.utils import \
    restore_customizaton_scripts
from container_service_extension.utils import get_org
from container_service_extension.utils import get_vdc
from container_service_extension.utils import SYSTEM_ORG_NAME
from container_service_extension.utils import wait_for_catalog_item_to_resolve


class CSEServerInstallationTest(unittest.TestCase):
    """Test CSE server installation.
    NOTES:
        - Edit configs in 'system_tests/configs/' for your own vCD instance.
        - These tests are meant to be run in sequence.
    
    Tests these following commands:
    $ cse check --config invalid-keys1.yaml
    $ cse check --config invalid-values1.yaml
    $ cse check --config invalid-misc.yaml -i

    $ cse install --config valid-cleanup.yaml --template photon-v2
        --amqp skip --ext skip --ssh-key ~/.ssh/id_rsa.pub --no-capture

    $ cse install --config valid-no-cleanup.yaml --template photon-v2

    $ cse install --config valid-cleanup.yaml --ssh-key ~/.ssh/id_rsa.pub
        --update --no-capture
    
    $ cse install --config valid-cleanup.yaml
    $ cse check --config valid-cleanup.yaml -i
    $ cse check --config invalid-templates.yaml -i
    """
    _client = None
    _org = None
    _vdc = None
    _api_extension = None
    _amqp_service = None
    _runner = None
    _ssh_key_filepath = None

    # runs once for this class, before all test methods
    @classmethod
    def setUpClass(cls):
        """."""
        config = yaml_to_dict(f'{CONFIGS_DIR}/valid-cleanup.yaml')
        cls._client = Client(config['vcd']['host'],
                             api_version=config['vcd']['api_version'],
                             verify_ssl_certs=config['vcd']['verify'],
                             log_file='cse-install.log',
                             log_headers=True,
                             log_bodies=True)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        cls._client.set_credentials(credentials)
        cls._org = get_org(cls._client, org_name=config['broker']['org'])
        cls._vdc = get_vdc(cls._client, config['broker']['vdc'], org=cls._org)
        cls._api_extension = APIExtension(cls._client)
        cls._amqp_service = AmqpService(cls._client)
        cls._runner = CliRunner()
        cls._ssh_key_filepath = f"{pathlib.Path.home() / '.ssh' / 'id_rsa.pub'}"  # noqa
        cls._original_amqp_settings = to_dict(cls._amqp_service.get_settings())
        cls._amqp_username = config['amqp']['username']
        cls._amqp_password = config['amqp']['password']

        assert cls._client is not None
        assert cls._org is not None
        assert cls._vdc is not None
        assert cls._api_extension is not None
        assert cls._amqp_service is not None
        assert cls._runner is not None
        assert cls._original_amqp_settings is not None
        assert cls._amqp_username is not None
        assert cls._amqp_password is not None

        for template in config['broker']['templates']:
            try:
                cls._org.delete_catalog_item(config['broker']['catalog'],
                                             template['catalog_item'])
                wait_for_catalog_item_to_resolve(cls._client,
                                                 config['broker']['catalog'],
                                                 template['catalog_item'],
                                                 org=cls._org)
                cls._org.reload()
            except EntityNotFoundException:
                pass
            try:
                cls._org.delete_catalog_item(config['broker']['catalog'],
                                             template['source_ova_name'])
                wait_for_catalog_item_to_resolve(cls._client,
                                                 config['broker']['catalog'],
                                                 template['source_ova_name'],
                                                 org=cls._org)
                cls._org.reload()
            except EntityNotFoundException:
                pass
            try:
                cls._vdc.delete_vapp(template['temp_vapp'], force=True)
                # stdout(task, ctx=ctx)
                # have to use sleep instead, because we don't have @ctx
                time.sleep(15)
                cls._vdc.reload()
            except EntityNotFoundException:
                pass

        try:
            cls._org.delete_catalog(config['broker']['catalog'])
        except EntityNotFoundException:
            pass

    # runs before each test method
    def setUp(self):
        pass

    # runs after each test method
    def tearDown(self):
        # reset vcd amqp configuration
        configure_vcd_amqp(self._client,
                           self._original_amqp_settings['AmqpExchange'],
                           self._original_amqp_settings['AmqpHost'],
                           self._original_amqp_settings['AmqpPort'],
                           self._original_amqp_settings['AmqpPrefix'],
                           self._original_amqp_settings['AmqpSslAcceptAll'],
                           self._original_amqp_settings['AmqpUseSSL'],
                           self._original_amqp_settings['AmqpVHost'],
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
        config = yaml_to_dict(f'{CONFIGS_DIR}/valid-cleanup.yaml')
        for template in config['broker']['templates']:
            try:
                cls._org.delete_catalog_item(config['broker']['catalog'],
                                             template['catalog_item'])
                wait_for_catalog_item_to_resolve(cls._client,
                                                 config['broker']['catalog'],
                                                 template['catalog_item'],
                                                 org=cls._org)
                cls._org.reload()
            except EntityNotFoundException:
                pass
            try:
                cls._org.delete_catalog_item(config['broker']['catalog'],
                                             template['source_ova_name'])
                wait_for_catalog_item_to_resolve(cls._client,
                                                 config['broker']['catalog'],
                                                 template['source_ova_name'],
                                                 org=cls._org)
                cls._org.reload()
            except EntityNotFoundException:
                pass
            try:
                cls._vdc.delete_vapp(template['temp_vapp'], force=True)
                # stdout(task, ctx=ctx)
                # have to use sleep instead, because we don't have @ctx
                time.sleep(15)
                cls._vdc.reload()
            except EntityNotFoundException:
                pass
        
        try:
            cls._org.delete_catalog(config['broker']['catalog'])
        except EntityNotFoundException:
            pass

        if cls._client is not None:
            cls._client.logout()

    def test_0010_config_invalid_keys_or_value_types(self):
        """Tests that config file with invalid/extra keys or invalid value
        types do not pass config validation.
        """
        config_files = [
            'invalid-keys1.yaml',
            'invalid-keys2.yaml',
            'invalid-keys3.yaml',
            'invalid-keys4.yaml'
        ]
        for config_filename in config_files:
            try:
                get_validated_config(f'{CONFIGS_DIR}/{config_filename}')
                print(f"{config_filename} passed validation when it should "
                      f"not have")
                assert False
            except KeyError:
                pass
        
        config_files = [
            'invalid-values1.yaml',
            'invalid-values2.yaml',
            'invalid-values3.yaml',
            'invalid-values4.yaml'
        ]
        for config_filename in config_files:
            try:
                get_validated_config(f'{CONFIGS_DIR}/{config_filename}')
                print(f"{config_filename} passed validation when it should "
                      f"not have")
                assert False
            except ValueError:
                pass

    def test_0020_config_valid(self):
        """Tests that config file with valid keys and value types pass
        config validation.
        """
        config_filename = 'valid-cleanup.yaml'
        get_validated_config(f'{CONFIGS_DIR}/{config_filename}')

    def test_0030_check_invalid_installation(self):
        """Tests cse check against config files that are invalid/have not been
        used for installation.
        """
        config_filename = 'valid-cleanup.yaml'
        config = yaml_to_dict(f'{CONFIGS_DIR}/{config_filename}')
        try:
            check_cse_installation(config)
            print("cse check passed when it should have failed.")
            assert False
        except EntityNotFoundException:
            pass

    def test_0040_install_no_capture(self):
        """Tests installation options: '--config', '--template', '--amqp skip',
         '--ext skip', '--ssh-key', '--no-capture'.
        Tests that installation downloads/uploads ova file,
        creates photon temp vapp,
        skips amqp configuration,
        skips cse registration,
        and skips temp vapp capture.

        command: cse install --config valid-cleanup.yaml --template photon-v2
            --amqp skip --ext skip --ssh-key ~/.ssh/id_rsa.pub --no-capture
        required files: ~/.ssh/id_rsa.pub, valid-cleanup.yaml, photon-v2 init,
            photon-v2 cust (blank)
        expected: cse not registered, amqp not configured, catalog exists,
            photon-v2 ova exists, temp vapp does not exist,
            template does not exist.
        """
        config_filepath = f"{CONFIGS_DIR}/valid-cleanup.yaml"
        config = yaml_to_dict(config_filepath)
        target_template = 'photon-v2'
        template_config = None
        for template_dict in config['broker']['templates']:
            if template_dict['name'] == target_template:
                template_config = template_dict
                break
        if template_config is None:
            print('Target template not found in config file')
            assert False

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', config_filepath, 
                                      '--ssh-key', self._ssh_key_filepath,
                                      '--template', target_template,
                                      '--amqp', 'skip',
                                      '--ext', 'skip',
                                      '--no-capture'],
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # check that amqp was not configured
        assert diff_amqp_settings(self._amqp_service, config['amqp'])
        
        # check that cse was not registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
            print('CSE is registered as an extension when it should not be.')
            assert False
        except MissingRecordException:
            pass
        
        # check that source ova file exists in catalog
        self._org.get_catalog_item(config['broker']['catalog'],
                                   template_config['source_ova_name'])

        # check that vapp templates do not exist
        try:
            self._org.get_catalog_item(config['broker']['catalog'],
                                       template_config['catalog_item'])
            print('vApp templates should not exist (--no-capture was used).')
            assert False
        except EntityNotFoundException:
            pass

        # check that temp vapp exists (--no-capture)
        # reload required here or vdc can't find temp_vapp
        self._vdc.reload()
        self._vdc.get_vapp(template_config['temp_vapp'])

    def test_0050_install_temp_vapp_already_exists(self):
        """Tests installation when temp vapp already exists.
        Tests that installation skips amqp configuration (when answering no
        to prompt),
        skips cse registration (when answering no to prompt),
        captures temp vapp as template correctly,
        does not delete temp_vapp when config file 'cleanup' property is false.
        
        command: cse install --config valid-no-cleanup.yaml
            --template photon-v2
        required files: valid-no-cleanup.yaml
        expected: cse not registered, amqp not configured,
            photon-v2 template exists, temp-vapp exists
        """
        config_filepath = f"{CONFIGS_DIR}/valid-no-cleanup.yaml"
        target_template = 'photon-v2'
        config = yaml_to_dict(config_filepath)
        template_config = None
        for template_dict in config['broker']['templates']:
            if template_dict['name'] == target_template:
                template_config = template_dict
                break
        if template_config is None:
            print('Target template not found in config file')
            assert False

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', config_filepath, 
                                      '--template', target_template],
                                     input='N',
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # check that amqp was not configured
        assert diff_amqp_settings(self._amqp_service, config['amqp'])
        
        # check that cse was not registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
            print('CSE is registered as an extension when it should not be.')
            assert False
        except MissingRecordException:
            pass
        
        # check that vapp template exists in catalog
        self._org.get_catalog_item(config['broker']['catalog'],
                                   template_config['catalog_item'])

        # check that temp vapp exists (cleanup: false)
        self._vdc.reload()
        self._vdc.get_vapp(template_config['temp_vapp'])

    def test_0060_install_update(self):
        """Tests installation option: '--update'.
        Tests that installation configures amqp (when answering yes to prompt),
        registers cse (when answering yes to prompt),
        creates all templates correctly,
        customizes temp vapps correctly.
        
        command: cse install --config valid-cleanup.yaml
            --ssh-key ~/.ssh/id_rsa.pub --update --no-capture
        required files: valid-cleanup.yaml, ~/.ssh/id_rsa.pub,
            ubuntu/photon init/cust scripts
            TODO uses blank customization scripts for now.
        expected: cse registered, amqp configured, ubuntu/photon ovas exist,
            temp vapps exist, templates exist.
        """
        config_filepath = f"{CONFIGS_DIR}/valid-cleanup.yaml"
        config = yaml_to_dict(config_filepath)

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', config_filepath,
                                      '--ssh-key', self._ssh_key_filepath,
                                      '--update',
                                      '--no-capture'],
                                     input='y',
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # check that amqp was configured
        assert not diff_amqp_settings(self._amqp_service, config['amqp'])
        
        # check that cse was registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
        except MissingRecordException:
            print('CSE is not registered as an extension when it should be.')
            assert False
        
        # check that ova files and temp vapps exist
        self._vdc.reload()
        for template_config in config['broker']['templates']:
            self._org.get_catalog_item(config['broker']['catalog'],
                                       template_config['source_ova_name'])
            self._vdc.get_vapp(template_config['temp_vapp'])

        # TODO ssh into vapps here to check for customization

    def test_0060_install_cleanup_true(self):
        """Tests that installation deletes temp vapps when 'cleanup' is True.
        Tests that '--amqp/--ext config' configures vcd amqp and registers cse.
        
        command: cse install --config valid-cleanup.yaml
        expected: temp vapps are deleted
        """
        config_filepath = f"{CONFIGS_DIR}/valid-cleanup.yaml"
        config = yaml_to_dict(config_filepath)
        target_template = 'photon-v2'
        template_config = None
        for template_dict in config['broker']['templates']:
            if template_dict['name'] == target_template:
                template_config = template_dict
                assert template_config['cleanup']
                break
        if template_config is None:
            print('Target template not found in config file')
            assert False

        result = self._runner.invoke(cli, 
                                     ['install',
                                      '--config', config_filepath,
                                      '--template', target_template,
                                      '--amqp', 'config',
                                      '--ext', 'config'],
                                     catch_exceptions=False)
        assert result.exit_code == 0

        # check that amqp was configured
        assert not diff_amqp_settings(self._amqp_service, config['amqp'])
        
        # check that cse was registered
        try:
            self._api_extension.get_extension(CSE_NAME,
                                              namespace=CSE_NAMESPACE)
        except MissingRecordException:
            print('CSE is not registered as an extension when it should be.')
            assert False

        # check that temp vapps do not exist (cleanup: true)
        self._vdc.reload()
        try:
            self._vdc.get_vapp(template_config['temp_vapp'])
            print('Temp vapp should not exist')
            assert False
        except EntityNotFoundException:
            pass

        # sub-test to make sure `cse check` works for valid installation
        try:
            check_cse_installation(config, check_template=target_template)
        except EntityNotFoundException:
            print("cse check failed when it should have passed.")
            assert False
        
        # sub-test to make sure `cse check` fails for config file with
        # invalid templates.
        config_filepath = f"{CONFIGS_DIR}/invalid-templates.yaml"
        config = yaml_to_dict(config_filepath)
        try:
            check_cse_installation(config)
            print("cse check passed when it should have failed.")
            assert False
        except EntityNotFoundException:
            pass

