# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
CSE client tests to test validity and functionality of `vcd cse` CLI commands.

Tests these following commands:
$ vcd cse version
$ vcd cse system info
$ vcd cse template list

$ vcd cse cluster create -n NETWORK -N 1 -t photon-v2 -c 1000
$ vcd cse cluster create -n NETWORK -N 1 -t photon-v2 -c 1000
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
- Clusters are deleted on test failure, unless 'teardown_clusters'=false in
    'base_config.yaml'.
- This test module typically takes ~20 minutes to finish per template.

TODO()
- tests/fixtures to test command accessibility for various
    users/roles (vcd_org_admin() fixture should be replaced with
    a minimum rights user fixture)
- test accessing cluster via kubectl
- test nfs functionality
- test pks functionality
- test that node rollback works correctly (node rollback is not implemented
    yet due to a vcd-side bug, where a partially powered-on VM cannot be force
    deleted)
- test `vcd cse system` commands
- test `vcd cse cluster config testcluster --save` option (currently does
    not work)
"""

import re
import subprocess
import time

import pytest
from vcd_cli.vcd import vcd

from container_service_extension.cse import cli
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
    for template in config['broker']['templates']:
        if not env.catalog_item_exists(template['catalog_item']):
            install_cmd.append('--update')
            break

    env.setup_active_config()
    result = env.CLI_RUNNER.invoke(cli, install_cmd,
                                   input='y',
                                   catch_exceptions=False)
    assert result.exit_code == 0

    # start cse server as subprocess
    cmd = f"cse run -c {env.ACTIVE_CONFIG_FILEPATH}"
    p = subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    time.sleep(10)  # server takes a little time to set itself up

    yield

    # terminate cse server subprocess
    p.terminate()


@pytest.fixture
def vcd_org_admin():
    """Fixture to ensure that we are logged in to vcd-cli as org admin.

    Usage: add the parameter 'vcd_org_admin' to the test function.

    vCD instance must have an org admin user in the specified org with
    username and password identical to those described in config['vcd'].
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    result = env.CLI_RUNNER.invoke(vcd,
                                   ['login',
                                    config['vcd']['host'],
                                    config['broker']['org'],
                                    config['vcd']['username'],
                                    '-iwp', config['vcd']['password']],
                                   catch_exceptions=False)
    assert result.exit_code == 0

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])
    assert result.exit_code == 0


@pytest.fixture
def delete_test_cluster():
    """Fixture to ensure that test cluster doesn't exist before or after tests.

    Usage: add the parameter 'delete_test_cluster' to the test function.

    Setup tasks:
    - Delete test cluster vApp

    Teardown tasks (only if config key 'teardown_clusters'=True):
    - Delete test cluster vApp
    """
    env.delete_vapp(env.TEST_CLUSTER_NAME)
    yield
    if env.TEARDOWN_CLUSTERS:
        env.delete_vapp(env.TEST_CLUSTER_NAME)


def test_0010_vcd_cse_version(vcd_org_admin):
    """Test vcd cse version command."""
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'version'],
                                   catch_exceptions=False)
    assert result.exit_code == 0


def test_0020_vcd_cse_system_info(vcd_org_admin):
    """Test vcd cse system info command."""
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'system', 'info'],
                                   catch_exceptions=False)
    assert result.exit_code == 0


def test_x_vcd_cse_system_enable():
    # TODO()
    pass


def test_x_vcd_cse_system_disable():
    # TODO()
    pass


def test_x_vcd_cse_system_stop():
    # TODO()
    pass


def test_0030_vcd_cse_cluster_create_rollback(config, vcd_org_admin,
                                              delete_test_cluster):
    """Test that --disable-rollback option works during cluster creation.

    commands:
    $ vcd cse cluster create -n NETWORK -N 1 -t photon-v2 -c 1000
    $ vcd cse cluster create -n NETWORK -N 1 -t photon-v2 -c 1000
        --disable-rollback
    """
    cmd = f"cse cluster create {env.TEST_CLUSTER_NAME} -n " \
          f"{config['broker']['network']} -N 1 -c 1000"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    time.sleep(10)  # wait for vApp to be deleted
    assert not env.vapp_exists(env.TEST_CLUSTER_NAME), \
        "Cluster exists when it should not."

    cmd += " --disable-rollback"
    result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    assert env.vapp_exists(env.TEST_CLUSTER_NAME), \
        "Cluster does not exist when it should."


def test_0040_vcd_cse_cluster_and_node_operations(config, vcd_org_admin,
                                                  delete_test_cluster):
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
        node_list_cmd = f"cse node list {env.TEST_CLUSTER_NAME}"
        node_list_result = env.CLI_RUNNER.invoke(vcd, node_list_cmd.split(),
                                                 catch_exceptions=False)
        assert node_list_result.exit_code == 0
        node_list = re.findall(node_pattern, node_list_result.output)
        assert len(node_list) == num_nodes, \
            f"Test cluster has {len(node_list)} nodes, when it should have " \
            f"{num_nodes} node(s)."
        return node_list

    # vcd cse template list
    # retrieves template names to test cluster deployment against
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'template', 'list'],
                                   catch_exceptions=False)
    assert result.exit_code == 0
    template_pattern = r'(True|False)\s*(\S*)'
    matches = re.findall(template_pattern, result.output)
    template_names = [match[1] for match in matches]
    if not env.TEST_ALL_TEMPLATES:
        template_names = [template_names[0]]

    # tests for cluster operations
    for template_name in template_names:
        print(f'\nTesting cluster operations for template: {template_name}\n')
        # vcd cse cluster create testcluster -n NETWORK -N 1 -t PHOTON
        cmd = f"cse cluster create {env.TEST_CLUSTER_NAME} -n " \
              f"{config['broker']['network']} -N 1 -t {template_name}"
        num_nodes += 1
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(),
                                       catch_exceptions=False)
        assert result.exit_code == 0
        assert env.vapp_exists(env.TEST_CLUSTER_NAME), \
            "Cluster doesn't exist when it should."
        nodes = check_node_list()
        print(f"Command [{cmd}] successful")

        # `cluster config`, `cluster info`, `cluster list`, `node info`
        # only need to run once
        has_run = False
        if not has_run:
            cmds = [
                f"cse cluster config {env.TEST_CLUSTER_NAME}",
                f"cse cluster info {env.TEST_CLUSTER_NAME}",
                f"cse cluster list",
                f"cse node info {env.TEST_CLUSTER_NAME} {nodes[0]}"
            ]
            for cmd in cmds:
                result = env.CLI_RUNNER.invoke(vcd, cmd.split(),
                                               catch_exceptions=False)
                assert result.exit_code == 0
            has_run = True

        # vcd cse node delete testcluster TESTNODE
        cmd = f"cse node delete {env.TEST_CLUSTER_NAME} {nodes[0]}"
        num_nodes -= 1
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                       catch_exceptions=False)
        assert result.exit_code == 0
        check_node_list()
        print(f"Command [{cmd}] successful")

        # vcd cse node create testcluster -n NETWORK -t PHOTON
        cmd = f"cse node create {env.TEST_CLUSTER_NAME} -n " \
              f"{config['broker']['network']} -t {template_name}"
        num_nodes += 1
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(),
                                       catch_exceptions=False)
        assert result.exit_code == 0
        check_node_list()
        print(f"Command [{cmd}] successful")

        # vcd cse cluster delete testcluster
        cmd = f"cse cluster delete {env.TEST_CLUSTER_NAME}"
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                       catch_exceptions=False)
        assert result.exit_code == 0
        assert not env.vapp_exists(env.TEST_CLUSTER_NAME), \
            "Cluster exists when it should not"
        num_nodes = 0
        print(f"Command [{cmd}] successful")
