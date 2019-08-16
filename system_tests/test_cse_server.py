# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import subprocess
import time

import paramiko
import pytest
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC

from container_service_extension.config_validator import get_validated_config
from container_service_extension.configure_cse import check_cse_installation
from container_service_extension.remote_template_manager import \
    get_local_script_filepath
from container_service_extension.remote_template_manager import \
    get_revisioned_template_name
from container_service_extension.server_cli import cli
from container_service_extension.server_constants import ScriptFile
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils
from container_service_extension.template_builder import TEMP_VAPP_VM_NAME
from container_service_extension.utils import read_data_file


"""
CSE server tests to test validity and functionality of `cse` CLI commands.

Tests these following commands:
$ cse check --config cse_test_config.yaml (missing/invalid keys)
$ cse check --config cse_test_config.yaml (incorrect value types)
$ cse check --config cse_test_config.yaml -i (cse not installed yet)

$ cse install --config cse_test_config.yaml --template photon-v2
    --ssh-key ~/.ssh/id_rsa.pub --no-capture

$ cse install --config cse_test_config.yaml --template photon-v2
$ cse install --config cse_test_config.yaml --ssh-key ~/.ssh/id_rsa.pub
    --update --no-capture
$ cse install --config cse_test_config.yaml

$ cse check --config cse_test_config.yaml -i

$ cse run --config cse_test_config.yaml
$ cse run --config cse_test_config.yaml --skip-check

NOTE:
- Edit 'base_config.yaml' for your own vCD instance.
- These tests will use your public/private SSH keys (RSA)
    - Required keys: '~/.ssh/id_rsa' and '~/.ssh/id_rsa.pub'
    - Keys should not be password protected, or tests will fail.
        To remove key password, use `ssh-keygen -p`.
    - ssh-key help: https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/  # noqa
- vCD entities related to CSE (vapps, catalog items) are cleaned up after
    tests run, unless 'teardown_installation'=false in 'base_config.yaml'.
- These tests are meant to run in sequence, but can run independently.
- !!! These tests will fail on Windows !!! We generate temporary config
    files and restrict its permissions due to the check that
    cse install/check performs. This permissions check is incompatible
    with Windows, and is a known issue.
- This test module typically takes ~40 minutes to finish.

TODO() need to check that rights exist when CSE is registered and that rights
don't exist when CSE is not registered. Need a pyvcloud function to check
if a right exists without adding it. Also need functionality to remove CSE
rights when CSE is unregistered.
"""


def _remove_cse_artifacts():
    for template in env.TEMPLATE_DEFINITIONS:
        env.delete_catalog_item(template['source_ova_name'])
        catalog_item_name = get_revisioned_template_name(
            template['name'], template['revision'])
        env.delete_catalog_item(catalog_item_name)
        temp_vapp_name = testutils.get_temp_vapp_name(template['name'])
        env.delete_vapp(temp_vapp_name)
    env.delete_catalog()
    env.unregister_cse()


@pytest.fixture(scope='module', autouse='true')
def delete_installation_entities():
    """Fixture to ensure that CSE entities do not exist in vCD.

    This fixture executes automatically for this module's setup and teardown.

    Setup tasks:
    - Delete source ova files, vapp templates, temp vapps, catalogs
    - Unregister CSE from vCD

    Teardown tasks (only if config key 'teardown_installation'=True):
    - Delete source ova files, vapp templates, temp vapps, catalogs
    - Unregister CSE from vCD
    """
    _remove_cse_artifacts()
    yield
    if env.TEARDOWN_INSTALLATION:
        _remove_cse_artifacts()


@pytest.fixture
def unregister_cse_before_test():
    """Fixture to ensure that CSE is not registered to vCD.

    Usage: add the parameter 'unregister_cse' to the test function.

    Note: we don't do teardown unregister_cse(), because the user may want
    to preserve the state of vCD after tests run.
    """
    env.unregister_cse()


def test_0010_cse_sample():
    """Test that `cse sample` is a valid command.

    Test that `cse sample` command along with every option is an actual
    command. Does not test for validity of sample outputs.
    """
    cmd = "sample"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    output_filepath = 'dummy-output.yaml'
    cmd = f'sample --output {output_filepath}'
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    cmd = f'sample --pks-output {output_filepath}'
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    if os.path.exists(output_filepath):
        os.remove(output_filepath)


def test_0020_cse_version():
    """Test that `cse version` is a valid command."""
    cmd = "version"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)


def test_0030_cse_check(config):
    """Test that `cse check` is a valid command.

    Test that `cse check` command along with every option is an actual command.
    Does not test for validity of config files or CSE installations.
    """
    cmd = f"check -c {env.ACTIVE_CONFIG_FILEPATH}"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    cmd = f"check -c {env.ACTIVE_CONFIG_FILEPATH} -i"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)


def test_0040_config_missing_keys(config):
    """Test that config files with missing keys don't pass validation."""
    bad_key_config1 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config1['amqp']

    bad_key_config2 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config2['vcs'][0]['username']

    configs = [
        bad_key_config1,
        bad_key_config2
    ]

    for config in configs:
        testutils.dict_to_yaml_file(config, env.ACTIVE_CONFIG_FILEPATH)
        try:
            get_validated_config(env.ACTIVE_CONFIG_FILEPATH)
            assert False, f"{env.ACTIVE_CONFIG_FILEPATH} passed validation " \
                          f"when it should not have"
        except KeyError:
            pass


def test_0050_config_invalid_value_types(config):
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
    bad_values_config4['broker']['remote_template_cookbook_url'] = 1

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
        except TypeError:
            pass


def test_0060_config_valid(config):
    """Test that configs with valid keys and value types pass validation."""
    try:
        get_validated_config(env.ACTIVE_CONFIG_FILEPATH)
    except (KeyError, TypeError, ValueError):
        assert False, f"{env.ACTIVE_CONFIG_FILEPATH} did not pass validation" \
                      f" when it should have"


def test_0070_check_invalid_installation(config):
    """Test cse check against config that hasn't been used for installation."""
    try:
        check_cse_installation(config)
        assert False, "cse check passed when it should have failed."
    except Exception:
        pass


def test_0080_install_skip_template_creation(config,
                                             unregister_cse_before_test):
    """Test install.

    Installation options: '--config', '--ssh-key', '--skip-create-templates'

    Tests that installation:
    - registers CSE, without installing the templates

    command: cse install --config cse_test_config.yaml
        --ssh-key ~/.ssh/id_rsa.pub --skip-create-templates
    required files: ~/.ssh/id_rsa.pub, cse_test_config.yaml,
    expected: cse registered, catalog exists, source ovas do not exist,
        temp vapps do not exist, k8s templates do not exist.
    """
    cmd = f"install --config {env.ACTIVE_CONFIG_FILEPATH} --ssh-key " \
          f"{env.SSH_KEY_FILEPATH} --skip-template-creation"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    # check that cse was registered correctly
    env.check_cse_registration(config['amqp']['routing_key'],
                               config['amqp']['exchange'])

    for template_config in env.TEMPLATE_DEFINITIONS:
        # check that source ova file does not exist in catalog
        assert not env.catalog_item_exists(
            template_config['source_ova_name']), \
            'Source ova file exists when it should not.'

        # check that k8s templates does not exist
        catalog_item_name = get_revisioned_template_name(
            template_config['name'], template_config['revision'])
        assert not env.catalog_item_exists(catalog_item_name), \
            'k8s templates exist when they should not.'

        # check that temp vapp does not exists
        temp_vapp_name = testutils.get_temp_vapp_name(template_config['name'])
        assert not env.vapp_exists(temp_vapp_name), \
            'vApp exists when it should not.'


def test_0090_install_retain_temp_vapp(config, unregister_cse_before_test):
    """Test install.

    Installation options: '--config', '--template', '--ssh-key',
        '--retain-temp-vapp'.

    Tests that installation:
    - downloads/uploads ova file,
    - creates photon temp vapp,
    - creates k8s templates
    - skips deleting the temp vapp
    - checks that proper packages are installed in the vm in temp vApp

    command: cse install --config cse_test_config.yaml --retain-temp-vapp
        --ssh-key ~/.ssh/id_rsa.pub
    required files: ~/.ssh/id_rsa.pub, cse_test_config.yaml
    expected: cse registered, catalog exists, source ovas exist,
        temp vapps exist, k8s templates exist.
    """
    cmd = f"install --config {env.ACTIVE_CONFIG_FILEPATH} --ssh-key " \
          f"{env.SSH_KEY_FILEPATH} --retain-temp-vapp"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(),
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    # check that cse was registered correctly
    env.check_cse_registration(config['amqp']['routing_key'],
                               config['amqp']['exchange'])

    vdc = VDC(env.CLIENT, href=env.VDC_HREF)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for template_config in env.TEMPLATE_DEFINITIONS:
        # check that source ova file exists in catalog
        assert env.catalog_item_exists(
            template_config['source_ova_name']), \
            'Source ova file does not exist when it should.'

        # check that k8s templates exist
        catalog_item_name = get_revisioned_template_name(
            template_config['name'], template_config['revision'])
        assert env.catalog_item_exists(catalog_item_name), \
            'k8s template does not exist when it should.'

        # check that temp vapp exists
        temp_vapp_name = testutils.get_temp_vapp_name(
            template_config['name'])
        try:
            vdc.reload()
            vapp_resource = vdc.get_vapp(temp_vapp_name)
        except EntityNotFoundException:
            assert False, 'vApp does not exist when it should.'

        # ssh into vms to check for installed software
        vapp = VApp(env.CLIENT, resource=vapp_resource)
        # The temp vapp is shutdown before the template is captured, it
        # needs to be powered on before trying to ssh into it.
        task = vapp.power_on()
        env.CLIENT.get_task_monitor().wait_for_success(task)
        vapp.reload()
        ip = vapp.get_primary_ip(TEMP_VAPP_VM_NAME)

        try:
            max_tries = 5
            for i in range(max_tries):
                try:
                    ssh_client.connect(ip, username='root')
                    break
                except Exception:
                    if i == max_tries - 1:
                        raise
                    time.sleep(env.WAIT_INTERVAL)

            # run different commands depending on OS
            if 'photon' in temp_vapp_name:
                script_filepath = get_local_script_filepath(
                    template_config['name'], template_config['revision'],
                    ScriptFile.CUST)
                script = read_data_file(script_filepath)
                pattern = r'(kubernetes\S*)'
                packages = re.findall(pattern, script)
                stdin, stdout, stderr = ssh_client.exec_command("rpm -qa")
                installed = [line.strip('.x86_64\n') for line in stdout]
                for package in packages:
                    assert package in installed, \
                        f"{package} not found in Photon VM"
            elif 'ubuntu' in temp_vapp_name:
                script_filepath = get_local_script_filepath(
                    template_config['name'], template_config['revision'],
                    ScriptFile.CUST)
                script = read_data_file(script_filepath)
                pattern = r'((kubernetes|docker\S*|kubelet|kubeadm|kubectl)\S*=\S*)'  # noqa: E501
                packages = [tup[0] for tup in re.findall(pattern, script)]
                cmd = "dpkg -l | awk '{print $2\"=\"$3}'"
                stdin, stdout, stderr = ssh_client.exec_command(cmd)
                installed = [line.strip() for line in stdout]
                for package in packages:
                    assert package in installed, \
                        f"{package} not found in Ubuntu VM"
        finally:
            if ssh_client:
                ssh_client.close()


def test_0100_install_force_update(config, unregister_cse_before_test):
    """Tests installation option: '--update'.

    Tests that installation:
    - creates all templates correctly,
    - customizes temp vapps correctly.

    command: cse install --config cse_test_config.yaml
        --ssh-key ~/.ssh/id_rsa.pub --update
    required files: cse_test_config.yaml, ~/.ssh/id_rsa.pub,
        ubuntu/photon init/cust scripts
    expected: cse registered, source ovas exist, k8s templates exist and
        temp vapps don't exist.
    """
    cmd = f"install --config {env.ACTIVE_CONFIG_FILEPATH} --ssh-key " \
          f"{env.SSH_KEY_FILEPATH} --force-update"
    result = env.CLI_RUNNER.invoke(
        cli, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    # check that cse was registered correctly
    env.check_cse_registration(config['amqp']['routing_key'],
                               config['amqp']['exchange'])

    for template_config in env.TEMPLATE_DEFINITIONS:
        # check that source ova file exists in catalog
        assert env.catalog_item_exists(
            template_config['source_ova_name']), \
            'Source ova file does not existswhen it should.'

        # check that k8s templates exist
        catalog_item_name = get_revisioned_template_name(
            template_config['name'], template_config['revision'])
        assert env.catalog_item_exists(catalog_item_name), \
            'k8s template does not exist when it should.'

        # check that temp vapp does not exists
        temp_vapp_name = testutils.get_temp_vapp_name(
            template_config['name'])
        assert not env.vapp_exists(temp_vapp_name), \
            'vApp exists when it should not.'


def test_0110_cse_check_valid_installation(config):
    """Tests that `cse check` passes for a valid installation.

    command: cse check -c cse_test_config.yaml -i
    expected: check passes
    """
    try:
        check_cse_installation(config)
    except EntityNotFoundException:
        assert False, "cse check failed when it should have passed."


def test_0120_cse_run(config):
    """Test `cse run` command.

    Run cse server as a subprocess with a timeout. If we
    reach the timeout, then cse server was valid and running. Exiting the
    process before then means that server run failed somehow.

    commands:
    $ cse run --config cse_test_config
    $ cse run --config cse_test_config --skip-check
    """
    cmds = [
        f"cse run -c {env.ACTIVE_CONFIG_FILEPATH}",
        f"cse run -c {env.ACTIVE_CONFIG_FILEPATH} -s"
    ]

    for cmd in cmds:
        p = None
        try:
            if os.name == 'nt':
                p = subprocess.Popen(cmd, shell=True)
            else:
                p = subprocess.Popen(cmd.split())
            p.wait(timeout=env.WAIT_INTERVAL * 2) # 1 minute
            assert False, f"`{cmd}` failed with returncode {p.returncode}"
        except subprocess.TimeoutExpired:
            pass
        finally:
            try:
                if p:
                    if os.name == 'nt':
                        subprocess.run(f"taskkill /f /pid {p.pid} /t")
                    else:
                        p.terminate()
            except OSError:
                pass
