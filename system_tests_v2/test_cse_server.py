# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import filecmp
import os
import subprocess
import tempfile

import pytest
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.vdc import VDC
from system_tests_v2.pytest_logger import PYTEST_LOGGER

from container_service_extension.common.utils import server_utils
from container_service_extension.installer.config_validator import get_validated_config  # noqa: E501
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
from container_service_extension.server.cli.server_cli import cli
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


PASSWORD_FOR_CONFIG_ENCRYPTION = "vmware"

"""
CSE server tests to test validity and functionality of `cse` CLI commands.

Tests these following commands:
$ cse check cse_test_config.yaml --skip-config-decryption (missing/invalid keys)
$ cse check cse_test_config.yaml --skip-config-decryption (incorrect value types)
$ cse check cse_test_config.yaml -i --skip-config-decryption (cse not installed yet)

$ cse install --config cse_test_config.yaml --template photon-v2 --skip-config-decryption
    --ssh-key ~/.ssh/id_rsa.pub --no-capture

$ cse install --config cse_test_config.yaml --template photon-v2 --skip-config-decryption 
$ cse install --config cse_test_config.yaml --ssh-key ~/.ssh/id_rsa.pub
    --update --no-capture --skip-config-decryption 
$ cse install --config cse_test_config.yaml --skip-config-decryption 

$ cse check cse_test_config.yaml -i --skip-config-decryption 

$ cse run --config cse_test_config.yaml --skip-config-decryption 
$ cse run --config cse_test_config.yaml --skip-check --skip-config-decryption

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
        env.delete_catalog_item(template['source_ova_name'],
                                logger=PYTEST_LOGGER)
        catalog_item_name = ltm.get_revisioned_template_name(
            template['name'], template['revision'])
        env.delete_catalog_item(catalog_item_name,
                                logger=PYTEST_LOGGER)
        temp_vapp_name = testutils.get_temp_vapp_name(template['name'])
        env.delete_vapp(temp_vapp_name, vdc_href=env.VDC_HREF)
    env.delete_catalog(logger=PYTEST_LOGGER)
    env.unregister_cse_in_mqtt(logger=PYTEST_LOGGER)
    env.cleanup_rde_artifacts(logger=PYTEST_LOGGER)
    env.cleanup_roles_and_users(logger=PYTEST_LOGGER)


@pytest.fixture(scope='module', autouse=True)
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
    env.unregister_cse_in_mqtt()


def test_0010_cse_sample():
    """Test that `cse sample` is a valid command.

    Test that `cse sample` command along with every option is an actual
    command. Does not test for validity of sample outputs.
    """
    cmd = "sample"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    output_filepath = 'dummy-output.yaml'
    cmd = f'sample --output {output_filepath}'
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    cmd = f'sample --pks-config --output {output_filepath}'
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
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
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)


def test_0030_cse_check(config):
    """Test that `cse check` is a valid command.

    Test that `cse check` command along with every option is an actual command.
    Does not test for validity of config files or CSE installations.
    """
    cmd = f"check {env.ACTIVE_CONFIG_FILEPATH} --skip-config-decryption"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)


def test_0040_config_missing_keys(config):
    """Test that config files with missing keys don't pass validation."""
    bad_key_config1 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config1['mqtt']

    bad_key_config2 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    del bad_key_config2['vcs'][0]['username']

    configs = [
        bad_key_config1,
        bad_key_config2
    ]

    for config in configs:
        testutils.dict_to_yaml_file(config, env.ACTIVE_CONFIG_FILEPATH)
        PYTEST_LOGGER.debug(f"Validating config: {config}")
        try:
            get_validated_config(env.ACTIVE_CONFIG_FILEPATH,
                                 skip_config_decryption=True)
            PYTEST_LOGGER.debug("Validation succeeded when it "
                                "should not have")
            assert False, f"{env.ACTIVE_CONFIG_FILEPATH} passed validation " \
                          f"when it should not have"
        except KeyError as e:
            PYTEST_LOGGER.debug("Validation failed as expected due "
                                f"to invalid keys: {e}")


def test_0050_config_invalid_value_types(config):
    """Test that configs with invalid value types don't pass validation."""
    bad_values_config1 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    bad_values_config1['vcd'] = True
    bad_values_config1['vcs'] = 'a'

    bad_values_config2 = testutils.yaml_to_dict(env.ACTIVE_CONFIG_FILEPATH)
    bad_values_config2['vcd']['username'] = True
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
        PYTEST_LOGGER.debug(f"Validating config: {config}")
        try:
            get_validated_config(env.ACTIVE_CONFIG_FILEPATH,
                                 skip_config_decryption=True)
            assert False, f"{env.ACTIVE_CONFIG_FILEPATH} passed validation " \
                          f"when it should not have"
        except TypeError as e:
            PYTEST_LOGGER.debug("Validation failed as expected due "
                                f"to invalid value: {e}")


def test_0060_config_valid(config):
    """Test that configs with valid keys and value types pass validation."""
    PYTEST_LOGGER.debug(f"Validating config: {config}")
    try:
        get_validated_config(env.ACTIVE_CONFIG_FILEPATH,
                             skip_config_decryption=True)
        PYTEST_LOGGER.debug("Validation succeeded as expected.")
    except (KeyError, TypeError, ValueError) as e:
        PYTEST_LOGGER.debug(f"Failed to validate the config. Error: {e}")
        assert False, f"{env.ACTIVE_CONFIG_FILEPATH} did not pass validation" \
                      f" when it should have"


def test_0070_check_invalid_installation(config):
    """Test cse check against config that hasn't been used for installation."""
    try:
        cmd = f"check {env.ACTIVE_CONFIG_FILEPATH} --skip-config-decryption --check-install"  # noqa: E501
        result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)  # noqa: E501
        PYTEST_LOGGER.debug(f"Executing command: {cmd}")
        PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
        PYTEST_LOGGER.debug(f"Output: {result.output}")
        assert False, "cse check passed when it should have failed."
    except Exception:
        pass


def test_0080_install(
        config,
        unregister_cse_before_test,
        publish_native_right_bundle
):
    """Test install.

    Installation options: '--skip-config-decryption'

    Tests that installation:
    - registers CSE

    command: cse install --config cse_test_config.yaml
        --skip-config-decryption

    required files: cse_test_config.yaml,
    expected: cse registered, catalog exists.
    """
    cmd = f"install --config {env.ACTIVE_CONFIG_FILEPATH} " \
          "--skip-config-decryption"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    # check that cse was registered correctly
    env.check_cse_registration_as_mqtt_extension(logger=PYTEST_LOGGER)


def test_0100_install_select_templates(config):
    """Tests template installation.

    Tests that selected template installation is done correctly

    command: cse template install template_name template_revision
        --config cse_test_config.yaml --ssh-key ~/.ssh/id_rsa.pub
        --skip-config-decryption --retain-temp-vapp
    required files: cse_test_config.yaml, ~/.ssh/id_rsa.pub,
        ubuntu/photon init/cust scripts
    expected: cse registered, source OVAs exist, k8s templates exist and
        temp vapps exist.
    """
    # check that cse was registered correctly
    env.check_cse_registration_as_mqtt_extension()
    remote_template_keys = server_utils.get_template_descriptor_keys(
        env.TEMPLATE_COOKBOOK_VERSION)

    vdc = VDC(env.CLIENT, href=env.VDC_HREF)
    for template_config in env.TEMPLATE_DEFINITIONS:
        # install the template
        cmd = f"template install {template_config[remote_template_keys.NAME]} " \
              f"{template_config['revision']} " \
              f"--config {env.ACTIVE_CONFIG_FILEPATH} " \
              f"--ssh-key {env.SSH_KEY_FILEPATH} " \
              f"--skip-config-decryption --force --retain-temp-vapp"  # noqa: E501
        result = env.CLI_RUNNER.invoke(
            cli, cmd.split(), catch_exceptions=False)
        PYTEST_LOGGER.debug(f"Executing command: {cmd}")
        PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
        PYTEST_LOGGER.debug(f"Output: {result.output}")
        assert result.exit_code == 0,\
            testutils.format_command_info('cse', cmd, result.exit_code,
                                          result.output)
        # check that source ova file exists in catalog
        assert env.catalog_item_exists(
            template_config[remote_template_keys.SOURCE_OVA_NAME],
            logger=PYTEST_LOGGER), \
            'Source ova file does not exists when it should.'

        # check that k8s templates exist
        catalog_item_name = ltm.get_revisioned_template_name(
            template_config[remote_template_keys.NAME],
            template_config[remote_template_keys.REVISION])
        assert env.catalog_item_exists(
            catalog_item_name, logger=PYTEST_LOGGER), \
            'k8s template does not exist when it should.'

        # check that temp vapp exists
        temp_vapp_name = testutils.get_temp_vapp_name(
            template_config[remote_template_keys.NAME])
        try:
            vdc.reload()
            vdc.get_vapp(temp_vapp_name)
        except EntityNotFoundException:
            assert False, 'vApp does not exist when it should.'


def test_0110_cse_check_valid_installation(config):
    """Tests that `cse check` passes for a valid installation.

    command: cse check cse_test_config.yaml -i -s
    expected: check passes
    """
    try:
        cmd = f"check {env.ACTIVE_CONFIG_FILEPATH} --skip-config-decryption --check-install"  # noqa: E501
        result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)  # noqa: E501
        PYTEST_LOGGER.debug(f"Executing command: {cmd}")
        PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
        PYTEST_LOGGER.debug(f"Output: {result.output}")
    except EntityNotFoundException:
        msg = "cse check failed when it should have passed."
        PYTEST_LOGGER.debug(msg)
        assert False, msg


def test_0120_cse_run(config):
    """Test `cse run` command.

    Run cse server as a subprocess with a timeout. If we
    reach the timeout, then cse server was valid and running. Exiting the
    process before then means that server run failed somehow.

    commands:
    $ cse run -c cse_test_config
    $ cse run -c cse_test_config --skip-check --skip-config-decryption
    """
    cmds = [
        f"cse run -c {env.ACTIVE_CONFIG_FILEPATH} --skip-config-decryption",
        f"cse run -c {env.ACTIVE_CONFIG_FILEPATH} --skip-check --skip-config-decryption"  # noqa: E501
    ]

    for cmd in cmds:
        p = None
        try:
            if os.name == 'nt':
                p = subprocess.Popen(cmd, shell=True)
            else:
                p = subprocess.Popen(cmd.split())
            p.wait(timeout=env.WAIT_INTERVAL * 2)  # 1 minute
            msg = f"`{cmd}` failed with return code {p.returncode}"
            PYTEST_LOGGER.debug(f"Executing command: {cmd}")
            PYTEST_LOGGER.debug(msg)
            assert False, msg
        except subprocess.TimeoutExpired as e:
            PYTEST_LOGGER.debug(f"CSE run command execution timedout: {e}")
        finally:
            try:
                if p:
                    if os.name == 'nt':
                        subprocess.run(f"taskkill /f /pid {p.pid} /t")
                    else:
                        p.terminate()
            except OSError as e:
                PYTEST_LOGGER.debug(f"Operating System exception occurred: {e}")  # noqa: E501


def test_0130_cse_encrypt_decrypt_with_password_from_stdin(config):
    """Test `cse encrypt plain-config.yaml and cse decrypt encrypted-config`.

    Get the password for encrypt/decrypt from stdin.

    1. Execute `cse encrypt` on plain-config file and store the encrypted file.
    2. Execute `cse decrypt` on the encrypted config file get decrypted file.
    3. Compare plain-config file and decrypted config file and check result.
    """
    encrypted_file = tempfile.NamedTemporaryFile()
    cmd = f"encrypt {env.ACTIVE_CONFIG_FILEPATH} -o {encrypted_file.name}"  # noqa: E501
    result = env.CLI_RUNNER.invoke(cli,
                                   cmd.split(),
                                   input=PASSWORD_FOR_CONFIG_ENCRYPTION,
                                   catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")

    # Run `cse decrypt` on the encrypted config file from previous step
    decrypted_file = tempfile.NamedTemporaryFile()
    cmd = f"decrypt {encrypted_file.name} -o {decrypted_file.name}"
    result = env.CLI_RUNNER.invoke(cli,
                                   cmd.split(),
                                   input=PASSWORD_FOR_CONFIG_ENCRYPTION,
                                   catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")

    # File comparison also include content comparison
    assert filecmp.cmp(env.ACTIVE_CONFIG_FILEPATH, decrypted_file.name,
                       shallow=False)


def test_0140_cse_encrypt_decrypt_with_password_from_environment_var(config):
    """Test `cse encrypt plain-config.yaml and cse decrypt encrypted-config`.

    Get the password for encrypt/decrypt from environment variable.

    1. Execute `cse encrypt` on plain-config file and store the encrypted file.
    2. Execute `cse decrypt` on the encrypted config file get decrypted file.
    3. Compare plain-config file and decrypted config file and check result.
    """
    os.environ['CSE_CONFIG_PASSWORD'] = PASSWORD_FOR_CONFIG_ENCRYPTION
    encrypted_file = tempfile.NamedTemporaryFile()
    cmd = f"encrypt {env.ACTIVE_CONFIG_FILEPATH} -o {encrypted_file.name}"  # noqa: E501
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")

    # Run `cse decrypt` on the encrypted config file from previous step
    decrypted_file = tempfile.NamedTemporaryFile()
    cmd = f"decrypt {encrypted_file.name} -o {decrypted_file.name}"
    result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")

    # File comparison also include content comparison
    assert filecmp.cmp(env.ACTIVE_CONFIG_FILEPATH, decrypted_file.name,
                       shallow=False)
