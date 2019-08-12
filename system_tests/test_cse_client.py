# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
CSE client tests to test validity and functionality of `vcd cse` CLI commands.

Tests these following commands:
$ vcd cse version
$ vcd cse system info
$ vcd cse template list

$ vcd cse cluster create testcluster -n NETWORK -N 1 -c 1000
$ vcd cse cluster create testcluster -n NETWORK -N 1 -c 1000
    --disable-rollback

$ vcd cse cluster create testcluster -n NETWORK -N 1 -t photon-v2
$ vcd cse cluster info testcluster
$ vcd cse cluster config testcluster
$ vcd cse cluster list
$ vcd cse node list testcluster
$ vcd cse node info testcluster TESTNODE
$ vcd cse node delete testcluster TESTNODE
$ vcd cse node create testcluster -n NETWORK -t photon-v2
$ vcd cse cluster delete testcluster

NOTE:
- These tests will install CSE on vCD if CSE is not installed already.
- Edit 'base_config.yaml' for your own vCD instance.
- Testers MUST have an org admin user in the org with the same credentials
    as system administrator (system administrators cannot deploy clusters).
- Clusters are deleted on test failure, unless 'teardown_clusters'=false in
    'base_config.yaml'.
- This test module typically takes ~20 minutes to finish per template.

TODO() by priority
- test `vcd cse ovdc...` commands
- test system administrator should be able to deploy cluster
- test pks broker
- test that node rollback works correctly (node rollback is not implemented
    yet due to a vcd-side bug, where a partially powered-on VM cannot be force
    deleted)
- tests/fixtures to test command accessibility for various
    users/roles (vcd_org_admin() fixture should be replaced with
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
from vcd_cli.vcd import vcd

from container_service_extension.cse import cli
import container_service_extension.server_constants as constants
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
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    install_cmd = ['install', '--config', env.ACTIVE_CONFIG_FILEPATH,
                   '--ssh-key', env.SSH_KEY_FILEPATH]
    env.setup_active_config()
    result = env.CLI_RUNNER.invoke(cli, install_cmd,
                                   input='y',
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('cse', install_cmd, result.exit_code,
                                      result.output)

    # start cse server as subprocess
    cmd = f"cse run -c {env.ACTIVE_CONFIG_FILEPATH}"
    p = None
    if os.name == 'nt':
        p = subprocess.Popen(cmd, shell=True)
    else:
        p = subprocess.Popen(cmd.split(),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
    time.sleep(env.WAIT_INTERVAL)  # server takes a little while to set up

    # enable kubernetes functionality on our ovdc
    # by default, an ovdc cannot deploy kubernetes clusters
    # TODO() this should be removed once this behavior is changed
    cmd = f"login {config['vcd']['host']} {constants.SYSTEM_ORG_NAME} " \
          f"{config['vcd']['username']} -iwp {config['vcd']['password']} " \
          f"-V {config['vcd']['api_version']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    cmd = f"org use {config['broker']['org']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    cmd = f"vdc use {config['broker']['vdc']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    cmd = f"cse ovdc enable {config['broker']['vdc']} -k " \
          f"{constants.K8sProvider.NATIVE}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    result = env.CLI_RUNNER.invoke(vcd, 'logout', catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    yield

    # terminate cse server subprocess
    try:
        # check if the subprocess is running or not
        if p and p.poll() is None:
            if os.name == 'nt':
                subprocess.Popen(f"taskkill /f /pid {p.pid} /t")
            else:
                p.terminate()
    except OSError:
        pass


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
          f"-V {config['vcd']['api_version']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    cmd = f"org use {config['broker']['org']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # ovdc context may be nondeterministic when there's multiple ovdcs
    cmd = f"vdc use {config['broker']['vdc']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])


@pytest.fixture
def vcd_org_admin():
    """Fixture to ensure that we are logged in to vcd-cli as org admin.

    Usage: add the parameter 'vcd_org_admin' to the test function.

    User will have the credentials specified in
    'system_test_framework/environment.py'

    Do not use this fixture with the other vcd_role fixtures, as only one
    user can be logged in at a time.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} {config['broker']['org']} " \
          f"{env.ORG_ADMIN_NAME} -iwp {env.ORG_ADMIN_PASSWORD} " \
          f"-V {config['vcd']['api_version']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    # ovdc context may be nondeterministic when there's multiple ovdcs
    cmd = f"vdc use {config['broker']['vdc']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])


@pytest.fixture
def vcd_vapp_author():
    """Fixture to ensure that we are logged in to vcd-cli as vapp author.

    Usage: add the parameter 'vcd_vapp_author' to the test function.

    User will have the credentials specified in
    'system_test_framework/environment.py'

    Do not use this fixture with the other vcd_role fixtures, as only one
    user can be logged in at a time.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} {config['broker']['org']} " \
          f"{env.VAPP_AUTHOR_NAME} -iwp {env.VAPP_AUTHOR_PASSWORD} " \
          f"-V {config['vcd']['api_version']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    # ovdc context may be nondeterministic when there's multiple ovdcs
    cmd = f"vdc use {config['broker']['vdc']}"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])


@pytest.fixture
def delete_test_clusters():
    """Fixture to ensure that test cluster doesn't exist before or after tests.

    Usage: add the parameter 'delete_test_cluster' to the test function.

    Setup tasks:
    - Delete test cluster vApp

    Teardown tasks (only if config key 'teardown_clusters'=True):
    - Delete test cluster vApp
    """
    env.delete_vapp(env.SYS_ADMIN_TEST_CLUSTER_NAME)
    env.delete_vapp(env.ORG_ADMIN_TEST_CLUSTER_NAME)
    env.delete_vapp(env.VAPP_ADMIN_TEST_CLUSTER_NAME)

    yield

    if env.TEARDOWN_CLUSTERS:
        env.delete_vapp(env.SYS_ADMIN_TEST_CLUSTER_NAME)
        env.delete_vapp(env.ORG_ADMIN_TEST_CLUSTER_NAME)
        env.delete_vapp(env.VAPP_ADMIN_TEST_CLUSTER_NAME)


def execute_commands(cmd_list):
    cmd_results = []
    for action in cmd_list:
        cmd = action.cmd
        print('CMD=', action.cmd)
        expected_exit_code = action.exit_code
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                       catch_exceptions=False)
        assert result.exit_code == expected_exit_code, \
            testutils.format_command_info(
                'vcd', cmd, result.exit_code, result.output)

        if action.validate_output_func is not None:
            action.validate_output_func(result.output, action.test_user)

        cmd_results.append(result)

    return cmd_results


def list_cluster_output_validator(output, runner_username):
    """Test cse cluster list command output.

    Validate cse cluster list command based on persona.

    :param output: list of results from execution of cse commands
    :param runner_username: persona used to run the command
    """
    def cluster_list_validator(output):
        count = re.findall('testcluster', output)
        return len(count)

    if runner_username == 'sys_admin':
        # sys admin can see all the clusters
        cluster_count = cluster_list_validator(output)
        assert cluster_count == 3

    if runner_username == 'org_admin':
        # org admin can see all the clusters belonging to the org
        cluster_count = cluster_list_validator(output)
        assert cluster_count == 3

    if runner_username == 'vapp_author':
        # vapp author can only see clusters created by him
        cluster_count = cluster_list_validator(output)
        assert cluster_count == 1


def test_0010_vcd_cse_version():
    """Test vcd cse version command."""
    cmd = "cse version"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


def test_0020_vcd_cse_system_info(vcd_org_admin):
    """Test vcd cse system info command."""
    cmd = "cse system info"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


def test_0030_vcd_cse_cluster_create_rollback(config, vcd_org_admin,
                                              delete_test_clusters):
    """Test that --disable-rollback option works during cluster creation.

    commands:
    $ vcd cse cluster create testcluster -n NETWORK -N 1 -c 1000
    $ vcd cse cluster create testcluster -n NETWORK -N 1 -c 1000
        --disable-rollback
    """
    cmd = f"cse cluster create {env.SYS_ADMIN_TEST_CLUSTER_NAME} -n " \
          f"{config['broker']['network']} -N 1 -c 1000"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # TODO: Make cluster rollback delete call blocking
    time.sleep(env.WAIT_INTERVAL * 2)  # wait for vApp to be deleted
    assert not env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME), \
        "Cluster exists when it should not."

    cmd += " --disable-rollback"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    assert env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME), \
        "Cluster does not exist when it should."


def test_0040_vcd_cse_cluster_and_node_operations(config, vcd_org_admin,
                                                  delete_test_clusters):
    """Test cse cluster/node commands.

    This test function contains several sub-test blocks that can be commented
    out or moved around for speed optimization purposes during testing.
    """
    # keeps track of the number of nodes that should exist.
    # Streamlines assert statements when checking node count
    num_nodes = 0

    def check_node_list():
        """Use `vcd cse node list` to verify that nodes were added/deleted.

        Internal function used to count nodes and validate that
        create/delete commands work as expected.

        Example: if we add a node to a cluster with 1 node, we expect to have
        2 nodes total. If this function finds that only 1 node exists, then
        this test will fail.

        :return: list of node names

        :rtype: List[str]
        """
        node_pattern = r'(node-\S+)'
        node_list_cmd = f"cse node list {env.SYS_ADMIN_TEST_CLUSTER_NAME}"
        print(f"Running command [vcd {node_list_cmd}]...", end='')
        node_list_result = env.CLI_RUNNER.invoke(vcd, node_list_cmd.split(),
                                                 catch_exceptions=False)
        assert node_list_result.exit_code == 0, \
            testutils.format_command_info('vcd', node_list_cmd,
                                          node_list_result.exit_code,
                                          node_list_result.output)
        print('SUCCESS')
        print(f"Output : {node_list_result.output}")
        node_list = re.findall(node_pattern, node_list_result.output)
        print(f"Computed node list : {node_list}")
        print(f"Expected # of nodes : {num_nodes}")
        assert len(node_list) == num_nodes, \
            f"Test cluster has {len(node_list)} nodes, when it should have " \
            f"{num_nodes} node(s)."
        return node_list

    # vcd cse template list
    # retrieves template names to test cluster deployment against
    cmd = 'cse template list'
    print(f"\nRunning command [vcd {cmd}]...", end='')
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'template', 'list'],
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    print('SUCCESS')

    template_name = config['broker']['default_template_name']
    template_revision = config['broker']['default_template_revision']

    # tests for cluster operations
    print(f"\nTesting cluster operations for template: {template_name} at "
          f"revision: {template_revision}\n")
    # vcd cse cluster create testcluster -n NETWORK -N 1 -t TEMPLATE_NAME
    # -r TEMPLATE_REVISION
    cmd = f"cse cluster create {env.SYS_ADMIN_TEST_CLUSTER_NAME} -n " \
          f"{config['broker']['network']} -N 1 -t {template_name} " \
          f"-r {template_revision}"
    num_nodes += 1
    print(f"Running command [vcd {cmd}]...", end='')
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    assert env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME), \
        "Cluster doesn't exist when it should."
    print(f"SUCCESS")
    nodes = check_node_list()

    cmds = [
        f"cse cluster config {env.SYS_ADMIN_TEST_CLUSTER_NAME}",
        f"cse cluster info {env.SYS_ADMIN_TEST_CLUSTER_NAME}",
        f"cse cluster list",
        f"cse node info {env.SYS_ADMIN_TEST_CLUSTER_NAME} {nodes[0]}"
    ]
    for cmd in cmds:
        print(f"Running command [vcd {cmd}]...", end='')
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(),
                                       catch_exceptions=False)
        assert result.exit_code == 0, \
            testutils.format_command_info('vcd', cmd,
                                          result.exit_code,
                                          result.output)
        print('SUCCESS')

    # vcd cse node delete testcluster TESTNODE
    cmd = f"cse node delete {env.SYS_ADMIN_TEST_CLUSTER_NAME} {nodes[0]}"
    num_nodes -= 1
    print(f"Running command [vcd {cmd}]...", end='')
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    print('SUCCESS')
    check_node_list()

    # vcd cse node create testcluster -n NETWORK -t PHOTON
    cmd = f"cse node create {env.SYS_ADMIN_TEST_CLUSTER_NAME} -n " \
          f"{config['broker']['network']} -t {template_name} "\
          f"-r {template_revision}"
    num_nodes += 1
    print(f"Running command [vcd {cmd}]...", end='')
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(),
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    print('SUCCESS')
    check_node_list()

    # vcd cse cluster delete testcluster
    cmd = f"cse cluster delete {env.SYS_ADMIN_TEST_CLUSTER_NAME}"
    print(f"Running command [vcd {cmd}]...", end='')
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    assert not env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME), \
        "Cluster exists when it should not"
    num_nodes = 0
    print('SUCCESS')


@pytest.mark.parametrize('test_runner_username', ['sys_admin', 'org_admin',
                                                  'vapp_author'])
def test_0050_vcd_cse_system_toggle(config, test_runner_username,
                                    delete_test_clusters):
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
    # Batch cse commands together in a list and then execute them one by one
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func'
                                        ' test_user')
    cmd_list = [
        cmd_binder(cmd=env.SYS_ADMIN_LOGIN_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=f"cse system disable", exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=env.USER_LOGIN_CMD_MAP.get(test_runner_username),
                   exit_code=0, validate_output_func=None,
                   test_user=test_runner_username),
        cmd_binder(cmd=f"org use {config['broker']['org']}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster create {env.SYS_ADMIN_TEST_CLUSTER_NAME} "
                       f"-n {config['broker']['network']} -N 1", exit_code=2,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=env.SYS_ADMIN_LOGIN_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd="cse system enable", exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=f"cse cluster create {env.SYS_ADMIN_TEST_CLUSTER_NAME} "
                       f"-n {config['broker']['network']} -N 1 -c 1000 "
                       f"--disable-rollback", exit_code=2,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin')
    ]

    execute_commands(cmd_list)

    assert not env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME), \
        "Cluster exist when it should not."


def test_0060_vcd_share_catalog(config):
    """Enable catalog sharing to vDC's within the org.

    :param config:cse config file for vcd configuration
    """
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    cmd_list = [
        cmd_binder(cmd=env.SYS_ADMIN_LOGIN_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=f"org use {config['broker']['org']}", exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=f"catalog acl add {config['broker']['catalog']}"
                       f" \'org:{config['broker']['org']}:ReadOnly\'",
                   exit_code=0, validate_output_func=None,
                   test_user='sys_admin'),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin')
    ]
    execute_commands(cmd_list)


@pytest.mark.parametrize('test_runner_username', ['sys_admin', 'org_admin',
                                                  'vapp_author'])
def test_0070_vcd_cse_cluster_create(config, test_runner_username):
    """Test 'vcd cse cluster create ...' command for various cse users.

    Test cluster creation from different persona's- sys_admin, org_admin
    and vapp_author. Created clusters will remain in the system for further
    command tests - list, resize and delete.

    :param config: cse config file for vcd configuration
    :param test_runner_username: parameterized persona to run tests with
    different users
    """
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')

    cmd_list = [
        cmd_binder(cmd=env.USER_LOGIN_CMD_MAP.get(test_runner_username),
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),

        cmd_binder(cmd=f"org use {config['broker']['org']}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"vdc use {config['broker']['vdc']}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster create "
                       f"{env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(test_runner_username)}"  # noqa
                       f" -n {config['broker']['network']} -N 1", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]
    execute_commands(cmd_list)

    assert env.vapp_exists(env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.
                           get(test_runner_username)), \
        "Cluster should exist"


@pytest.mark.parametrize('test_runner_username', ['sys_admin', 'org_admin',
                                                  'vapp_author'])
def test_0080_vcd_cse_cluster_list(test_runner_username):
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')

    cmd_list = [
        cmd_binder(cmd=env.USER_LOGIN_CMD_MAP.get(test_runner_username),
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster list", exit_code=0,
                   validate_output_func=list_cluster_output_validator,
                   test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]

    execute_commands(cmd_list)


def test_0090_vcd_cse_cluster_delete(config):
    """Test 'vcd cse cluster delete ...' command for various cse users.

    Cluster delete operation on the above create clusters operations.
    Vapp Author can only delete cluster created by him, Org admin can
    delete any cluster in the org.

    :param config: cse config file for vcd configuration
    """
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')

    cmd_list = [
        cmd_binder(cmd=env.VAPP_AUTHOR_LOGIN_CMD,
                   exit_code=0,
                   validate_output_func=None, test_user=env.VAPP_AUTHOR_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(env.SYS_ADMIN_NAME)}",  # noqa
                   exit_code=2,
                   validate_output_func=None, test_user=env.VAPP_AUTHOR_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(env.ORG_ADMIN_NAME)}",  # noqa
                   exit_code=2,
                   validate_output_func=None, test_user=env.VAPP_AUTHOR_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(env.VAPP_AUTHOR_NAME)}",  # noqa
                   exit_code=0,
                   validate_output_func=None, test_user=env.VAPP_AUTHOR_NAME),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=env.VAPP_AUTHOR_NAME),
        cmd_binder(cmd=env.ORG_ADMIN_LOGIN_CMD,
                   exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME),
        cmd_binder(cmd=f"org use {config['broker']['org']}", exit_code=0,
                   validate_output_func=None, test_user='org_admin'),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(env.SYS_ADMIN_NAME)}",  # noqa
                   exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(env.ORG_ADMIN_NAME)}",  # noqa
                   exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME)
    ]

    execute_commands(cmd_list)

    for cluster_name in env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.values():
        assert not env.vapp_exists(
            env.USERNAME_TO_TEST_CLUSTER_NAME_MAP.get(cluster_name)), \
            "Cluster should exist"


def test_9999_vcd_cse_system_stop(vcd_sys_admin):
    """Test `vcd cse system stop -y`.

    This test shuts down CSE service, so '9999' ensures it runs last.
    """
    # must disable CSE before attempting to stop
    cmd = 'cse system disable'
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)

    cmd = 'cse system stop'
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                   catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
