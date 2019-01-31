# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
CSE server tests.

TODO() need to check that rights exist when CSE is registered and that rights
don't exist when CSE is not registered. Need a pyvcloud function to check
if a right exists without adding it. Also need functionality to remove CSE
rights when CSE is unregistered.

NOTES:
    - Edit 'base_config.yaml' for your own vCD instance
    - These tests will use your public/private SSH keys (RSA)
        - Required keys: '~/.ssh/id_rsa' and '~/.ssh/id_rsa.pub'
        - Keys should not be password protected, or tests will fail.
            To remove key password, use `ssh-keygen -p`.
        - ssh-key help: https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/  # noqa
    - vCD entities related to CSE (vapps, catalog items) are cleaned up after
        tests run, unless 'developer_mode'=True in 'base_config.yaml'.
    - These tests are meant to run in sequence, but can run independently.
    - !!! These tests will fail on Windows !!! We generate temporary config
        files and restrict its permissions due to the check that
        cse install/check performs. This permissions check is incompatible
        with Windows, and is a known issue.
    - This test module typically takes ~40 minutes to finish.

Tests these following commands:
$ cse check --config cse_test_config.yaml (missing/invalid keys)
$ cse check --config cse_test_config.yaml (incorrect value types)
$ cse check --config cse_test_config.yaml -i (cse not installed yet)

$ cse install --config cse_test_config.yaml --template photon-v2
    --ext skip --ssh-key ~/.ssh/id_rsa.pub --no-capture

$ cse install --config cse_test_config.yaml --template photon-v2

$ cse install --config cse_test_config.yaml --ssh-key ~/.ssh/id_rsa.pub
    --update --no-capture

$ cse install --config cse_test_config.yaml
$ cse check --config cse_test_config.yaml -i
$ cse check --config cse_test_config.yaml -i (invalid templates)

"""

import re

import paramiko
import pytest
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC

from container_service_extension.configure_cse import check_cse_installation
from container_service_extension.configure_cse import get_validated_config
from container_service_extension.cse import cli
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils
import container_service_extension.utils as utils


@pytest.fixture(scope='module', autouse='true')
def delete_installation_entities():
    """Fixture to ensure that CSE entities do not exist in vCD.

    This fixture executes automatically for test module setup and teardown
    If 'developer_mode_aware' is enabled, then the teardown deletion will not
    occur.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    for template in config['broker']['templates']:
        env.delete_catalog_item(template['source_ova_name'])
        env.delete_catalog_item(template['catalog_item'])
        env.delete_vapp(template['temp_vapp'])
    env.delete_catalog()
    env.unregister_cse()

    yield

    if not env.DEV_MODE:
        for template in config['broker']['templates']:
            env.delete_catalog_item(template['source_ova_name'])
            env.delete_catalog_item(template['catalog_item'])
            env.delete_vapp(template['temp_vapp'])
        env.delete_catalog()
        env.unregister_cse()


@pytest.fixture
def blank_cust_scripts():
    """Fixture to ensure that the customization scripts are empty.

    Usage: add the parameter 'blank_cust_scripts' to the test function.
    """
    env.blank_customizaton_scripts()
    yield
    env.blank_customizaton_scripts()


@pytest.fixture
def unregister_cse():
    """Fixture to ensure that CSE is not registered to vCD.

    Usage: add the parameter 'unregister_cse' to the test function.
    """
    env.unregister_cse()


def test_0010_config_invalid_keys(config):
    """Test that config files with invalid/extra keys don't pass validation."""
    bad_key_config1 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config1['amqp']
    bad_key_config1['extra_section'] = True

    bad_key_config2 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config2['vcs'][0]['username']
    bad_key_config2['vcs'][0]['extra_property'] = 'a'

    bad_key_config3 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config3['broker']['templates'][0]['mem']
    del bad_key_config3['broker']['templates'][0]['name']
    bad_key_config3['broker']['templates'][0]['extra_property'] = 0

    configs = [
        bad_key_config1,
        bad_key_config2,
        bad_key_config3
    ]

    for config in configs:
        testutils.dict_to_yaml_file(config, env.ACTIVE_CONFIG_FILEPATH)
        try:
            get_validated_config(env.ACTIVE_CONFIG_FILEPATH)
            assert False, f"{env.ACTIVE_CONFIG_FILEPATH} passed validation " \
                          f"when it should not have"
        except KeyError:
            pass


def test_0020_config_invalid_value_types(config):
    """Test that configs with invalid value types don't pass validation."""
    bad_values_config1 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    bad_values_config1['vcd'] = True
    bad_values_config1['vcs'] = 'a'

    bad_values_config2 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    bad_values_config2['vcd']['username'] = True
    bad_values_config2['vcd']['api_version'] = 123
    bad_values_config2['vcd']['port'] = 'a'

    bad_values_config3 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    bad_values_config3['vcs'][0]['username'] = True
    bad_values_config3['vcs'][0]['password'] = 123
    bad_values_config3['vcs'][0]['verify'] = 'a'

    bad_values_config4 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    bad_values_config4['broker']['templates'][0]['cpu'] = 'a'
    bad_values_config4['broker']['templates'][0]['name'] = 123

    configs = [
        bad_values_config1,
        bad_values_config2,
        bad_values_config3,
        bad_values_config4
    ]

    for config in configs:
        testutils.dict_to_yaml_file(config, env.ACTIVE_CONFIG_FILEPATH)
        try:
            get_validated_config(env.ACTIVE_CONFIG_FILEPATH)
            assert False, f"{env.ACTIVE_CONFIG_FILEPATH} passed validation " \
                          f"when it should not have"
        except ValueError:
            pass


def test_0030_config_valid(config):
    """Test that configs with valid keys and value types pass validation."""
    try:
        get_validated_config(env.ACTIVE_CONFIG_FILEPATH)
    except (KeyError, ValueError):
        assert False, f"{env.ACTIVE_CONFIG_FILEPATH} did not pass validation" \
                      f" when it should have"


def test_0040_check_invalid_installation(config):
    """Test cse check against configs that are invalid/haven't been used."""
    try:
        check_cse_installation(config)
        assert False, "cse check passed when it should have failed."
    except EntityNotFoundException:
        pass


def test_0050_install_no_capture(config, blank_cust_scripts, unregister_cse):
    """Test install.

    Installation options: '--config', '--template', '--ext skip',
        '--ssh-key', '--no-capture'.

    Tests that installation:
    - downloads/uploads ova file,
    - creates photon temp vapp,
    - skips cse registration,
    - skips temp vapp capture.

    command: cse install --config cse_test_config.yaml --template photon-v2
        --ext skip --ssh-key ~/.ssh/id_rsa.pub --no-capture
    required files: ~/.ssh/id_rsa.pub, cse_test_config.yaml,
        photon-v2 init, photon-v2 cust (blank)
    expected: cse not registered, catalog exists, photon-v2 ova exists,
        temp vapp does not exist, template does not exist.
    """
    template_config = None
    for template_dict in config['broker']['templates']:
        if template_dict['name'] == env.PHOTON_TEMPLATE_NAME:
            template_config = template_dict
            break
    assert template_config is not None, \
        'Target template not found in config file'

    result = env.CLI_RUNNER.invoke(cli,
                                   ['install',
                                    '--config', env.ACTIVE_CONFIG_FILEPATH,
                                    '--ssh-key', env.SSH_KEY_FILEPATH,
                                    '--template', env.PHOTON_TEMPLATE_NAME,
                                    '--ext', 'skip',
                                    '--no-capture'],
                                   catch_exceptions=False)
    assert result.exit_code == 0

    # check that cse was not registered
    assert not env.is_cse_registered(), \
        'CSE is registered as an extension when it should not be.'

    # check that source ova file exists in catalog
    assert env.catalog_item_exists(template_config['source_ova_name']), \
        'Source ova file does not exist when it should.'

    # check that vapp templates do not exist
    assert not env.catalog_item_exists(template_config['catalog_item']), \
        'vApp templates exist when they should not (--no-capture was used).'

    # check that temp vapp exists (--no-capture)
    assert env.vapp_exists(template_config['temp_vapp']), \
        'vApp does not exist when it should (--no-capture).'


def test_0060_install_temp_vapp_already_exists(config, blank_cust_scripts,
                                               unregister_cse):
    """Test installation when temp vapp already exists.

    Tests that installation:
    - skips cse registration (answering no to prompt),
    - captures temp vapp as template correctly,
    - does not delete temp_vapp when config file 'cleanup' property is false.

    command: cse install --config cse_test_config.yaml
        --template photon-v2
    required files: cse_test_config.yaml
    expected: cse not registered, photon-v2 template exists, temp-vapp exists
    """
    template_config = None
    # set cleanup to false for this test
    for i, template_dict in enumerate(config['broker']['templates']):
        config['broker']['templates'][i]['cleanup'] = False
        if template_dict['name'] == env.PHOTON_TEMPLATE_NAME:
            template_config = template_dict
            break
    assert template_config is not None, \
        'Target template not found in config file'

    testutils.dict_to_yaml_file(config, env.ACTIVE_CONFIG_FILEPATH)

    res = env.CLI_RUNNER.invoke(cli,
                                ['install',
                                 '--config', env.ACTIVE_CONFIG_FILEPATH,
                                 '--template', env.PHOTON_TEMPLATE_NAME],
                                input='N\nN',
                                catch_exceptions=False)
    assert res.exit_code == 0

    # check that cse was not registered
    assert not env.is_cse_registered(), \
        'CSE is registered as an extension when it should not be.'

    # check that vapp template exists in catalog
    assert env.catalog_item_exists(template_config['catalog_item']), \
        'vApp template does not exist when it should.'

    # check that temp vapp exists (cleanup: false)
    assert env.vapp_exists(template_config['temp_vapp']), \
        'vApp does not exist when it should (cleanup: false).'


def test_0070_install_update(config, blank_cust_scripts, unregister_cse):
    """Tests installation option: '--update'.

    Tests that installation:
    - registers cse (when answering yes to prompt),
    - creates all templates correctly,
    - customizes temp vapps correctly.

    command: cse install --config cse_test_config.yaml
        --ssh-key ~/.ssh/id_rsa.pub --update --no-capture
    required files: cse_test_config.yaml, ~/.ssh/id_rsa.pub,
        ubuntu/photon init/cust scripts
    expected: cse registered, ubuntu/photon ovas exist, temp vapps exist,
        templates exist.
    """
    env.prepare_customization_scripts()
    result = env.CLI_RUNNER.invoke(cli,
                                   ['install',
                                    '--config', env.ACTIVE_CONFIG_FILEPATH,
                                    '--ssh-key', env.SSH_KEY_FILEPATH,
                                    '--update',
                                    '--no-capture'],
                                   input='y\ny',
                                   catch_exceptions=False)
    assert result.exit_code == 0

    vdc = VDC(env.CLIENT, href=env.VDC_HREF)

    # check that cse was registered correctly
    is_cse_registered = env.is_cse_registered()
    assert is_cse_registered, \
        'CSE is not registered as an extension when it should be.'
    if is_cse_registered:
        assert env.is_cse_registration_valid(config['amqp']['routing_key'],
                                             config['amqp']['exchange']), \
            'CSE is registered as an extension, but the extension settings ' \
            'on vCD are not the same as config settings.'

    # ssh into vms to check for installed software
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # check that ova files and temp vapps exist
    for template_config in config['broker']['templates']:
        assert env.catalog_item_exists(template_config['source_ova_name']), \
            'Source ova files do not exist when they should.'

        temp_vapp_name = template_config['temp_vapp']
        try:
            vapp_resource = vdc.get_vapp(temp_vapp_name)
        except EntityNotFoundException:
            assert False, 'vApp does not exist when it should (--no-capture)'

        vapp = VApp(env.CLIENT, resource=vapp_resource)
        ip = vapp.get_primary_ip(temp_vapp_name)
        try:
            ssh_client.connect(ip, username='root')
            # run different commands depending on OS
            if 'photon' in temp_vapp_name:
                script = utils.get_data_file(env.STATIC_PHOTON_CUST_SCRIPT)
                pattern = r'(kubernetes\S*)'
                packages = re.findall(pattern, script)
                stdin, stdout, stderr = ssh_client.exec_command("rpm -qa")
                installed = [line.strip('.x86_64\n') for line in stdout]
                for package in packages:
                    assert package in installed, \
                        f"{package} not found in Photon VM"
            elif 'ubuntu' in temp_vapp_name:
                script = utils.get_data_file(env.STATIC_UBUNTU_CUST_SCRIPT)
                pattern = r'((kubernetes|docker\S*|kubelet|kubeadm|kubectl)\S*=\S*)'  # noqa
                packages = [tup[0] for tup in re.findall(pattern, script)]
                cmd = "dpkg -l | grep '^ii' | awk '{print $2\"=\"$3}'"
                stdin, stdout, stderr = ssh_client.exec_command(cmd)
                installed = [line.strip() for line in stdout]
                for package in packages:
                    assert package in installed, \
                        f"{package} not found in Ubuntu VM"
        finally:
            ssh_client.close()


def test_0080_install_cleanup_true(config, blank_cust_scripts, unregister_cse):
    """Tests that installation deletes temp vapps when 'cleanup' is True.

    Also tests that '--ext config' registers cse.

    command: cse install --config cse_test_config.yaml
    expected: temp vapps are deleted
    """
    for template_config in config['broker']['templates']:
        assert template_config['cleanup'], \
            "'cleanup' key in template config should be True"

    result = env.CLI_RUNNER.invoke(cli,
                                   ['install',
                                    '--config', env.ACTIVE_CONFIG_FILEPATH,
                                    '--ext', 'config'],
                                   catch_exceptions=False)
    assert result.exit_code == 0

    # check that cse was registered correctly
    is_cse_registered = env.is_cse_registered()
    assert is_cse_registered, \
        'CSE is not registered as an extension when it should be.'
    if is_cse_registered:
        assert env.is_cse_registration_valid(config['amqp']['routing_key'],
                                             config['amqp']['exchange']), \
            'CSE is registered as an extension, but the extension settings ' \
            'on vCD are not the same as config settings.'

    for template_config in config['broker']['templates']:
        # check that vapp templates exists
        assert env.catalog_item_exists(template_config['catalog_item']), \
            'vApp template does not exist when it should.'

        # check that temp vapps do not exist (cleanup: true)
        assert not env.vapp_exists(template_config['temp_vapp']), \
            'Temp vapp exists when it should not (cleanup: True).'


def test_0090_cse_check_valid_installation(config):
    """Tests that `cse check` passes for a valid installation.

    command: cse check -c cse_test_config.yaml -i
    expected: check passes
    """
    try:
        check_cse_installation(config)
    except EntityNotFoundException:
        assert False, "cse check failed when it should have passed."


def test_0100_cse_check_invalid_installation(config):
    """Tests that `cse check` fails for an invalid installation.

    command: cse check -c cse_test_config.yaml -i
    expected: check fails
    """
    for i, template_dict in enumerate(config['broker']['templates']):
        config['broker']['templates'][i]['catalog_item'] = f"_bad{i}"

    try:
        check_cse_installation(config)
        assert False, "cse check passed when it should have failed."
    except EntityNotFoundException:
        pass


def test_0110_cse_run():
    pass


def test_0120_cse_sample():
    # TODO(): maybe add a check
    result = env.CLI_RUNNER.invoke(cli, ['sample'], catch_exceptions=False)
    assert result.exit_code == 0


def test_0130_cse_version():
    # TODO(): maybe add a check
    result = env.CLI_RUNNER.invoke(cli, ['version'], catch_exceptions=False)
    assert result.exit_code == 0
