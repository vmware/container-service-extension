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
import re
import subprocess
import time

import pytest
from system_tests_v2.pytest_logger import PYTEST_LOGGER
from vcd_cli.vcd import vcd
import yaml

from container_service_extension.rde.utils import get_runtime_rde_version_by_vcd_api_version  # noqa: E501
from container_service_extension.server.cli.server_cli import cli
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


OVDC_ENABLE_TEST_PARAM = collections.namedtuple("OvdcEnableParam", "user password org_name ovdc_name disable_before_test expect_failure")  # noqa: E501
OVDC_DISABLE_TEST_PARAM = collections.namedtuple("OvdcDisableParam", "user password org_name ovdc_name enable_before_test expect_failure")  # noqa: E501
SYSTEM_TOGGLE_TEST_PARAM = collections.namedtuple("SystemToggleTestParam", "user password cluster_name worker_count nfs_count rollback sizing_class storage_profile ovdc_network template_name template_revision expect_failure")  # noqa: E501
CLUSTER_APPLY_TEST_PARAM = collections.namedtuple("ClusterApplyTestParam", "user password cluster_name worker_count nfs_count rollback cpu memory sizing_class storage_profile ovdc_network template_name template_revision expected_phase retain_cluster exit_code should_vapp_exist should_rde_exist required_rde_version")  # noqa: E501
CLUSTER_DELETE_TEST_PARAM = collections.namedtuple("CluserDeleteTestParam", "user password cluster_name org ovdc expect_failure")  # noqa: E501

DEFAULT_CPU_COUNT = 2
DEFAULT_MEMORY_MB = 2048


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
    if env.IS_CSE_SERVER_RUNNING:
        # CSE server is already running
        yield
        return
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


def create_apply_spec(apply_spec_param):
    """Create apply specification throught cse cluster apply --sample command.

    :param dict apply_spec_param: Dictionary containing the information
        that need to be modified in the initial sample command
    :return the dictionary containing the following
    - worker count
    - nfs count
    - template name
    - template revision
    - network
    - sizing class
    - storage profile
    """
    # run cse sample to generate apply sepecification
    cmd = f"cse cluster apply --sample --native -o {env.APPLY_SPEC_PATH}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    PYTEST_LOGGER.debug(f"Using params {apply_spec_param} to create "
                        "apply specification")

    testutils.modify_cluster_apply_spec(env.APPLY_SPEC_PATH, apply_spec_param)


@pytest.fixture
def system_toggle_test_case(request):
    param: SYSTEM_TOGGLE_TEST_PARAM = request.param

    # login as sysadmin
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    user = param.user

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
    PYTEST_LOGGER.debug(f"Logged in as {user}")

    cleanup_cluster_artifacts()

    # create apply specification
    spec_params = {
        'worker_count': param.worker_count,
        'nfs_count': param.nfs_count,
        'rollback': param.rollback,
        'template_name': param.template_name,
        'template_revision': param.template_revision,
        'network': param.ovdc_network,
        'sizing_class': param.sizing_class,
        'storage_profile': param.storage_profile,
        'cluster_name': param.cluster_name
    }
    create_apply_spec(spec_params)

    yield param

    cleanup_cluster_artifacts()

    # logout
    env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug(f"Logged out as {user}")


def _follow_apply_output(expect_failure=False):
    def validator(output, test_runner_username):
        task_wait_command = output.split('\n')[1]
        task_wait_command_args = task_wait_command.split()[1:]

        # follow cluster apply output
        result = env.CLI_RUNNER.invoke(
            vcd, task_wait_command_args, catch_exceptions=True)
        PYTEST_LOGGER.debug(f"Executing command: {task_wait_command}")
        PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
        PYTEST_LOGGER.debug(f"Output: {result.output}")

        if result.exit_code != 0:
            if expect_failure:
                PYTEST_LOGGER.debug(f"{task_wait_command} failed as expected. "
                                    f"Exit code {result.exit_code}. "
                                    f"Output: {result.output}")
                return True
            PYTEST_LOGGER.debug(f"Unexpected failure when executing "
                                f"'{task_wait_command}'. "
                                f"Exit code {result.exit_code}. "
                                f"Output: {result.output}")
            return False
        return True
    return validator


def _follow_delete_output(expect_failure=False):
    def validator(output, test_runner_username):
        task_wait_command = output.split('\n')[2]
        task_wait_command_args = task_wait_command.split()[1:]

        # follow cluster delete output
        result = env.CLI_RUNNER.invoke(
            vcd, task_wait_command_args, catch_exceptions=True)
        PYTEST_LOGGER.debug(f"Executing command: {task_wait_command}")
        PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
        PYTEST_LOGGER.debug(f"Output: {result.output}")

        if result.exit_code != 0:
            if expect_failure:
                PYTEST_LOGGER.debug(f"{task_wait_command} failed as expected. "
                                    f"Exit code {result.exit_code}. "
                                    f"Output: {result.output}")
                return True
            PYTEST_LOGGER.debug(f"Unexpected failure when executing "
                                f"'{task_wait_command}'. "
                                f"Exit code {result.exit_code}. "
                                f"Output: {result.output}")
            return False
        return True
    return validator


@pytest.mark.parametrize(
    "system_toggle_test_case",
    [
        SYSTEM_TOGGLE_TEST_PARAM(
            user=env.SYS_ADMIN_NAME,
            password=None,
            cluster_name=f"{env.SYS_ADMIN_TEST_CLUSTER_NAME}-s1",
            worker_count=0, nfs_count=0, rollback=True,
            sizing_class=None, storage_profile=None,
            ovdc_network="Invalid_network",
            template_name=env.TEMPLATE_DEFINITIONS[0]['name'],
            template_revision=env.TEMPLATE_DEFINITIONS[0]['revision'],
            expect_failure=False)
    ],
    indirect=['system_toggle_test_case']
)
def test_0030_vcd_cse_system_toggle(system_toggle_test_case: SYSTEM_TOGGLE_TEST_PARAM):  # noqa: E501
    """Test `vcd cse system ...` commands.

    Test that on disabling CSE, cluster deployments are no longer
    allowed, and on enabling CSE, cluster deployments are allowed again.
    These commands are combined into 1 test function because only sys admin
    can modify the state of CSE server, org admin/tenant can test cluster
    deployment to ensure that CSE is disabled/enabled. Also, this avoids
    cases such as running the system disable test, and then running the
    cluster operations test, which would fail due to CSE server being
    disabled).
    :param config: cse config file for vcd configuration
    :param test_runner_username: parameterized persona to run tests with
    different users
    """
    cmd_list = [
        testutils.CMD_BINDER(cmd="cse system disable",
                             exit_code=0,
                             validate_output_func=None,
                             test_user=system_toggle_test_case.user),
        testutils.CMD_BINDER(cmd=f"cse cluster apply {env.APPLY_SPEC_PATH}",
                             exit_code=2,
                             validate_output_func=None,
                             test_user=system_toggle_test_case.user),
        testutils.CMD_BINDER(cmd="cse system enable",
                             exit_code=0,
                             validate_output_func=None,
                             test_user=system_toggle_test_case.user),
        testutils.CMD_BINDER(cmd=f"cse cluster apply {env.APPLY_SPEC_PATH} ",
                             exit_code=0,
                             validate_output_func=_follow_apply_output(expect_failure=True),  # noqa: E501
                             test_user=system_toggle_test_case.user)
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)


def _get_cluster_phase(cluster_name, test_runner_username, org_name=None, vdc_name=None):  # noqa: E501
    if not org_name and not vdc_name:
        org_name = env.TEST_ORG
        vdc_name = env.TEST_VDC
    cmd_list = [
        testutils.CMD_BINDER(
            cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
            exit_code=0,
            validate_output_func=None,
            test_user=test_runner_username),
        testutils.CMD_BINDER(
            cmd=f"cse cluster info {cluster_name} -o {org_name} -v {vdc_name}",
            exit_code=0,
            validate_output_func=None,
            test_user=test_runner_username),
    ]
    result = testutils.execute_commands(cmd_list=cmd_list, logger=PYTEST_LOGGER)[-1]  # noqa: E501
    if result.exit_code != 0:
        raise Exception("Cluster {cluster_name} not found.")
    match = re.search(r'phase: (\w+:\w+)', result.output)
    return match[1]


def _generate_cluster_apply_tests(test_users=None):
    """Generate cluster apply test cases.

    param list test_users: the list of users for which the test cases
        should be generated. If not supplied, the tests will be generated for
        all the users. (System admin, Cluster admin and Cluster author)
    The functions which use this method to generate test cases should have
    test_user_name and create_apply_spec as fixture parameters.
    :return: list of test cases of the format
    (test_user, (...apply_spec_params), expected_phase)
    """
    if not test_users:
        # test for all the users
        test_users = \
            [
                env.SYS_ADMIN_NAME,
                env.CLUSTER_ADMIN_NAME
                # env.CLUSTER_AUTHOR_NAME
            ]

    test_cases = []
    for user in test_users:
        for template in env.TEMPLATE_DEFINITIONS:
            test_cases.extend(
                [
                    # Invalid Sizing policy
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case1",  # noqa: E501
                        worker_count=0,
                        nfs_count=0,
                        rollback=True,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class="Invalid_value",
                        storage_profile=None,
                        expected_phase="CREATE:FAILED",
                        retain_cluster=False,
                        exit_code=0,
                        should_rde_exist=False,
                        should_vapp_exist=False,
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # Invalid Storage profile
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=0,
                        rollback=True,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class=None,
                        storage_profile="Invalid_value",
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case2",  # noqa: E501
                        expected_phase="CREATE:FAILED",
                        retain_cluster=False,
                        exit_code=0,
                        should_rde_exist=False,
                        should_vapp_exist=False,
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # Invalid Network
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=0,
                        rollback=True,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network="Invalid_value",
                        cpu=None,
                        memory=None,
                        sizing_class=None,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case3",  # noqa: E501
                        expected_phase="CREATE:FAILED",
                        retain_cluster=False,
                        exit_code=0,
                        should_rde_exist=False,
                        should_vapp_exist=False,
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # Invalid network without rollback
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network="Invalid_value",
                        cpu=None,
                        memory=None,
                        sizing_class=None,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case4",  # noqa: E501
                        expected_phase="CREATE:FAILED",
                        retain_cluster=False,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=False, # creation of vapp will fail
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # cpu/memory and sizing class provided
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=DEFAULT_CPU_COUNT,
                        memory=DEFAULT_MEMORY_MB,
                        sizing_class=env.SIZING_CLASS_NAME,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case5",  # noqa: E501
                        expected_phase="CREATE:FAILED",
                        retain_cluster=False,
                        exit_code=2,
                        should_rde_exist=False,
                        should_vapp_exist=False,
                        required_rde_version=['2.0.0']
                    ),
                    # cluster created with cpu/memory and no sizing class
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=DEFAULT_CPU_COUNT,
                        memory=DEFAULT_MEMORY_MB,
                        sizing_class=None,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case6",  # noqa: E501
                        expected_phase="CREATE:SUCCEEDED",
                        retain_cluster=True,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['2.0.0']
                    ),
                    # Resize a cluster created using cpu/memory with sizing
                    # class
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=1,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class=env.SIZING_CLASS_NAME,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case6",  # noqa: E501
                        expected_phase="CREATE:SUCCEEDED", # validation failure
                        retain_cluster=True,
                        exit_code=2,   # should be 2?
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['2.0.0']
                    ),
                    # Resize a cluster created using cpu/memory using
                    # cpu/memory
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=1,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=DEFAULT_CPU_COUNT,
                        memory=DEFAULT_MEMORY_MB,
                        sizing_class=None,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case6",  # noqa: E501
                        expected_phase="UPDATE:SUCCEEDED",
                        retain_cluster=False,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['2.0.0']
                    ),
                    # Create cluster using sizing policy
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        rollback=False,
                        worker_count=0,
                        nfs_count=0,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class=env.SIZING_CLASS_NAME,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}",
                        expected_phase="CREATE:SUCCEEDED",
                        retain_cluster=True,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # Resize cluster created with sizing class using cpu/mem
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=1,
                        nfs_count=1,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=DEFAULT_CPU_COUNT,
                        memory=DEFAULT_MEMORY_MB,
                        sizing_class=None,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}",
                        expected_phase='CREATE:SUCCEEDED',  # validation fail
                        retain_cluster=True,
                        exit_code=2,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['2.0.0']
                    ),
                    # Resize up a valid deployment
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=1,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class=env.SIZING_CLASS_NAME,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}",
                        expected_phase='UPDATE:SUCCEEDED',
                        retain_cluster=True,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # Resize down a valid deployment
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=0,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class=env.SIZING_CLASS_NAME,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}",
                        expected_phase='UPDATE:SUCCEEDED',
                        retain_cluster=True,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['1.0.0', '2.0.0']
                    ),
                    # Add nfs node
                    CLUSTER_APPLY_TEST_PARAM(
                        user=user,
                        password=None,
                        worker_count=0,
                        nfs_count=1,
                        rollback=False,
                        template_name=template['name'],
                        template_revision=template['revision'],
                        ovdc_network=None,
                        cpu=None,
                        memory=None,
                        sizing_class=env.SIZING_CLASS_NAME,
                        storage_profile=None,
                        cluster_name=f"{env.USERNAME_TO_CLUSTER_NAME[user]}",
                        expected_phase='UPDATE:SUCCEEDED',
                        retain_cluster=True,
                        exit_code=0,
                        should_rde_exist=True,
                        should_vapp_exist=True,
                        required_rde_version=['1.0.0', '2.0.0']
                    )
                ]
            )
    return test_cases


@pytest.fixture
def cluster_apply_param(request):
    param: CLUSTER_APPLY_TEST_PARAM = request.param

    # login as the user
    login_cmd = env.USERNAME_TO_LOGIN_CMD[param.user]
    env.CLI_RUNNER.invoke(vcd, login_cmd.split(), catch_exceptions=False)

    PYTEST_LOGGER.debug(f"Logged in as {param.user}")
    PYTEST_LOGGER.debug(f"Parameters used: {param}")
    # create apply specification
    spec_params = {
        'worker_count': param.worker_count,
        'nfs_count': param.nfs_count,
        'rollback': param.rollback,
        'template_name': param.template_name,
        'template_revision': param.template_revision,
        'network': param.ovdc_network,
        'sizing_class': param.sizing_class,
        'cpu': param.cpu,
        'memory': param.memory,
        'storage_profile': param.storage_profile,
        'cluster_name': param.cluster_name
    }
    create_apply_spec(spec_params)
    # enable ovdc for cluster creation
    cmd = f"cse ovdc enable --native --org {env.TEST_ORG} {env.TEST_VDC}"
    env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=True)

    yield param

    if not param.retain_cluster:
        env.delete_rde(param.cluster_name)
        env.delete_vapp(param.cluster_name, vdc_href=env.TEST_VDC_HREF)
        PYTEST_LOGGER.debug(f"Deleting cluster after test {param.cluster_name}")  # noqa: E501

    # logout
    env.CLI_RUNNER.invoke(vcd, ['logout'])
    PYTEST_LOGGER.debug(f"Logged out as {param.user}")


@pytest.mark.parametrize('cluster_apply_param', _generate_cluster_apply_tests(), indirect=['cluster_apply_param'])  # noqa: E501
def test_0040_vcd_cse_cluster_apply(cluster_apply_param: CLUSTER_APPLY_TEST_PARAM):  # noqa: E501
    """Test 'vcd cse cluster create ...' command for various cse users.

    Test cluster creation from different persona's- sys_admin, org_admin
    and k8_author. Created clusters will remain in the system for further
    command tests - list, resize and delete.
    :param config: cse config file for vcd configuration
    :param test_runner_username: parameterized persona to run tests with
    different users
    """
    print(f"Running cluster create operation for {cluster_apply_param.user}")

    rde_version = get_runtime_rde_version_by_vcd_api_version(
        env.VCD_API_VERSION_TO_USE)
    if rde_version not in cluster_apply_param.required_rde_version:
        # Do not execute the test if not relevant to the RDE version used
        return
    exit_code = cluster_apply_param.exit_code
    expect_failure = "FAILED" in cluster_apply_param.expected_phase

    cmd_list = [
        testutils.CMD_BINDER(cmd=f"cse cluster apply {env.APPLY_SPEC_PATH} ",
                             exit_code=exit_code,
                             validate_output_func=_follow_apply_output(expect_failure=expect_failure),  # noqa: E501
                             test_user=cluster_apply_param.user)
    ]
    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    created_cluster_name = cluster_apply_param.cluster_name

    if cluster_apply_param.should_rde_exist:
        assert env.rde_exists(created_cluster_name), \
            f"Expected RDE to be present for cluster {created_cluster_name}"
        assert _get_cluster_phase(created_cluster_name, cluster_apply_param.user) == cluster_apply_param.expected_phase, \
            f"Expected RDE phase to be {cluster_apply_param.expected_phase}"  # noqa: E501
    else:
        assert not env.rde_exists(created_cluster_name), \
            f"Expected RDE to not exist for cluster {created_cluster_name}"

    if cluster_apply_param.should_vapp_exist:
        assert env.vapp_exists(created_cluster_name, vdc_href=env.TEST_VDC_HREF), \
            f"Expected VApp to be present for cluster {created_cluster_name}"  # noqa: E501
    else:
        assert not env.vapp_exists(created_cluster_name, vdc_href=env.TEST_VDC_HREF), \
            f"Expected VApp to not be present for cluster {created_cluster_name}"  # noqa: E501
    if "UPDATE" in cluster_apply_param.expected_phase:
        if "SUCCEEDED" in cluster_apply_param.expected_phase:
            cmd_list = [
            testutils.CMD_BINDER(cmd=f"cse cluster info {created_cluster_name}",   # noqa
                                 exit_code=0,
                                 validate_output_func=testutils.generate_validate_node_count_func(  # noqa: E501
                                     cluster_name=created_cluster_name,
                                     expected_nodes=cluster_apply_param.worker_count,  # noqa: E501
                                     rde_version=get_runtime_rde_version_by_vcd_api_version(env.VCD_API_VERSION_TO_USE),  # noqa: E501
                                     logger=PYTEST_LOGGER),  # noqa: E501
                                 test_user=cluster_apply_param.user)
            ]
            testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    # logout user
    env.CLI_RUNNER.invoke(vcd, env.USER_LOGOUT_CMD, catch_exceptions=False)


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.CLUSTER_ADMIN_NAME
                                                  #   env.CLUSTER_AUTHOR_NAME
                                                  ])
def test_0060_vcd_cse_cluster_list(test_runner_username):
    cmd_list = [
        testutils.CMD_BINDER(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd="cse cluster list",
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username)
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.CLUSTER_AUTHOR_NAME
                                                  #   env.CLUSTER_ADMIN_NAME
                                                  ])
def test_0070_vcd_cse_cluster_info(test_runner_username):
    cmd_list = [
        testutils.CMD_BINDER(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=f"cse cluster info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=testutils.validate_yaml_output(),  # noqa: E501
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username)
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.CLUSTER_AUTHOR_NAME
                                                  #   env.CLUSTER_ADMIN_NAME
                                                  ])
def test_0080_vcd_cse_cluster_config(test_runner_username):
    # Failing for the first call with err:
    # Error: Expecting value: line 1 column 1 (char 0)
    cmd_list = [
        testutils.CMD_BINDER(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=f"cse cluster config {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=testutils.validate_yaml_output(),  # noqa: E501
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username)
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)


def get_nfs_node_for_2_0_0_cluster(cluster_dict):
    return cluster_dict['status']['nodes']['nfs'][0]['name']


def get_nfs_node_for_1_0_0_cluster(cluster_dict):
    return cluster_dict['status']['nodes']['nfs'][0]['name']


def get_nfs_node(cluster_info):
    cluster_dict = yaml.safe_load(cluster_info)
    if 'apiVersion' in cluster_dict:
        return get_nfs_node_for_2_0_0_cluster(cluster_dict)
    return get_nfs_node_for_1_0_0_cluster(cluster_dict)


def validate_if_node_not_present(node_name):
    def validator(output, test_runner_username):
        return node_name not in output
    return validator


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.CLUSTER_AUTHOR_NAME
                                                  #   env.CLUSTER_ADMIN_NAME
                                                  ])
def test_0050_vcd_cse_delete_nfs(test_runner_username):
    """Test delete nfs node command."""
    cluster_name = env.USERNAME_TO_CLUSTER_NAME[test_runner_username]

    cmd_list = [
        testutils.CMD_BINDER(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=f"org use {env.TEST_ORG}",
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=f"vdc use {env.TEST_VDC}",
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username)
    ]
    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    cmd_list = [
        testutils.CMD_BINDER(cmd=f"cse cluster info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",   # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username)
    ]
    cmd_results = testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    nfs_node = get_nfs_node(cmd_results[0].output)

    cmd_list = [
        testutils.CMD_BINDER(cmd=f"cse cluster delete-nfs {cluster_name} {nfs_node}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=f"cse cluster info {cluster_name}",
                             exit_code=0,
                             validate_output_func=validate_if_node_not_present(nfs_node),  # noqa: E501
                             test_user=test_runner_username)
    ]
    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)


@pytest.mark.parametrize("cluster_delete_param",
                         [
                             CLUSTER_DELETE_TEST_PARAM(
                                 user=env.CLUSTER_ADMIN_NAME,
                                 password=None,
                                 cluster_name=f"{env.SYS_ADMIN_TEST_CLUSTER_NAME}",  # noqa: E501
                                 org=env.TEST_ORG,
                                 ovdc=env.TEST_VDC,
                                 expect_failure=True),
                             #  CLUSTER_DELETE_TEST_PARAM(
                             #      user=env.CLUSTER_AUTHOR_NAME,
                             #      password=None,
                             #      cluster_name=f"{env.CLUSTER_ADMIN_TEST_CLUSTER_NAME}",  # noqa: E501
                             #      org=env.TEST_ORG,
                             #      ovdc=env.TEST_VDC,
                             #      expect_failure=True),
                             CLUSTER_DELETE_TEST_PARAM(
                                 user=env.SYS_ADMIN_NAME,
                                 password=None,
                                 cluster_name=f"{env.SYS_ADMIN_TEST_CLUSTER_NAME}",  # noqa: E501
                                 org=env.TEST_ORG,
                                 ovdc=env.TEST_VDC,
                                 expect_failure=False),
                             CLUSTER_DELETE_TEST_PARAM(
                                 user=env.CLUSTER_ADMIN_NAME,
                                 password=None,
                                 cluster_name=f"{env.CLUSTER_ADMIN_TEST_CLUSTER_NAME}",  # noqa: E501
                                 org=env.TEST_ORG,
                                 ovdc=env.TEST_VDC,
                                 expect_failure=False),
                             # TODO change back to cluster admin deleting
                             # cluster author's cluster
                             #  CLUSTER_DELETE_TEST_PARAM(
                             #      user=env.SYS_ADMIN_NAME,
                             #      password=None,
                             #      cluster_name=f"{env.CLUSTER_AUTHOR_TEST_CLUSTER_NAME}",  # noqa: E501
                             #      org=env.TEST_ORG,
                             #      ovdc=env.TEST_VDC,
                             #      expect_failure=False),
                         ])
def test_0090_vcd_cse_cluster_delete(cluster_delete_param: CLUSTER_DELETE_TEST_PARAM):  # noqa: E501
    """Test 'vcd cse cluster delete ...' command for various cse users.

    Cluster delete operation on the above create clusters operations-
    cluster Author can only delete self created clusters.
    cluster admin can delete all cluster in the organization.

    :param config: cse config file for vcd configuration
    """
    cmd_list = [
        testutils.CMD_BINDER(cmd=env.USERNAME_TO_LOGIN_CMD[cluster_delete_param.user],  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=cluster_delete_param.user),
        testutils.CMD_BINDER(cmd=f"org use {cluster_delete_param.org}",
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.CLUSTER_ADMIN_NAME),
        testutils.CMD_BINDER(cmd=f"cse cluster delete {cluster_delete_param.cluster_name}",  # noqa: E501
                             exit_code=2 if cluster_delete_param.expect_failure else 0,  # noqa: E501
                             validate_output_func=_follow_delete_output(expect_failure=cluster_delete_param.expect_failure),  # noqa: E501
                             test_user=cluster_delete_param.user),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.CLUSTER_AUTHOR_NAME),
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    if not cluster_delete_param.expect_failure:
        assert not env.vapp_exists(
            cluster_delete_param.cluster_name,
            vdc_href=env.TEST_VDC_HREF,
            logger=PYTEST_LOGGER), \
            f"Cluster {cluster_delete_param.cluster_name} exists when it should not"  # noqa: E501


@pytest.mark.parametrize("ovdc_disable_test_case",
                         [OVDC_DISABLE_TEST_PARAM(user=env.SYS_ADMIN_NAME, password="", org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=True, expect_failure=False),  # noqa: E501
                          OVDC_DISABLE_TEST_PARAM(user=env.CLUSTER_ADMIN_NAME, password=env.CLUSTER_ADMIN_PASSWORD, org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=True, expect_failure=True),  # noqa: E501
                          #   OVDC_DISABLE_TEST_PARAM(user=env.CLUSTER_AUTHOR_NAME, password=env.CLUSTER_AUTHOR_PASSWORD, org_name=env.TEST_ORG, ovdc_name=env.TEST_VDC, enable_before_test=True, expect_failure=True),  # noqa: E501
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
