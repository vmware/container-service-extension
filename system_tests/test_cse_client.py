import pytest

import container_service_extension.system_test_framework.environment as env
from container_service_extension.cse import cli


@pytest.fixture(scope='module', autouse=True)
def cse_server(config):
    """Fixture to ensure that CSE is installed before client tests.

    This function will execute before tests run in this module.

    Setup tasks:
    - install CSE if it is not already installed
    """
    installation_exists = True
    for template in config['broker']['template']:
        if not env.catalog_item_exists():
            installation_exists = False
            break

    if installation_exists and not env.is_cse_registered():
        installation_exists = False

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


def test_0010():
    pass
