# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

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

    This fixture executes automatically for test session setup and teardown.
    Does not have any side effects to vCD.

    Setup tasks:
    - initialize variables (org/vdc href, client, amqp settings)
    - delete directory 'system_tests/scripts' (if it exists)

    Teardown tasks:
    - logout client
    """
    env.init_environment()
    yield
    env.cleanup_environment()


@pytest.fixture(scope='session', autouse=True)
def vcd_users():
    """Fixture to setup required users if they do not exist already.

    This fixture executes automatically for test session setup and teardown.
    User credentials are in 'system_test_framework/environment.py'

    Setup tasks:
    - create Organization Administrator if it doesn't exist
    - create vApp Author if it doesn't exist
    """
    env.create_user(env.ORG_ADMIN_NAME, env.ORG_ADMIN_PASSWORD,
                    env.ORG_ADMIN_ROLE_NAME)
    env.create_user(env.K8_AUTHOR_NAME, env.K8_AUTHOR_PASSWORD,
                    env.K8_AUTHOR_ROLE_NAME)
    yield


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


@pytest.fixture
def test_config():
    """Fixture to provide 'test' section of test config to individual tests."""
    config = testutils.yaml_to_dict(env.BASE_CONFIG_FILEPATH)
    yield config['test']
