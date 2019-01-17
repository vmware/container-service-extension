import pytest

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


@pytest.fixture(scope='module', autouse=True)
def vcd_login_sys_admin():
    """Fixture to ensure that we are logged in to vcd-cli.

    This function will execute once for this module.

    Setup tasks:
    - log into vcd using vcd-cli

    Teardown tasks:
    - log out of vcd
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


def test_0010():
    pass
