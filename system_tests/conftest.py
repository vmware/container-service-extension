"""
conftest.py is used by pytest to automatically find shared fixtures.
Fixtures defined here can be used without importing.
"""
import pytest

import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


@pytest.fixture(scope='session', autouse=True)
def environment():
    """Fixture to setup and teardown the session environment.

    ALWAYS runs for each test session (don't invoke this fixture)

    Setup tasks:
    - initialize variables (org/vdc href, client, amqp settings)
    - delete ova files, templates, temp vapps, clusters
    - unregister cse from vcd
    - reset vcd amqp settings

    Teardown tasks:
    - delete ova files, templates, temp vapps, clusters
    - unregister cse from vcd
    - reset vcd amqp settings
    - logout client
    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    env.init_environment()

    dev_mode_aware = False
    try:
        dev_mode_aware = config['test']['developer_mode_aware']
    except KeyError:
        pass

    yield

    if not dev_mode_aware:
        env.delete_cse_entities(config)

    env.cleanup_environment()


@pytest.fixture
def config():
    """Fixture to setup and teardown an active config file.

    Usage: add the parameter 'config' to the test function. This 'config'
        parameter is the dict representation of the config file, and can be
        used in the test function.

    Tasks:
    - create config dict from env.BASE_CONFIG_FILEPATH
    - create active config file at env.ACTIVE_CONFIG_FILEPATH
    - adjust active config file security

    yields config dict
    """
    config = env.setup_active_config()
    yield config
    env.teardown_active_config()


@pytest.fixture(scope='module')
def config_module():
    """Same as 'function' scoped fixture 'config', but 'module' scope is
    required to use this fixture in 'module' scoped fixtures.
    """
    config = env.setup_active_config()
    yield config
    env.teardown_active_config()


@pytest.fixture
def test_config():
    """Fixture to provide 'test' section of test config to individual tests.

    """
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    yield config['test']
