# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
CSE client tests to test validity and functionality of `vcd cse` CLI commands.

Tests these following commands:
$ vcd cse version
$ vcd cse system info
$ vcd cse template list
$ vcd cse ovdc enable ...
$ vcd cse ovdc disable ...

NOTE:
- These tests will install CSE on vCD if CSE is not installed already.
- Edit 'base_config.yaml' for your own vCD instance.
- Testers MUST have an cluster admin user in the org with the same credentials
    as system administrator (system administrators cannot deploy clusters).
- Clusters are deleted on test failure, unless 'teardown_clusters'=false in
    'base_config.yaml'.
- This test module typically takes ~20 minutes to finish per template.

TODO() by priority
- test pks broker
- test that node rollback works correctly (node rollback is not implemented
    yet due to a vcd-side bug, where a partially powered-on VM cannot be force
    deleted)
- tests/fixtures to test command accessibility for various
    users/roles (vcd_cluster_admin() fixture should be replaced with
    a minimum rights user fixture)
- test `vcd cse cluster config testcluster --save` option (currently does
    not work)
- test nfs functionality
- test accessing cluster via kubectl (may be unnecessary)
"""

import collections
import os
import subprocess
import time

import pytest
from system_tests_v2.pytest_logger import PYTEST_LOGGER
from vcd_cli.vcd import vcd

from container_service_extension.server.cli.server_cli import cli
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


OVDC_ENABLE_TEST_PARAM = collections.namedtuple("OvdcEnableParam", "user password org_name ovdc_name disable_before_test expect_failure")  # noqa: E501
OVDC_DISABLE_TEST_PARAM = collections.namedtuple("OvdcDisableParam", "user password org_name ovdc_name enable_before_test expect_failure")  # noqa: E501


@pytest.fixture(scope='module', autouse=True)
def cse_server():
    """Fixture to ensure that CSE is installed and running before client tests.

    This fixture executes automatically for this module's setup and teardown.

    Setup tasks:
    - If templates do not exist, install CSE using `--upgrade`
    - Run `cse install` to ensure that CSE is registered and AMQP
        exchange exists.
    - Run CSE server as a subprocess

    Teardown tasks:
    - Stop CSE server
    """
    env.setup_active_config(logger=PYTEST_LOGGER)
    if env.is_cse_registered_as_mqtt_ext(logger=PYTEST_LOGGER):
        cmd = ['upgrade',
               '--config', env.ACTIVE_CONFIG_FILEPATH,
               '--ssh-key', env.SSH_KEY_FILEPATH,
               '--skip-config-decryption',
               '--skip-template-creation']
    else:
        cmd = ['install',
               '--config', env.ACTIVE_CONFIG_FILEPATH,
               '--ssh-key', env.SSH_KEY_FILEPATH,
               '--skip-config-decryption',
               '--skip-template-creation']
    result = env.CLI_RUNNER.invoke(cli, cmd, input='y', catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', cmd, result.exit_code,
                                      result.output)

    # assign native right bundle to test org
    env.publish_right_bundle_to_deployment_org(logger=PYTEST_LOGGER)
    # assign rights to cluster admin role
    env.assign_native_rights(env.CLUSTER_ADMIN_ROLE_NAME,
                             ["cse:nativeCluster: Full Access",
                              "cse:nativeCluster: Modify",
                              "cse:nativeCluster: View"],
                             logger=PYTEST_LOGGER)
    # assign rights to cluster author role
    env.assign_native_rights(env.CLUSTER_AUTHOR_ROLE_NAME,
                             ["cse:nativeCluster: Modify",
                              "cse:nativeCluster: View"],
                             logger=PYTEST_LOGGER)
    # Create missing templates
    PYTEST_LOGGER.debug("Creating missing templates")
    for template_config in env.TEMPLATE_DEFINITIONS:
        cmd = f"template install {template_config['name']} " \
              f"{template_config['revision']} " \
              f"--config {env.ACTIVE_CONFIG_FILEPATH} " \
              f"--ssh-key {env.SSH_KEY_FILEPATH} " \
              f"--skip-config-decryption"
        result = env.CLI_RUNNER.invoke(
            cli, cmd.split(), catch_exceptions=False)
        assert result.exit_code == 0,\
            testutils.format_command_info('cse', cmd, result.exit_code,
                                          result.output)
        PYTEST_LOGGER.debug("Successfully installed template "
                            f"{template_config['name']} at "
                            f"revision {template_config['revision']}")

    # start cse server as subprocess
    cmd = f"cse run -c {env.ACTIVE_CONFIG_FILEPATH} --skip-config-decryption"
    p = None
    if os.name == 'nt':
        p = subprocess.Popen(cmd, shell=True)
    else:
        p = subprocess.Popen(cmd.split(),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
    time.sleep(env.WAIT_INTERVAL * 3)  # server takes a little while to set up
    PYTEST_LOGGER.debug(p.stdout)
    PYTEST_LOGGER.debug("Successfully started the CSE server.")

    yield

    # terminate cse server subprocess
    try:
        # check if the subprocess is running or not
        if p and p.poll() is None:
            if os.name == 'nt':
                subprocess.Popen(f"taskkill /f /pid {p.pid} /t")
            else:
                p.terminate()
        PYTEST_LOGGER.debug("Killed CSE server")
    except OSError as e:
        PYTEST_LOGGER.warning(f"Failed to kill CSE server {e}")


@pytest.fixture
def vcd_sys_admin():
    """Fixture to ensure that we are logged in to vcd-cli as sys admin.

    Usage: add the parameter 'vcd_sys_admin' to the test function.

    User will have the credentials specified in
    'system_tests/base_config.yaml'

    Do not use this fixture with the other vcd_role fixtures, as only one
    user can be logged in at a time.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} system " \
          f"{config['vcd']['username']} -iwp {config['vcd']['password']} " \
          f"-V {env.VCD_API_VERSION_TO_USE}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    cmd = f"org use {env.TEST_ORG}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # ovdc context may be nondeterministic when there's multiple ovdcs
    cmd = f"vdc use {env.TEST_VDC}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    PYTEST_LOGGER.debug("Logged in as sys admin")
    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug("Logged out as sys admin")


@pytest.fixture
def vcd_cluster_admin():
    """Fixture to ensure that we are logged in to vcd-cli as cluster admin.

    Usage: add the parameter 'vcd_cluster_admin' to the test function.

    User will have the credentials specified in
    'system_test_framework/environment.py'

    Do not use this fixture with the other vcd_role fixtures, as only one
    user can be logged in at a time.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} {env.TEST_ORG} " \
        f"{env.CLUSTER_ADMIN_NAME} -iwp {env.CLUSTER_ADMIN_PASSWORD} " \
        f"-V {env.VCD_API_VERSION_TO_USE}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    # ovdc context may be nondeterministic when there's multiple ovdcs
    cmd = f"vdc use {env.TEST_VDC}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    PYTEST_LOGGER.debug(f"Logged in as {env.CLUSTER_ADMIN_NAME}")

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug(f"Logged out as {env.CLUSTER_ADMIN_NAME}")


@pytest.fixture
def vcd_cluster_author():
    """Fixture to ensure that we are logged in to vcd-cli as vapp author.

    Usage: add the parameter 'vcd_k8_author' to the test function.

    User will have the credentials specified in
    'system_test_framework/environment.py'

    Do not use this fixture with the other vcd_role fixtures, as only one
    user can be logged in at a time.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} {env.TEST_ORG} " \
        f"{env.CLUSTER_AUTHOR_NAME} -iwp {env.CLUSTER_AUTHOR_PASSWORD} " \
        f"-V {env.VCD_API_VERSION_TO_USE}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    # ovdc context may be nondeterministic when there's multiple ovdcs
    cmd = f"vdc use {env.TEST_VDC}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    PYTEST_LOGGER.debug(f"Logged in as {env.CLUSTER_AUTHOR_NAME}")

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug(f"Logged out as {env.CLUSTER_AUTHOR_NAME}")


def cleanup_cluster_artifacts():
    """Can be called to remove cluster artifacts such as Vapp and RDE."""
    env.delete_all_vapps_with_prefix(
        env.SYS_ADMIN_TEST_CLUSTER_NAME,
        vdc_href=env.TEST_VDC_HREF,
        logger=PYTEST_LOGGER)
    env.delete_all_rde_with_prefix(
        env.SYS_ADMIN_TEST_CLUSTER_NAME,
        logger=PYTEST_LOGGER)

    env.delete_all_vapps_with_prefix(
        env.CLUSTER_ADMIN_TEST_CLUSTER_NAME,
        vdc_href=env.TEST_VDC_HREF,
        logger=PYTEST_LOGGER)
    env.delete_all_rde_with_prefix(
        env.CLUSTER_ADMIN_TEST_CLUSTER_NAME,
        logger=PYTEST_LOGGER)

    env.delete_all_vapps_with_prefix(
        env.CLUSTER_AUTHOR_TEST_CLUSTER_NAME,
        vdc_href=env.TEST_VDC_HREF,
        logger=PYTEST_LOGGER)
    env.delete_all_rde_with_prefix(
        env.CLUSTER_AUTHOR_TEST_CLUSTER_NAME,
        logger=PYTEST_LOGGER)


@pytest.fixture
def delete_test_clusters():
    """Fixture to ensure that test cluster doesn't exist before or after tests.

    Usage: add the parameter 'delete_test_cluster' to the test function.

    Setup tasks:
    - Delete test cluster vApp

    Teardown tasks (only if config key 'teardown_clusters'=True):
    - Delete test cluster vApp
    """
    cleanup_cluster_artifacts()

    yield

    if env.TEARDOWN_CLUSTERS:
        cleanup_cluster_artifacts()


def test_0010_vcd_cse_version():
    """Test vcd cse version command."""
    cmd = "cse version"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


def test_0020_vcd_cse_system_info(vcd_cluster_admin):
    """Test vcd cse system info command."""
    cmd = "cse system info"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    assert "version" in result.output


@pytest.fixture
def ovdc_enable_test_case(request):
    test_case: OVDC_ENABLE_TEST_PARAM = request.param

    # login user
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    pwd = test_case.password
    user = test_case.user
    org_name = test_case.org_name
    if test_case.user == env.SYS_ADMIN_NAME:
        user = config['vcd']['username']
        pwd = config['vcd']['password']
        org_name = 'system'
    cmd = f"login {config['vcd']['host']} {org_name} " \
          f"{user} -iwp {pwd} " \
          f"-V {env.VCD_API_VERSION_TO_USE}"

    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")

    PYTEST_LOGGER.debug(f"Logged in as {test_case.user}")

    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    if test_case.disable_before_test:
        # disable ovdc before test
        cmd = f"cse ovdc disable --native --org {test_case.org_name} {test_case.ovdc_name} --force"  # noqa: E501
        env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=True)

    yield test_case

    # disable ovdc after test
    cmd = f"cse ovdc disable --native --org {test_case.org_name} {test_case.ovdc_name} --force"  # noqa: E501
    env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=True)

    # logout
    env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug(f"Logged out as {test_case.user}")


@pytest.mark.parametrize("ovdc_enable_test_case",
                         [OVDC_ENABLE_TEST_PARAM(user=env.SYS_ADMIN_NAME, password="", org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, disable_before_test=True, expect_failure=False),  # noqa: E501
                          OVDC_ENABLE_TEST_PARAM(user=env.CLUSTER_AUTHOR_NAME, password=env.CLUSTER_AUTHOR_PASSWORD, org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, disable_before_test=True, expect_failure=True),  # noqa: E501
                          OVDC_ENABLE_TEST_PARAM(user=env.CLUSTER_ADMIN_NAME, password=env.CLUSTER_ADMIN_PASSWORD, org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, disable_before_test=True, expect_failure=True),  # noqa: E501
                          # Following test should fail because
                          # ovdc will be already enabled for native
                          OVDC_ENABLE_TEST_PARAM(user=env.SYS_ADMIN_NAME, password="", org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, disable_before_test=False, expect_failure=True)],  # noqa: E501
                         indirect=['ovdc_enable_test_case'])
def test_0020_vcd_ovdc_enable(ovdc_enable_test_case: OVDC_ENABLE_TEST_PARAM):
    """Test ovdc enable operation.

    Disabling the test ovdc is necessary to avoid errors if there are clusters
        left over from previous test execution.

    commands:
    $ vcd cse ovdc enable -n -o TEST_ORG TEST_VDC
    """
    cmd = f"cse ovdc enable {ovdc_enable_test_case.ovdc_name} --native --org {ovdc_enable_test_case.org_name}"  # noqa: E501
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=True)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")

    assert result.exit_code == 0 or ovdc_enable_test_case.expect_failure, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


@pytest.fixture
def ovdc_disable_test_case(request):
    test_case: OVDC_DISABLE_TEST_PARAM = request.param
    # login user
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    user = test_case.user
    pwd = test_case.password
    org_name = test_case.org_name
    if test_case.user == env.SYS_ADMIN_NAME:
        user = config['vcd']['username']
        pwd = config['vcd']['password']
        org_name = 'system'
    cmd = f"login {config['vcd']['host']} {org_name} " \
        f"{user} -iwp {pwd} " \
        f"-V {env.VCD_API_VERSION_TO_USE}"

    env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)

    PYTEST_LOGGER.debug(f"Logged in as {test_case.user}")

    if test_case.enable_before_test:
        # disable ovdc before test
        cmd = f"cse ovdc enable --native --org {test_case.org_name} {test_case.ovdc_name}"  # noqa: E501
        env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=True)

    yield test_case

    # logout
    env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug(f"Logged out as {test_case.user}")


@pytest.mark.parametrize("ovdc_disable_test_case",
                         [OVDC_DISABLE_TEST_PARAM(user=env.SYS_ADMIN_NAME, password="", org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=True, expect_failure=False),  # noqa: E501
                          OVDC_DISABLE_TEST_PARAM(user=env.CLUSTER_ADMIN_NAME, password=env.CLUSTER_ADMIN_PASSWORD, org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=True, expect_failure=True),  # noqa: E501
                          OVDC_DISABLE_TEST_PARAM(user=env.CLUSTER_AUTHOR_NAME, password=env.CLUSTER_AUTHOR_PASSWORD, org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=True, expect_failure=True),  # noqa: E501
                          OVDC_DISABLE_TEST_PARAM(user=env.SYS_ADMIN_NAME, password="", org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=False, expect_failure=True)],  # noqa: E501
                         indirect=['ovdc_disable_test_case'])
def test_0100_vcd_ovdc_disable(ovdc_disable_test_case: OVDC_DISABLE_TEST_PARAM):  # noqa: E501
    """Test ovdc disable operation.

    commands:
    $ vcd cse ovdc disable -n -o TEST_ORG TEST_VDC
    """
    cmd = f"cse ovdc disable {env.TEST_VDC} -n -o {env.TEST_ORG}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0 or ovdc_disable_test_case.expect_failure, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


def test_9999_vcd_cse_system_stop(vcd_sys_admin):
    """Test `vcd cse system stop -y`.

    This test shuts down CSE service, so '9999' ensures it runs last.
    """
    # must disable CSE before attempting to stop
    cmd = 'cse system disable'
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    cmd = 'cse system stop'
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                   catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
