# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pytest
import subprocess
import time

import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils
import container_service_extension.utils as utils
from container_service_extension.cse import cli
from vcd_cli.vcd import vcd


@pytest.fixture(scope='module', autouse=True)
def cse_server():
    """Fixture to ensure that CSE is installed before client tests.

    This function will execute once for this module.

    Setup tasks:
    - install CSE if it is not already installed
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    installation_exists = True
    for template in config['broker']['templates']:
        if not env.catalog_item_exists(template['catalog_item']):
            installation_exists = False
            break

    env.setup_active_config()
    installation_exists = installation_exists and env.is_cse_registered()
    if not installation_exists:
        result = env.CLI_RUNNER.invoke(cli,
                                       ['install',
                                        '--config', env.ACTIVE_CONFIG_FILEPATH,
                                        '--ssh-key', env.SSH_KEY_FILEPATH,
                                        '--update',
                                        '--no-capture'],
                                       input='y\ny',
                                       catch_exceptions=False)
        assert result.exit_code == 0

    # start cse server as subprocess
    cmd = f"cse run -c {env.ACTIVE_CONFIG_FILEPATH}"
    p = subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    time.sleep(10)

    yield

    # terminate cse server subprocess
    p.terminate()


@pytest.fixture
def vcd_sys_admin():
    """Fixture to ensure that we are logged in to vcd-cli as sys admin.

    Usage: add the parameter 'vcd_sys_admin' to the test function.
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


def test_0010():
    pass
