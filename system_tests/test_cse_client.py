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

from container_service_extension.server.cli.server_cli import cli
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils
from container_service_extension.system_test_framework.utils import \
    execute_commands
from container_service_extension.system_test_framework.utils import \
    list_cluster_output_validator


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
    env.setup_active_config()
    if env.is_cse_registered():
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

    # Create missing templates
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
    cmd = f"login {config['vcd']['host']} {env.TEST_ORG} " \
        f"{env.ORG_ADMIN_NAME} -iwp {env.ORG_ADMIN_PASSWORD} " \
        f"-V {config['vcd']['api_version']}"
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

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])


@pytest.fixture
def vcd_k8_author():
    """Fixture to ensure that we are logged in to vcd-cli as vapp author.

    Usage: add the parameter 'vcd_k8_author' to the test function.

    User will have the credentials specified in
    'system_test_framework/environment.py'

    Do not use this fixture with the other vcd_role fixtures, as only one
    user can be logged in at a time.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} {env.TEST_ORG} " \
        f"{env.K8_AUTHOR_NAME} -iwp {env.K8_AUTHOR_PASSWORD} " \
        f"-V {config['vcd']['api_version']}"
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
    env.delete_vapp(env.SYS_ADMIN_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF)  # noqa
    env.delete_vapp(env.ORG_ADMIN_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF)  # noqa
    env.delete_vapp(env.K8_AUTHOR_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF)  # noqa

    yield

    if env.TEARDOWN_CLUSTERS:
        env.delete_vapp(env.SYS_ADMIN_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF)  # noqa
        env.delete_vapp(env.ORG_ADMIN_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF)  # noqa
        env.delete_vapp(env.K8_AUTHOR_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF)  # noqa


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
          f"{env.TEST_NETWORK} -N 1 -c 1000"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # TODO: Make cluster rollback delete call blocking
    time.sleep(env.WAIT_INTERVAL * 2)  # wait for vApp to be deleted
    assert not env.vapp_exists(
        env.SYS_ADMIN_TEST_CLUSTER_NAME, vdc_href=env.TEST_VDC_HREF), \
        "Cluster exists when it should not."

    cmd += " --disable-rollback"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0,\
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    assert env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME,
                           vdc_href=env.TEST_VDC_HREF), \
        "Cluster does not exist when it should."


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
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
        cmd_binder(cmd="cse system disable", exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0, validate_output_func=None,
                   test_user=test_runner_username),
        cmd_binder(cmd=f"org use {env.TEST_ORG}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster create {env.SYS_ADMIN_TEST_CLUSTER_NAME} "
                       f"-n {env.TEST_NETWORK} -N 1", exit_code=2,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=env.SYS_ADMIN_LOGIN_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd="cse system enable", exit_code=0,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=f"cse cluster create {env.SYS_ADMIN_TEST_CLUSTER_NAME} "
                       f"-n {env.TEST_NETWORK} -N 1 -c 1000 "
                       f"--disable-rollback", exit_code=2,
                   validate_output_func=None, test_user='sys_admin'),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user='sys_admin')
    ]

    execute_commands(cmd_list)

    assert not env.vapp_exists(env.SYS_ADMIN_TEST_CLUSTER_NAME,
                               vdc_href=env.TEST_VDC_HREF), \
        "Cluster exists when it should not."


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
def test_0070_vcd_cse_cluster_create(config, test_runner_username):
    """Test 'vcd cse cluster create ...' command for various cse users.

    Test cluster creation from different persona's- sys_admin, org_admin
    and k8_author. Created clusters will remain in the system for further
    command tests - list, resize and delete.

    :param config: cse config file for vcd configuration
    :param test_runner_username: parameterized persona to run tests with
    different users
    """
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    print(f"Running cluster create operation for {test_runner_username}")
    cmd_list = [
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),

        cmd_binder(cmd=f"org use {env.TEST_ORG}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"vdc use {env.TEST_VDC}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster create "
                       f"{env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}"
                       f" -n {env.TEST_NETWORK} -N 0 ", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]
    execute_commands(cmd_list)

    assert env.vapp_exists(
        env.USERNAME_TO_CLUSTER_NAME[test_runner_username],
        vdc_href=env.TEST_VDC_HREF), \
        f"Cluster {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} " \
        f"should exist"
    print(f"Successfully created cluster {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} "  # noqa
          f"for {test_runner_username}")


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
def test_0080_vcd_cse_cluster_list(test_runner_username):
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    print(f"Running cluster list operation for {test_runner_username}")
    cmd_list = [
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd="cse cluster list", exit_code=0,
                   validate_output_func=list_cluster_output_validator,
                   test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]

    execute_commands(cmd_list)
    print(f"Successfully listed cluster for {test_runner_username}.")


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
def test_0090_vcd_cse_cluster_info(test_runner_username):
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    print(f"Running cluster info operation for {test_runner_username} on "
          f"{env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}")
    cmd_list = [
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",  # noqa
                   exit_code=0, validate_output_func=None,
                   test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]

    execute_commands(cmd_list)
    print(f"Successful cluster info on {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}.")  # noqa


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
def test_0100_vcd_cse_cluster_config(test_runner_username):
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    print(f"Running cluster config operation for {test_runner_username} on "
          f"{env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}")
    cmd_list = [
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster config {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",  # noqa
                   exit_code=0, validate_output_func=None,
                   test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]

    execute_commands(cmd_list)
    print(f"Successful cluster config on {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}.")  # noqa


def generate_validate_node_count_func(expected_nodes):
    """Generate validator function to verify the number of nodes in the cluster.

    :param expected_nodes: Expected number of nodes in the cluster

    :return validator: function(output, test_user)
    """
    node_pattern = r'(node-\S+)'

    def validator(output, test_runner_username):
        cmd_binder = collections.namedtuple('UserCmdBinder',
                                            'cmd exit_code validate_output_func ' # noqa: E501
                                            'test_user')
        print(f"Running cluster info operation for {test_runner_username}")
        cmd_list = [
            cmd_binder(cmd=f"cse cluster info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",   # noqa
                       exit_code=0,
                       validate_output_func=None,
                       test_user=test_runner_username)
        ]
        cmd_results = execute_commands(cmd_list)

        return len(re.findall(node_pattern, cmd_results[0].output)) == expected_nodes # noqa

    return validator


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
def test_0110_vcd_cse_cluster_resize(test_runner_username, config):
    """Test 'vcd cse cluster resize ...' commands."""
    node_pattern = r'(node-\S+)'
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')

    print(f"Running cluster info operation for {test_runner_username}")
    cmd_list = [
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"org use {env.TEST_ORG}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"vdc use {env.TEST_VDC}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",   # noqa
                   exit_code=0,
                   validate_output_func=None,
                   test_user=test_runner_username)
    ]
    cmd_results = execute_commands(cmd_list)

    num_nodes = len(re.findall(node_pattern, cmd_results[-1].output))

    print(f"Running cluster resize operation for {test_runner_username}")

    cmd_list = [
        cmd_binder(cmd=f"cse cluster resize -N {num_nodes+1} -n {env.TEST_NETWORK}"  # noqa
                       f" {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}", # noqa: E501
                   exit_code=0, validate_output_func=generate_validate_node_count_func(num_nodes+1), # noqa
                   test_user=test_runner_username),
        cmd_binder(cmd=f"cse cluster resize -N 0 -n {env.TEST_NETWORK}" # noqa
                       f" {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}", # noqa: E501
                   exit_code=0, validate_output_func=generate_validate_node_count_func(0), # noqa
                   test_user=test_runner_username)
    ]
    execute_commands(cmd_list)
    print(f"Successful cluster resize on {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}.") # noqa


@pytest.mark.parametrize('test_runner_username', [env.SYS_ADMIN_NAME,
                                                  env.ORG_ADMIN_NAME,
                                                  env.K8_AUTHOR_NAME])
def test_0120_vcd_cse_node_operation(test_runner_username, config):
    """Test 'vcd cse node create/list/info/delete ...' commands.

    Test node creation from different persona's- sys_admin, org_admin
    and k8_author. Created nodes will remain in the system for further
    command tests - list and delete.

    :param config: cse config file for vcd configuration
    :param test_runner_username: parameterized persona to run tests with
    different users
    """
    node_pattern = r'(node-\S+)'
    num_nodes = 0 # last resize scaled the cluster down to 0 nodes
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    print(f"Running node add operation for {test_runner_username}")

    cmd_list = [
        cmd_binder(cmd=env.USERNAME_TO_LOGIN_CMD[test_runner_username],
                   exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"org use {env.TEST_ORG}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"vdc use {env.TEST_VDC}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username),
        cmd_binder(cmd=f"cse node create {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}"  # noqa
                       f" -n {env.TEST_NETWORK}", exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]
    execute_commands(cmd_list)
    # Increase Node count by 1
    num_nodes += 1
    print(f"Successfully added node to cluster "
          f"{env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}")

    print(f"Running node list operation for {test_runner_username}")
    cmd_list = [
        cmd_binder(cmd=f"cse node list {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",   # noqa
                   exit_code=0,
                   validate_output_func=None,
                   test_user=test_runner_username)
    ]
    cmd_results = execute_commands(cmd_list)
    assert len(re.findall(node_pattern, cmd_results[0].output)) == num_nodes
    print(f"Successful node list on cluster {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}.")  # noqa

    # Get cse node name to be used for info and delete
    node_names = list(re.findall(node_pattern, cmd_results[0].output))
    node_name = node_names[0]

    print(f"Running node info operation on cluster "
          f"{env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} for"
          f" node {node_name}")
    cmd_list = [
        cmd_binder(cmd=f"cse node info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} "   # noqa
                       f"{node_name}",
                   exit_code=0, validate_output_func=None,
                   test_user=test_runner_username)
    ]
    execute_commands(cmd_list)
    print(f"Successful node info on {node_name}.")  # noqa

    print(f"Running node delete operation for {test_runner_username} on "
          f"cluster {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} "
          f"to delete node {node_name}")
    cmd_list = [
        cmd_binder(cmd=f"cse node delete {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} "   # noqa
                       f"{node_name}",
                   exit_code=0, validate_output_func=None,
                   test_user=test_runner_username),
    ]
    execute_commands(cmd_list)
    # Decrease Node count by 1
    num_nodes -= 1
    print(f"Successfully deleted node {node_name} from "
          f"{env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}")

    cmd_list = [
        cmd_binder(cmd=f"cse node list {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]} ",   # noqa
                   exit_code=0,
                   validate_output_func=None,
                   test_user=test_runner_username),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=test_runner_username)
    ]
    cmd_results = execute_commands(cmd_list)
    assert len(re.findall(node_pattern, cmd_results[0].output)) == num_nodes
    print(f"Successful node list on cluster {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}.")  # noqa


def test_0130_vcd_cse_cluster_delete(config):
    """Test 'vcd cse cluster delete ...' command for various cse users.

    Cluster delete operation on the above create clusters operations-
    K8 Author can only delete self created clusters.
    Org admin can delete all cluster in the organization.

    :param config: cse config file for vcd configuration
    """
    cmd_binder = collections.namedtuple('UserCmdBinder',
                                        'cmd exit_code validate_output_func '
                                        'test_user')
    print("Running cluster delete operations")
    cmd_list = [
        cmd_binder(cmd=env.K8_AUTHOR_LOGIN_CMD,
                   exit_code=0,
                   validate_output_func=None, test_user=env.K8_AUTHOR_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_CLUSTER_NAME[env.SYS_ADMIN_NAME]}",  # noqa
                   exit_code=2,
                   validate_output_func=None, test_user=env.K8_AUTHOR_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_CLUSTER_NAME[env.ORG_ADMIN_NAME]}",  # noqa
                   exit_code=2,
                   validate_output_func=None, test_user=env.K8_AUTHOR_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_CLUSTER_NAME[env.K8_AUTHOR_NAME]}",  # noqa
                   exit_code=0,
                   validate_output_func=None, test_user=env.K8_AUTHOR_NAME),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=env.K8_AUTHOR_NAME),
        cmd_binder(cmd=env.ORG_ADMIN_LOGIN_CMD,
                   exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME),
        cmd_binder(cmd=f"org use {env.TEST_ORG}", exit_code=0,
                   validate_output_func=None, test_user='org_admin'),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_CLUSTER_NAME[env.SYS_ADMIN_NAME]}",  # noqa
                   exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME),
        cmd_binder(cmd=f"cse cluster delete "
                       f"{env.USERNAME_TO_CLUSTER_NAME[env.ORG_ADMIN_NAME]}",  # noqa
                   exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME),
        cmd_binder(cmd=env.USER_LOGOUT_CMD, exit_code=0,
                   validate_output_func=None, test_user=env.ORG_ADMIN_NAME)
    ]

    execute_commands(cmd_list)

    for cluster_name in env.USERNAME_TO_CLUSTER_NAME.values():
        assert not env.vapp_exists(cluster_name, vdc_href=env.TEST_VDC_HREF), \
            f"Cluster {cluster_name} exists when it should not"
    print("Successfully deleted clusters.")


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
