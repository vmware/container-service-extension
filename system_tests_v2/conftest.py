# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
conftest.py is used by pytest to automatically find shared fixtures.

Fixtures defined here can be used without importing.
"""
import os

import pytest
import system_tests_v2.pytest_logger as pytest_logger

import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


def pytest_logger_config(logger_config):
    # adds two loggers, which will:
    # - log to pytest_logger at 'warn' level
    logger_config.add_loggers([pytest_logger.PYTEST_LOGGER_NAME],
                              stdout_level='warn')
    # default --loggers option is set to log pytest_logger at WARN level
    logger_config.set_log_option_default(pytest_logger.PYTEST_LOGGER_NAME)


def pytest_logger_logdirlink(config):
    return os.path.join(os.path.dirname(__file__), pytest_logger.PYTEST_LOG_FILE_NAME)  # noqa: E501


@pytest.fixture(scope='session', autouse=True)
def environment():
    """Fixture to setup and teardown the session environment.

    This fixture executes automatically for test session setup and teardown.
    Does not have any side effects to vCD.

    Setup tasks:
    - initialize variables (org/vdc href, client, mqtt settings)
    - create cluster admin and cluster author roles

    Teardown tasks:
    - logout client
    """
    env.init_rde_environment(logger=pytest_logger.PYTEST_LOGGER)
    yield
    env.cleanup_environment(logger=pytest_logger.PYTEST_LOGGER)


@pytest.fixture(scope='session', autouse=True)
def vcd_users():
    """Fixture to setup required users if they do not exist already.

    This fixture executes automatically for test session setup and teardown.
    User credentials are in 'system_test_framework/environment.py'

    Setup tasks:
    - create Cluster admin user if it doesn't exist
    - create Cluster author user if it doesn't exist
    """
    if env.SHOULD_INSTALL_PREREQUISITES:
        # org_admin -> cluster_admin
        # k8_author -> cluster_author
        env.create_user(env.CLUSTER_ADMIN_NAME,
                        env.CLUSTER_ADMIN_PASSWORD,
                        env.CLUSTER_ADMIN_ROLE_NAME,
                        logger=pytest_logger.PYTEST_LOGGER)
        env.create_user(env.CLUSTER_AUTHOR_NAME,
                        env.CLUSTER_AUTHOR_PASSWORD,
                        env.CLUSTER_AUTHOR_ROLE_NAME,
                        logger=pytest_logger.PYTEST_LOGGER)


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
    return config['test']


@pytest.fixture
def publish_native_right_bundle():
    """Publish CSE native right bundle to deployment org.

    Usage: add parameter 'publish_native_right_bundle' to the test function.
        This fixture will be executed after the test function completes

    Tasks done:
    - publish cse native right bundle to deployment org (org specified in
        'test' section of base_config.yaml)
    - assign appropriate rights to roles in test org
    """
    yield
    env.publish_right_bundle_to_deployment_org(
        logger=pytest_logger.PYTEST_LOGGER)
    env.assign_native_rights(env.CLUSTER_ADMIN_ROLE_NAME,
                             ["cse:nativeCluster: Full Access",
                              "cse:nativeCluster: Modify",
                              "cse:nativeCluster: View"],
                             logger=pytest_logger.PYTEST_LOGGER)
    env.assign_native_rights(env.CLUSTER_AUTHOR_ROLE_NAME,
                             ["cse:nativeCluster: Modify",
                              "cse:nativeCluster: View"],
                             logger=pytest_logger.PYTEST_LOGGER)
