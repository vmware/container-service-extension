# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
CSE client tests to test validity and functionality of `vcd cse` CLI commands.

Tests these following commands:
$ vcd cse version
$ vcd cse system info
$ vcd cse template list
$ vcd cse ovdc enalbe ...

(Test cluster apply command for create cluster and resize cluster)
$ vcd cse cluster apply cluster_apply_specification.yaml

$ vcd cse cluster info testcluster
$ vcd cse cluster config testcluster
$ vcd cse cluster list
$ vcd cse cluster delete-nfs testcluster node-name
$ vcd cse cluster delete testcluster

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
        PYTEST_LOGGER.error(f"Failed to kill CSE server {e}")


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
    assert result.exit_code == 0,\
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


def get_rde_version_from_apply_spec(sample_apply_spec):
    rde_version = get_runtime_rde_version_by_vcd_api_version(
        env.VCD_API_VERSION_TO_USE)
    return rde_version


def create_apply_spec(apply_spec_param):
    """Create apply specification throught cse cluster apply --sample command.

    :param dict apply_spec_param: Dictionary containing the information
        that need to be modified in the initial sample command
    :return the dictionary containing the following
    - worker count
    - nfs count
    - tempalte name
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


def cleanup_cluster_artifacts():
    """Can be called to remove cluster artifacts such as Vapp and RDE."""
    env.delete_vapp(env.SYS_ADMIN_TEST_CLUSTER_NAME,
                    vdc_href=env.TEST_VDC_HREF,
                    logger=PYTEST_LOGGER)
    env.delete_rde(env.SYS_ADMIN_TEST_CLUSTER_NAME, logger=PYTEST_LOGGER)

    env.delete_vapp(env.CLUSTER_ADMIN_TEST_CLUSTER_NAME,
                    vdc_href=env.TEST_VDC_HREF,
                    logger=PYTEST_LOGGER)
    env.delete_rde(env.CLUSTER_ADMIN_TEST_CLUSTER_NAME, logger=PYTEST_LOGGER)

    env.delete_vapp(env.CLUSTER_AUTHOR_TEST_CLUSTER_NAME,
                    vdc_href=env.TEST_VDC_HREF,
                    logger=PYTEST_LOGGER)
    env.delete_rde(env.CLUSTER_AUTHOR_TEST_CLUSTER_NAME, logger=PYTEST_LOGGER)


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


@pytest.fixture
def delete_clusters_before_test():
    """Fixture to ensure that cluster don't exist before the test."""
    cleanup_cluster_artifacts()
    yield


def delete_clusters_after_test():
    """Fixture to ensure that cluster don't exist after the test."""
    yield

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


def test_0020_vcd_ovdc_enable(vcd_sys_admin):
    """Test ovdc enable operation.

    commands:
    $ vcd cse ovdc enable -n -o TEST_ORG TEST_VDC
    """
    cmd = f"cse ovdc enable {env.TEST_VDC} -n -o {env.TEST_ORG}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


@pytest.mark.parametrize(
    "test_runner_username,test_case",
    [pytest.param(
        env.SYS_ADMIN_NAME,
        (0, 0, False,
         None, None, 'INVALID-NETWORK',
         None, None, env.SYS_ADMIN_TEST_CLUSTER_NAME))])
def test_0030_vcd_cse_system_toggle(config, delete_test_clusters, test_runner_username, test_case):  # noqa: E501
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
        testutils.CMD_BINDER(cmd=env.SYS_ADMIN_LOGIN_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user='sys_admin'),
        testutils.CMD_BINDER(cmd="cse system disable",
                             exit_code=0,
                             validate_output_func=None,
                             test_user='sys_admin'),
        testutils.CMD_BINDER(cmd=f"cse cluster apply {env.APPLY_SPEC_PATH}",
                             exit_code=2,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd="cse system enable",
                             exit_code=0,
                             validate_output_func=None,
                             test_user='sys_admin'),
        testutils.CMD_BINDER(cmd=f"cse cluster apply {env.APPLY_SPEC_PATH} ",
                             exit_code=0,
                             validate_output_func=_follow_apply_output(),
                             test_user='sys_admin'),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user='sys_admin')
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    assert env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME,
                           vdc_href=env.TEST_VDC_HREF,
                           logger=PYTEST_LOGGER), \
        "Cluster doesn't exist when it should."
    assert env.rde_exists(env.USERNAME_TO_CLUSTER_NAME[env.SYS_ADMIN_NAME],
                          logger=PYTEST_LOGGER)


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
                env.CLUSTER_ADMIN_NAME,
                env.CLUSTER_AUTHOR_NAME
            ]

    test_cases = []
    for user in test_users:
        for template in env.TEMPLATE_DEFINITIONS:
            test_cases.extend(
                [
                    # Invalid Sizing policy
                    pytest.param(
                        user,
                        (0, 0, True,
                         template['name'], template['revision'], None,
                         "INVALID-VALUE", None, f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case1"),  # noqa: E501
                        "CREATE:FAILED"
                    ),
                    # Invalid Storage profile
                    pytest.param(
                        user,
                        (0, 0, True,
                         template['name'], template['revision'], None,
                         None, "INVALID-VALUE", f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case2"),  # noqa: E501
                        "CREATE:FAILED"
                    ),
                    # Invalid Network
                    pytest.param(
                        user,
                        (0, 0, True,
                         template['name'], template['revision'], "INVALID-VALUE",  # noqa: E501
                         None, None, f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case3"),  # noqa: E501
                        "CREATE:FAILED"
                    ),
                    # Invalid network with rollback
                    pytest.param(
                        user,
                        (0, 0, False,
                         template['name'], template['revision'], 'INVALID-NETWORK',  # noqa: E501
                         None, None, f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case4"),  # noqa: E501
                        'CREATE:FAILED'
                    ),
                    # Valid case
                    pytest.param(
                        user,
                        (0, 0, False,
                         template['name'], template['revision'], None,
                         None, None, env.USERNAME_TO_CLUSTER_NAME[user]),
                        'CREATE:SUCCEEDED'
                    ),
                    # # resize a failed deployment
                    pytest.param(
                        user,
                        (1, 0, False,
                         template['name'], template['revision'], 'INVALID-NETWORK',  # noqa: E501
                         None, None, f"{env.USERNAME_TO_CLUSTER_NAME[user]}-case4"),  # noqa: E501
                        'UPDATE:FAILED'
                    ),
                    # Resize up a valid deployment
                    pytest.param(
                        user,
                        (1, 1, False,
                         template['name'], template['revision'], None,
                         None, None, f"{env.USERNAME_TO_CLUSTER_NAME[user]}"),
                        'UPDATE:SUCCEEDED'
                    ),
                    # # Resize down a valid deployment
                    pytest.param(
                        user,
                        (0, 1, False,
                         template['name'], template['revision'], None,
                         None, None, f"{env.USERNAME_TO_CLUSTER_NAME[user]}"),
                        'UPDATE:SUCCEEDED'
                    )
                ]
            )
    return test_cases


@pytest.mark.parametrize('test_runner_username,test_case,expected_phase', _generate_cluster_apply_tests())  # noqa: E501
def test_0040_vcd_cse_cluster_apply(config, test_runner_username, test_case, expected_phase):  # noqa: E501
    """Test 'vcd cse cluster create ...' command for various cse users.

    Test cluster creation from different persona's- sys_admin, org_admin
    and k8_author. Created clusters will remain in the system for further
    command tests - list, resize and delete.

    :param config: cse config file for vcd configuration
    :param test_runner_username: parameterized persona to run tests with
    different users
    """
    print(f"Running cluster create operation for {test_runner_username}")
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

    # create apply specification
    spec_params = testutils.construct_apply_param(test_case)
    create_apply_spec(spec_params)

    if "CREATE" in expected_phase:
        env.delete_vapp(vapp_name=spec_params['cluster_name'],
                        vdc_href=env.TEST_VDC_HREF,
                        logger=PYTEST_LOGGER)
        env.delete_rde(spec_params['cluster_name'])

    exit_code = 0
    if expected_phase == 'UPDATE:FAILED':
        # Validation failure during cluster update will fail the command
        # execution before task is generated.
        exit_code = 2
    expect_failure = "FAILED" in expected_phase

    cmd_list = [
        testutils.CMD_BINDER(cmd=f"cse cluster apply {env.APPLY_SPEC_PATH} ",
                             exit_code=exit_code,
                             validate_output_func=_follow_apply_output(expect_failure=expect_failure),  # noqa: E501
                             test_user=test_runner_username)
    ]
    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    created_cluster_name = spec_params['cluster_name']
    rollback = spec_params['rollback']

    if "CREATE" in expected_phase:
        if "SUCCEEDED" in expected_phase:
            assert env.vapp_exists(created_cluster_name, vdc_href=env.TEST_VDC_HREF), \
                f"Expected VApp to be present for cluster {created_cluster_name}"  # noqa: E501
            assert env.rde_exists(created_cluster_name), \
                f"Expected RDE to be present for cluster {created_cluster_name}"  # noqa: E501
            assert _get_cluster_phase(created_cluster_name, test_runner_username) == 'CREATE:SUCCEEDED', \
                "Expected RDE phase to be 'CREATE:SUCCEEDED'"  # noqa: E501
        if "FAILED" in expected_phase:
            if rollback:
                assert not env.vapp_exists(created_cluster_name, vdc_href=env.TEST_VDC_HREF), \
                    f"Expected VApp to be present for cluster {created_cluster_name}"  # noqa: E501
                assert not env.rde_exists(created_cluster_name), \
                    f"Expected RDE to be present for cluster {created_cluster_name}"  # noqa: E501
            else:
                # During failure, cannot garauntee vapp creation
                assert env.rde_exists(created_cluster_name), \
                    f"Expected RDE for the cluster {created_cluster_name} to be present"  # noqa: E501
                assert _get_cluster_phase(created_cluster_name, test_runner_username) == 'CREATE:FAILED', \
                    "Expected RDE phase to be 'CREATE:FAILED'"  # noqa: E501
    if "UPDATE" in expected_phase:
        if "SUCCEEDED" in expected_phase:
            cmd_list = [
            testutils.CMD_BINDER(cmd=f"cse cluster info {created_cluster_name}",   # noqa
                                 exit_code=0,
                                 validate_output_func=testutils.generate_validate_node_count_func(expected_nodes=spec_params['worker_count']),  # noqa: E501
                                 test_user=test_runner_username)
            ]
            testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)
        # common for both succeeded and failed conditions
        assert _get_cluster_phase(created_cluster_name, test_runner_username) == expected_phase, \
            f"Expected RDE phase to be {expected_phase}"  # noqa: E501

    # logout user
    env.CLI_RUNNER.invoke(vcd, env.USER_LOGOUT_CMD, catch_exceptions=False)


def get_nfs_node_for_2_0_0_cluster(cluster_dict):
    return cluster_dict['status']['nodes']['nfs'][0]['name']


def get_nfs_node_for_1_0_0_cluster(cluster_dict):
    return


def get_nfs_node(cluster_info):
    cluster_dict = yaml.load(cluster_info)
    if 'apiVersion' in cluster_dict:
        return get_nfs_node_for_2_0_0_cluster(cluster_dict)
    return get_nfs_node_for_1_0_0_cluster(cluster_dict)


def validate_if_node_not_present(node_name):
    def validator(output, test_runner_username):
        return node_name not in output


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.CLUSTER_AUTHOR_NAME,
                                                  env.CLUSTER_ADMIN_NAME])
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


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.CLUSTER_AUTHOR_NAME,
                                                  env.CLUSTER_AUTHOR_NAME])
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
                                                  env.CLUSTER_AUTHOR_NAME,
                                                  env.CLUSTER_ADMIN_NAME])
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
                                                  env.CLUSTER_AUTHOR_NAME,
                                                  env.CLUSTER_ADMIN_NAME])
def test_0080_vcd_cse_cluster_config(test_runner_username):
    cmd_list = [
        testutils.CMD_BINDER(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=f"cse cluster config {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=test_runner_username)
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)


def get_worker_count_from_1_0_0_entity_dict(cluster_dict):
    return len(cluster_dict['status']['nodes']['workers'])


def get_worker_count_from_2_0_0_entity_dict(cluster_dict):
    return len(cluster_dict['status']['nodes']['workers'])


def test_0090_vcd_cse_cluster_delete(config):
    """Test 'vcd cse cluster delete ...' command for various cse users.

    Cluster delete operation on the above create clusters operations-
    K8 Author can only delete self created clusters.
    Org admin can delete all cluster in the organization.

    :param config: cse config file for vcd configuration
    """
    cmd_list = [
        testutils.CMD_BINDER(cmd=env.K8_AUTHOR_LOGIN_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.K8_AUTHOR_NAME),
        testutils.CMD_BINDER(cmd=f"cse cluster delete {env.USERNAME_TO_CLUSTER_NAME[env.SYS_ADMIN_NAME]}",  # noqa: E501
                             exit_code=2,
                             validate_output_func=None,
                             test_user=env.K8_AUTHOR_NAME),
        testutils.CMD_BINDER(cmd=f"cse cluster delete {env.USERNAME_TO_CLUSTER_NAME[env.ORG_ADMIN_NAME]}",  # noqa: E501
                             exit_code=2,
                             validate_output_func=None,
                             test_user=env.K8_AUTHOR_NAME),
        testutils.CMD_BINDER(cmd=f"cse cluster delete {env.USERNAME_TO_CLUSTER_NAME[env.K8_AUTHOR_NAME]}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.K8_AUTHOR_NAME),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.K8_AUTHOR_NAME),
        testutils.CMD_BINDER(cmd=env.ORG_ADMIN_LOGIN_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.ORG_ADMIN_NAME),
        testutils.CMD_BINDER(cmd=f"org use {env.TEST_ORG}",
                             exit_code=0,
                             validate_output_func=None,
                             test_user='org_admin'),
        testutils.CMD_BINDER(cmd=f"cse cluster delete {env.USERNAME_TO_CLUSTER_NAME[env.SYS_ADMIN_NAME]}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.ORG_ADMIN_NAME),
        testutils.CMD_BINDER(cmd=f"cse cluster delete {env.USERNAME_TO_CLUSTER_NAME[env.ORG_ADMIN_NAME]}",  # noqa: E501
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.ORG_ADMIN_NAME),
        testutils.CMD_BINDER(cmd=env.USER_LOGOUT_CMD,
                             exit_code=0,
                             validate_output_func=None,
                             test_user=env.ORG_ADMIN_NAME)
    ]

    testutils.execute_commands(cmd_list, logger=PYTEST_LOGGER)

    for cluster_name in env.USERNAME_TO_CLUSTER_NAME.values():
        assert not env.vapp_exists(
            cluster_name,
            vdc_href=env.TEST_VDC_HREF,
            logger=PYTEST_LOGGER), \
            f"Cluster {cluster_name} exists when it should not"


def test_0100_vcd_ovdc_disable(vcd_sys_admin):
    """Test ovdc enable operation.

    commands:
    $ vcd cse ovdc enable -n -o TEST_ORG TEST_VDC
    """
    cmd = f"cse ovdc disable {env.TEST_VDC} -n -o {env.TEST_ORG}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    PYTEST_LOGGER.debug(f"Executing command: {cmd}")
    PYTEST_LOGGER.debug(f"Exit code: {result.exit_code}")
    PYTEST_LOGGER.debug(f"Output: {result.output}")
    assert result.exit_code == 0, \
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
