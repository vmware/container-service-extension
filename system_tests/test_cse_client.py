# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
CSE client tests.

TODO() include tests/fixtures to test command accessibility for various
users/roles, test accessing cluster via kubectl, test nfs functionality,
test pks functionality.

NOTES:
- These tests will install CSE on vCD if CSE is not installed already.
- Edit 'base_config.yaml' for your own vCD instance.
- Clusters are deleted on test failure, unless 'teardown_clusters'=false in
    'base_config.yaml'.
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
import subprocess
import time

import pytest
from vcd_cli.vcd import vcd

from container_service_extension.cse import cli
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils
import container_service_extension.utils as utils


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
def vcd_sys_admin():
    """Fixture to ensure that we are logged in to vcd-cli as sys admin.

    Usage: add the parameter 'vcd_sys_admin' to the test function. Do not use
    both `vcd_sys_admin` and `vcd_org_admin` fixtures in the same function.
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    result = env.CLI_RUNNER.invoke(vcd,
                                   ['login',
                                    config['vcd']['host'],
                                    utils.SYSTEM_ORG_NAME,
                                    config['vcd']['username'],
                                    '-iwp', config['vcd']['password']],
                                   catch_exceptions=False)
    assert result.exit_code == 0

    yield

    result = env.CLI_RUNNER.invoke(vcd, ['logout'])
    assert result.exit_code == 0


@pytest.fixture
def vcd_org_admin():
    """Fixture to ensure that we are logged in to vcd-cli as org admin.

    Usage: add the parameter 'vcd_org_admin' to the test function. Do not use
    both `vcd_sys_admin` and `vcd_org_admin` fixtures in the same function.

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


def test_vcd_cse_version(vcd_org_admin):
    """Test vcd cse version command."""
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'version'],
                                   catch_exceptions=False)
    assert result.exit_code == 0


def test_vcd_cse_system_info(vcd_org_admin):
    """Test vcd cse system info command."""
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'system', 'info'],
                                   catch_exceptions=False)
    assert result.exit_code == 0


def test_vcd_cse_template_list(vcd_org_admin):
    """Test vcd cse template list command."""
    result = env.CLI_RUNNER.invoke(vcd, ['cse', 'template', 'list'],
                                   catch_exceptions=False)
    assert result.exit_code == 0
