# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
from pathlib import Path
from sys import exec_prefix
from typing import List

from click.testing import CliRunner
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials, ResourceType
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.role import Role
from pyvcloud.vcd.vdc import VDC
from requests.auth import HTTPDigestAuth
from requests.models import HTTPError
from system_tests_v2.pytest_logger import PYTEST_LOGGER
from vcd_cli.vcd import vcd

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.utils.core_utils import get_max_api_version  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as pyvcloud_utils  # noqa: E501
import container_service_extension.exception.exceptions as cse_exceptions
from container_service_extension.installer.right_bundle_manager import RightBundleManager  # noqa: E501
from container_service_extension.installer.templates.remote_template_manager import RemoteTemplateManager  # noqa: E501
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER, SERVER_CLOUDAPI_WIRE_LOGGER  # noqa: E501
from container_service_extension.mqi.mqtt_extension_manager import \
    MQTTExtensionManager
import container_service_extension.rde.constants as rde_constants
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.schema_service as def_schema_svc
import container_service_extension.rde.utils as rde_utils
from container_service_extension.server.compute_policy_manager import ComputePolicyManager  # noqa: E501
import container_service_extension.system_test_framework.utils as testutils


"""
This module manages environment state during CSE system tests.
These variables persist through all test cases and do not change.

Module usage example:
```
import container_service_extension.system_test_framework.environment as env

env.init_environment()
# do something with env.CLIENT
```

NOTE: Imports using 'from environment import CLIENT' imports the variable to
the local module namespace, so calling 'init_environment' will change
environment.CLIENT but will not change the CLIENT that was imported.
"""
BASE_CONFIG_FILEPATH = 'base_config.yaml'
ACTIVE_CONFIG_FILEPATH = 'cse_test_config.yaml'
TEMPLATE_DEFINITIONS = None
TEMPLATE_COOKBOOK_VERSION = None

SCRIPTS_DIR = 'scripts'

SSH_KEY_FILEPATH = str(Path.home() / '.ssh' / 'id_rsa.pub')
CLI_RUNNER = CliRunner()
SYS_ADMIN_TEST_CLUSTER_NAME = 'testclustersystem'
CLUSTER_ADMIN_TEST_CLUSTER_NAME = 'testclusteradmin'
CLUSTER_AUTHOR_TEST_CLUSTER_NAME = 'testclusterauthor'

# TODO remove legacy test clusters after removing legacy mode
ORG_ADMIN_TEST_CLUSTER_NAME = 'testclusteradmin'
K8_AUTHOR_TEST_CLUSTER_NAME = 'testclusterk8'

# required user info
SYS_ADMIN_NAME = 'sys_admin'
CLUSTER_ADMIN_NAME = 'cluster_admin'
CLUSTER_ADMIN_PASSWORD = 'password'
CLUSTER_ADMIN_ROLE_NAME = 'cluster_admin_role'
CLUSTER_AUTHOR_NAME = 'cluster_author'
CLUSTER_AUTHOR_PASSWORD = 'password'
CLUSTER_AUTHOR_ROLE_NAME = 'cluster_author_role'
# TODO remove legacy users after removing legacy mode
ORG_ADMIN_NAME = 'org_admin'
ORG_ADMIN_PASSWORD = 'password'  # nosec: test environment
ORG_ADMIN_ROLE_NAME = 'Organization Administrator'
VAPP_AUTHOR_ROLE_NAME = 'vApp Author'
K8_AUTHOR_NAME = 'k8_author'
K8_AUTHOR_PASSWORD = 'password'  # nosec: test environment
K8_AUTHOR_ROLE_NAME = 'k8 Author'

VCD_API_VERSION_TO_USE = None

# config file 'test' section flags
TEARDOWN_INSTALLATION = None
TEARDOWN_CLUSTERS = None
TEST_ALL_TEMPLATES = None
TEST_ORG = None
TEST_VDC = None
TEST_NETWORK = None
TEST_ORG_HREF = None
TEST_VDC_HREF = None

# Persona login cmd
SYS_ADMIN_LOGIN_CMD = None
CLUSTER_ADMIN_LOGIN_CMD = None
CLUSTER_AUTHOR_LOGIN_CMD = None
# TODO remove legacy login command after removing legacy mode
ORG_ADMIN_LOGIN_CMD = None
K8_AUTHOR_LOGIN_CMD = None
USER_LOGOUT_CMD = "logout"
USERNAME_TO_LOGIN_CMD = {}
USERNAME_TO_CLUSTER_NAME = {}

AMQP_USERNAME = None
AMQP_PASSWORD = None
CLIENT = None
ORG_HREF = None
VDC_HREF = None
CATALOG_NAME = None

WAIT_INTERVAL = 30
DUPLICATE_NAME = "DUPLICATE_NAME"
VIEW_PUBLISHED_CATALOG_RIGHT = 'Catalog: View Published Catalogs'

VCD_SITE = None

# Location at which the cluster apply spec will be generated and used
APPLY_SPEC_PATH = 'cluster_apply_specification.yaml'

SHOULD_INSTALL_PREREQUISITES = True
IS_CSE_SERVER_RUNNING = False

SIZING_CLASS_NAME = 'sc1'
SIZING_CLASS_DESCRIPTION = 'sizing class for cse testing'
TEST_TEMPLATES_PRESENT = False


def _init_test_vars(config, logger=NULL_LOGGER):
    """Initialize all the environment variables that are used for test.

    :param dict config:
    """
    global TEMPLATE_DEFINITIONS, TEARDOWN_INSTALLATION, TEARDOWN_CLUSTERS, \
        TEST_ALL_TEMPLATES, TEST_ORG, TEST_VDC, TEST_NETWORK, \
        USERNAME_TO_CLUSTER_NAME, SHOULD_INSTALL_PREREQUISITES, \
        IS_CSE_SERVER_RUNNING
    USERNAME_TO_CLUSTER_NAME = {
        SYS_ADMIN_NAME: SYS_ADMIN_TEST_CLUSTER_NAME,
        CLUSTER_ADMIN_NAME: ORG_ADMIN_TEST_CLUSTER_NAME,
        CLUSTER_AUTHOR_NAME: K8_AUTHOR_TEST_CLUSTER_NAME
    }
    test_config = config['test']
    if test_config is not None:
        TEARDOWN_INSTALLATION = test_config.get('teardown_installation', True)
        TEARDOWN_CLUSTERS = test_config.get('teardown_clusters', True)
        TEST_ALL_TEMPLATES = test_config.get('test_all_templates', False)
        TEST_ORG = test_config.get('org', 'test-org')
        TEST_VDC = test_config.get('vdc', 'test-vdc')
        TEST_NETWORK = test_config.get('network', 'test-network')
        rtm = RemoteTemplateManager(
            config['broker']['remote_template_cookbook_url'],
            legacy_mode=config['service']['legacy_mode'])
        template_cookbook = rtm.get_filtered_remote_template_cookbook()
        TEMPLATE_DEFINITIONS = template_cookbook['templates']
        if not TEST_ALL_TEMPLATES:
            specified_templates_str = test_config.get('test_templates', "")
            specified_templates = specified_templates_str.split(",")
            specified_templates_def = []
            for template in specified_templates:
                tokens = template.split(":")
                # ToDo: log missing/bad specified templates
                if len(tokens) == 2:
                    template_name = tokens[0]
                    template_revision = tokens[1]
                    for template_def in TEMPLATE_DEFINITIONS:
                        if (template_name, int(template_revision)) == (template_def['name'], int(template_def['revision'])):  # noqa: E501
                            specified_templates_def.append(template_def)
                            break
            TEMPLATE_DEFINITIONS = specified_templates_def
    SHOULD_INSTALL_PREREQUISITES = \
        test_config.get('should_install_prerequisites', True)
    IS_CSE_SERVER_RUNNING = test_config.get('is_cse_server_running', False)


_init_test_vars(testutils.yaml_to_dict(BASE_CONFIG_FILEPATH))


def init_rde_environment(config_filepath=BASE_CONFIG_FILEPATH, logger=NULL_LOGGER):  # noqa: E501
    """Set up module variables according to config dict.

    :param str config_filepath:
    :param logging.Logger logger:
    """
    global CLIENT, ORG_HREF, VDC_HREF, \
        CATALOG_NAME, TEARDOWN_INSTALLATION, TEARDOWN_CLUSTERS, \
        TEMPLATE_DEFINITIONS, TEST_ALL_TEMPLATES, SYS_ADMIN_LOGIN_CMD, \
        CLUSTER_ADMIN_LOGIN_CMD, CLUSTER_AUTHOR_LOGIN_CMD, \
        USERNAME_TO_LOGIN_CMD, USERNAME_TO_CLUSTER_NAME, TEST_ORG_HREF, \
        TEST_VDC_HREF, VCD_API_VERSION_TO_USE, VCD_SITE

    logger.debug("Setting RDE environement")
    config = testutils.yaml_to_dict(config_filepath)
    logger.debug(f"Config file used: {config}")

    # download all remote template scripts
    rtm = RemoteTemplateManager(
        config['broker']['remote_template_cookbook_url'],
        legacy_mode=config['service']['legacy_mode'])
    template_cookbook = rtm.get_filtered_remote_template_cookbook()
    TEMPLATE_DEFINITIONS = template_cookbook['templates']
    rtm.download_all_template_scripts(force_overwrite=True)

    sysadmin_client = Client(
        config['vcd']['host'],
        verify_ssl_certs=config['vcd']['verify'])
    sysadmin_client.set_credentials(BasicLoginCredentials(
        config['vcd']['username'],
        shared_constants.SYSTEM_ORG_NAME,
        config['vcd']['password']))

    vcd_supported_api_versions = \
        set(sysadmin_client.get_supported_versions_list())
    cse_supported_api_versions = set(shared_constants.SUPPORTED_VCD_API_VERSIONS)  # noqa: E501
    common_supported_api_versions = \
        list(cse_supported_api_versions.intersection(vcd_supported_api_versions))  # noqa: E501
    common_supported_api_versions.sort()
    max_api_version = get_max_api_version(common_supported_api_versions)
    CLIENT = Client(config['vcd']['host'],
                    api_version=max_api_version,
                    verify_ssl_certs=config['vcd']['verify'])
    credentials = BasicLoginCredentials(config['vcd']['username'],
                                        shared_constants.SYSTEM_ORG_NAME,
                                        config['vcd']['password'])
    CLIENT.set_credentials(credentials)
    VCD_API_VERSION_TO_USE = max_api_version
    logger.debug(f"Using VCD api version: {VCD_API_VERSION_TO_USE}")

    CATALOG_NAME = config['broker']['catalog']
    VCD_SITE = f"https://{config['vcd']['host']}"

    SYS_ADMIN_LOGIN_CMD = f"login {config['vcd']['host']} system " \
                          f"{config['vcd']['username']} " \
                          f"-iwp {config['vcd']['password']} " \
                          f"-V {VCD_API_VERSION_TO_USE}"
    CLUSTER_ADMIN_LOGIN_CMD = f"login {config['vcd']['host']} " \
                              f"{TEST_ORG}" \
                              f" {CLUSTER_ADMIN_NAME} " \
                              f"-iwp {CLUSTER_ADMIN_PASSWORD} " \
                              f"-V {VCD_API_VERSION_TO_USE}"
    CLUSTER_AUTHOR_LOGIN_CMD = f"login {config['vcd']['host']} " \
                               f"{TEST_ORG}" \
                               f" {CLUSTER_AUTHOR_NAME} " \
                               f"-iwp {CLUSTER_AUTHOR_PASSWORD} " \
                               f"-V {VCD_API_VERSION_TO_USE}"

    USERNAME_TO_LOGIN_CMD = {
        SYS_ADMIN_NAME: SYS_ADMIN_LOGIN_CMD,
        CLUSTER_ADMIN_NAME: CLUSTER_ADMIN_LOGIN_CMD,
        CLUSTER_AUTHOR_NAME: CLUSTER_AUTHOR_LOGIN_CMD
    }

    # hrefs for Org and VDC that hosts the catalog
    org = pyvcloud_utils.get_org(CLIENT, org_name=config['broker']['org'])
    vdc = pyvcloud_utils.get_vdc(CLIENT, vdc_name=config['broker']['vdc'],
                                 org=org)
    ORG_HREF = org.href
    VDC_HREF = vdc.href

    logger.debug(f"Using template org {org.get_name()} with href {ORG_HREF}")
    logger.debug(f"Using template vdc {vdc.name} with href {VDC_HREF}")

    # hrefs for Org and VDC that tests cluster operations
    test_org = pyvcloud_utils.get_org(CLIENT, org_name=TEST_ORG)
    test_vdc = pyvcloud_utils.get_vdc(CLIENT, vdc_name=TEST_VDC, org=test_org)
    TEST_ORG_HREF = test_org.href
    TEST_VDC_HREF = test_vdc.href

    logger.debug(f"Using test org {test_org.get_name()} "
                 f"with href {TEST_ORG_HREF}")
    logger.debug(f"Using test vdc {test_vdc.name} with href {TEST_VDC_HREF}")
    if SHOULD_INSTALL_PREREQUISITES:
        create_cluster_admin_role(config['vcd'], logger=logger)
        create_cluster_author_role(config['vcd'], logger=logger)

        # create and publish sizing class sc1 to TEST_VDC
        cpm = ComputePolicyManager(sysadmin_client=sysadmin_client, log_wire=True)
        created_policy = None
        try:
             created_policy = cpm.add_vdc_compute_policy(
                SIZING_CLASS_NAME,
                description=SIZING_CLASS_DESCRIPTION,
                cpu_count=2,
                memory_mb=2048)
        except HTTPError as err:
            if 'already exists' in err.response.text:
                logger.debug(f"Compute policy {SIZING_CLASS_NAME} already exists")
                created_policy = cpm.get_vdc_compute_policy(SIZING_CLASS_NAME)
            else:
                logger.error(f"Request to create sizing policy {SIZING_CLASS_NAME} failed.")  # noqa: E501
                raise
        try:
            cpm.add_compute_policy_to_vdc(
                pyvcloud_utils.extract_id(test_vdc.get_resource_admin().get('id')),
                created_policy['id'])
        except Exception as err:
            logger.error(f"Error here: {err}")

        create_cluster_admin_role(config['vcd'], logger=logger)
        create_cluster_author_role(config['vcd'], logger=logger)


# TODO remove after removing legacy mode
def init_environment(config_filepath=BASE_CONFIG_FILEPATH):
    """Set up module variables according to config dict.

    :param str config_filepath:
    """
    global AMQP_USERNAME, AMQP_PASSWORD, CLIENT, ORG_HREF, VDC_HREF, \
        CATALOG_NAME, TEARDOWN_INSTALLATION, TEARDOWN_CLUSTERS, \
        TEMPLATE_DEFINITIONS, TEST_ALL_TEMPLATES, SYS_ADMIN_LOGIN_CMD, \
        ORG_ADMIN_LOGIN_CMD, K8_AUTHOR_LOGIN_CMD, USERNAME_TO_LOGIN_CMD, \
        USERNAME_TO_CLUSTER_NAME, TEST_ORG_HREF, TEST_VDC_HREF, \
        VCD_API_VERSION_TO_USE, TEMPLATE_COOKBOOK_VERSION

    config = testutils.yaml_to_dict(config_filepath)

    rtm = \
        RemoteTemplateManager(config['broker']['remote_template_cookbook_url'],
                              legacy_mode=config['service']['legacy_mode'])
    template_cookbook = rtm.get_filtered_remote_template_cookbook()
    TEMPLATE_COOKBOOK_VERSION = rtm.cookbook_version
    TEMPLATE_DEFINITIONS = template_cookbook['templates']
    rtm.download_all_template_scripts(force_overwrite=True)

    CLIENT = Client(config['vcd']['host'],
                    api_version=config['vcd']['api_version'],
                    verify_ssl_certs=config['vcd']['verify'])
    credentials = BasicLoginCredentials(config['vcd']['username'],
                                        shared_constants.SYSTEM_ORG_NAME,
                                        config['vcd']['password'])
    CLIENT.set_credentials(credentials)

    VCD_API_VERSION_TO_USE = config['vcd']['api_version']
    CATALOG_NAME = config['broker']['catalog']
    AMQP_USERNAME = config['amqp']['username']
    AMQP_PASSWORD = config['amqp']['password']

    SYS_ADMIN_LOGIN_CMD = f"login {config['vcd']['host']} system " \
                          f"{config['vcd']['username']} " \
                          f"-iwp {config['vcd']['password']} " \
                          f"-V {VCD_API_VERSION_TO_USE}"
    ORG_ADMIN_LOGIN_CMD = f"login {config['vcd']['host']} " \
                          f"{TEST_ORG}" \
                          f" {ORG_ADMIN_NAME} -iwp {ORG_ADMIN_PASSWORD} " \
                          f"-V {VCD_API_VERSION_TO_USE}"
    K8_AUTHOR_LOGIN_CMD = f"login {config['vcd']['host']} " \
        f"{TEST_ORG} " \
        f"{K8_AUTHOR_NAME} -iwp {K8_AUTHOR_PASSWORD}" \
        f" -V {VCD_API_VERSION_TO_USE}"

    USERNAME_TO_LOGIN_CMD = {
        'sys_admin': SYS_ADMIN_LOGIN_CMD,
        'org_admin': ORG_ADMIN_LOGIN_CMD,
        'k8_author': K8_AUTHOR_LOGIN_CMD
    }

    USERNAME_TO_CLUSTER_NAME = {
        'sys_admin': SYS_ADMIN_TEST_CLUSTER_NAME,
        'org_admin': ORG_ADMIN_TEST_CLUSTER_NAME,
        'k8_author': K8_AUTHOR_TEST_CLUSTER_NAME
    }
    # hrefs for Org and VDC that hosts the catalog
    org = pyvcloud_utils.get_org(CLIENT, org_name=config['broker']['org'])
    vdc = pyvcloud_utils.get_vdc(CLIENT, vdc_name=config['broker']['vdc'],
                                 org=org)
    ORG_HREF = org.href
    VDC_HREF = vdc.href

    # hrefs for Org and VDC that tests cluster operations
    test_org = pyvcloud_utils.get_org(CLIENT, org_name=TEST_ORG)
    test_vdc = pyvcloud_utils.get_vdc(CLIENT, vdc_name=TEST_VDC, org=test_org)
    TEST_ORG_HREF = test_org.href
    TEST_VDC_HREF = test_vdc.href
    create_k8_author_role(config['vcd'])


def cleanup_environment(logger=NULL_LOGGER):
    logger.debug("Logging out.")
    if CLIENT is not None:
        CLIENT.logout()


def setup_active_config(logger=NULL_LOGGER):
    """Set up the active config file from BASE_CONFIG.

    'test' section is removed if it exists in base config, active config is
    created at ACTIVE_CONFIG_FILEPATH.

    :returns: config dict without 'test' key

    :rtype: dict
    """
    logger.debug("Setting up active config")
    config = testutils.yaml_to_dict(BASE_CONFIG_FILEPATH)
    if 'test' in config:
        del config['test']

    testutils.dict_to_yaml_file(config, ACTIVE_CONFIG_FILEPATH)
    os.chmod(ACTIVE_CONFIG_FILEPATH, 0o600)

    return config


def teardown_active_config():
    """Delete the active config file if it exists."""
    if os.path.exists(ACTIVE_CONFIG_FILEPATH):
        os.remove(ACTIVE_CONFIG_FILEPATH)


# TODO remove after removing legacy mode
def create_k8_author_role(vcd_config: dict):
    cmd = f"login {vcd_config['host']} {shared_constants.SYSTEM_ORG_NAME} " \
        f"{vcd_config['username']} -iwp {vcd_config['password']} " \
        f"-V {VCD_API_VERSION_TO_USE}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    cmd = f"org use {TEST_ORG}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    result = CLI_RUNNER.invoke(
        vcd, ['role', 'clone', VAPP_AUTHOR_ROLE_NAME, K8_AUTHOR_ROLE_NAME],
        catch_exceptions=False)
    assert DUPLICATE_NAME in result.stdout or result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # Add View right for other published catalogs
    result = CLI_RUNNER.invoke(
        vcd, ['role', 'add-right', K8_AUTHOR_ROLE_NAME,
              VIEW_PUBLISHED_CATALOG_RIGHT],
        catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)


def create_cluster_admin_role(vcd_config: dict, logger=NULL_LOGGER):
    """Create cluster_admin role using pre-existing 'vapp author' role.

    :param dict vcd_config: server config file
    :param logging.Logger logger:
    """
    logger.debug("Creating cluster admin role.")
    cmd = f"login {vcd_config['host']} {shared_constants.SYSTEM_ORG_NAME} " \
        f"{vcd_config['username']} -iwp {vcd_config['password']} " \
        f"-V {VCD_API_VERSION_TO_USE}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    cmd = f"org use {TEST_ORG}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0

    logger.debug(f"Cloning role {ORG_ADMIN_ROLE_NAME} "
                 f"to create {CLUSTER_ADMIN_ROLE_NAME}")
    result = CLI_RUNNER.invoke(
        vcd, ['role', 'clone', ORG_ADMIN_ROLE_NAME, CLUSTER_ADMIN_ROLE_NAME],
        catch_exceptions=False)
    role_exists = DUPLICATE_NAME in result.stdout
    if role_exists:
        logger.debug(f"Role {CLUSTER_ADMIN_ROLE_NAME} already exists.")
    assert role_exists or result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # Add View right for other published catalogs
    logger.debug(f"Publishing {VIEW_PUBLISHED_CATALOG_RIGHT} to "
                 f"the role {CLUSTER_ADMIN_ROLE_NAME}")
    result = CLI_RUNNER.invoke(
        vcd, ['role', 'add-right', CLUSTER_ADMIN_ROLE_NAME,
              VIEW_PUBLISHED_CATALOG_RIGHT],
        catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    logger.debug(f"Successfully created role: {CLUSTER_ADMIN_ROLE_NAME}")


def create_cluster_author_role(vcd_config: dict, logger=NULL_LOGGER):
    """Create cluster_author role using pre-existing 'org admin' role.

    :param dict vcd_config: server config file
    :param logging.Logger logger:
    """
    logger.debug("Creating cluster author role.")
    cmd = f"login {vcd_config['host']} {shared_constants.SYSTEM_ORG_NAME} " \
        f"{vcd_config['username']} -iwp {vcd_config['password']} " \
        f"-V {VCD_API_VERSION_TO_USE}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    cmd = f"org use {TEST_ORG}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0

    logger.debug(f"Cloning role {VAPP_AUTHOR_ROLE_NAME} "
                 f"to create {CLUSTER_AUTHOR_ROLE_NAME}")
    result = CLI_RUNNER.invoke(
        vcd, ['role', 'clone', VAPP_AUTHOR_ROLE_NAME, CLUSTER_AUTHOR_ROLE_NAME],  # noqa: E501
        catch_exceptions=False)
    assert DUPLICATE_NAME in result.stdout or result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    # Add View right for other published catalogs
    logger.debug(f"Publishing {VIEW_PUBLISHED_CATALOG_RIGHT} to the role "
                 f"{CLUSTER_AUTHOR_ROLE_NAME}")
    result = CLI_RUNNER.invoke(
        vcd, ['role', 'add-right', CLUSTER_AUTHOR_ROLE_NAME,
              VIEW_PUBLISHED_CATALOG_RIGHT],
        catch_exceptions=False)
    assert result.exit_code == 0, \
        testutils.format_command_info('vcd', cmd, result.exit_code,
                                      result.output)
    logger.debug(f"Successfully created role: {CLUSTER_AUTHOR_ROLE_NAME}")


def create_user(username, password, role, logger=NULL_LOGGER):
    config = testutils.yaml_to_dict(BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} " \
          f"{shared_constants.SYSTEM_ORG_NAME} " \
          f"{config['vcd']['username']} -iwp {config['vcd']['password']} " \
          f"-V {VCD_API_VERSION_TO_USE}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    cmd = f"org use {TEST_ORG}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0

    # cannot use cmd.split() here because the role name
    # "Organization Administrator" gets split into 2 arguments
    CLI_RUNNER.invoke(
        vcd,
        ['user', 'create', username, password, role, '--enabled'],
        catch_exceptions=False
    )
    # no assert here because if the user exists, the exit code will be 2

    logger.debug(f"Successfully created user {username}")


def delete_catalog_item(item_name, logger=NULL_LOGGER):
    logger.debug(f"Deleting catalog item: {item_name}")
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.delete_catalog_item(CATALOG_NAME, item_name)
        pyvcloud_utils.wait_for_catalog_item_to_resolve(CLIENT, CATALOG_NAME,
                                                        item_name, org=org)
        org.reload()
        logger.debug(f"Successfully deleted the catalog item: {item_name}")
    except EntityNotFoundException as e:
        logger.warning(f"Failed to delete catalog item {item_name}: {e}")


def delete_vapp(vapp_name, vdc_href, logger=NULL_LOGGER):
    logger.debug(f"Deleting vapp {vapp_name} in vdc {vdc_href}.")
    vdc = VDC(CLIENT, href=vdc_href)
    try:
        task = vdc.delete_vapp(vapp_name, force=True)
        CLIENT.get_task_monitor().wait_for_success(task)
        vdc.reload()
        logger.debug(f"Successfully deleted the vapp {vapp_name}.")
    except EntityNotFoundException as e:
        logger.warning(f"Failed to vapp {vapp_name}: {e}")


def delete_rde(cluster_name, logger=NULL_LOGGER):
    """Delete defined entity with the given name.

    NOTE: RDE names are not unique. This function deletes all occurances
    """
    try:
        cloudapi_client: CloudApiClient = \
            pyvcloud_utils.get_cloudapi_client_from_vcd_client(
                CLIENT, logger_debug=logger, logger_wire=SERVER_CLOUDAPI_WIRE_LOGGER)  # noqa: E501
        from container_service_extension.rde.common.entity_service import DefEntityService  # noqa: E501
        entity_svc = DefEntityService(cloudapi_client)
        for cluster_rde in \
            entity_svc.list_all_native_rde_by_name_and_rde_version(
                cluster_name,
                rde_utils.get_runtime_rde_version_by_vcd_api_version(CLIENT.get_api_version())):  # noqa: E501
            entity_svc.resolve_entity(cluster_rde.id, cluster_rde.entityType)
            entity_svc.delete_entity(cluster_rde.id)
    except cse_exceptions.DefEntityServiceError as e:
        PYTEST_LOGGER.error(f"Failed to delete RDE: {e}")
        pass


def delete_catalog(catalog_name=None, logger=NULL_LOGGER):
    if catalog_name is None:
        catalog_name = CATALOG_NAME
    logger.debug(f"Deleting catalog {catalog_name}")
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.delete_catalog(catalog_name)
        # TODO() no way currently to wait for catalog deletion.
        # https://github.com/vmware/pyvcloud/issues/334
        # below causes EntityNotFoundException, catalog not found.
        # time.sleep(15)
        # org.reload()
        logger.debug(f"Successfully deleted the catalog {catalog_name}")
    except EntityNotFoundException:
        logger.warning(f"Failed to delete catalog {catalog_name}")


# TODO remove after removing legacy mode
def unregister_cse():
    try:
        APIExtension(CLIENT).delete_extension(
            server_constants.CSE_SERVICE_NAME,
            server_constants.CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        pass


def unregister_cse_in_mqtt(logger=NULL_LOGGER):
    logger.debug("Unregistering CSE as MQTT extension")
    try:
        mqtt_ext_manager = MQTTExtensionManager(CLIENT)
        mqtt_ext_info = mqtt_ext_manager.get_extension_info(
            ext_name=server_constants.CSE_SERVICE_NAME,
            ext_version=server_constants.MQTT_EXTENSION_VERSION,
            ext_vendor=server_constants.MQTT_EXTENSION_VENDOR)
        ext_urn_id = mqtt_ext_info[server_constants.MQTTExtKey.EXT_URN_ID]
        mqtt_ext_manager.delete_extension(
            ext_name=server_constants.CSE_SERVICE_NAME,
            ext_version=server_constants.MQTT_EXTENSION_VERSION,
            ext_vendor=server_constants.MQTT_EXTENSION_VENDOR,
            ext_urn_id=ext_urn_id)
        logger.debug("Successfully unregistered CSE as MQTT extension")
    except Exception as e:
        logger.warning(f"Failed to unregister CSE from MQTT: {e}")


def publish_right_bundle_to_deployment_org(logger=NULL_LOGGER):
    try:
        rbm = RightBundleManager(CLIENT, logger_debug=logger, logger_wire=logger)  # noqa: E501
        cse_right_bundle = rbm.get_right_bundle_by_name(
            rde_constants.DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE)
        test_org_id = TEST_ORG_HREF.split('/')[-1]
        rbm.publish_cse_right_bundle_to_tenants(
            right_bundle_id=cse_right_bundle['id'],
            org_ids=[test_org_id])
        logger.debug(
            f"Successfully published native right bundle to orgs {TEST_ORG}")
    except Exception as e:
        logger.warning(f"Failed to publish native right bundle "
                       f"to org {TEST_ORG}: {e}")


def assign_native_rights(role_name, right_list=None, logger=NULL_LOGGER):
    logger.debug(f"Assigning rights {right_list} to the role {role_name}")
    if not right_list:
        logger.debug(f"Skipping assigning native rights to role {role_name}")
        return
    try:
        test_org = Org(CLIENT, href=TEST_ORG_HREF)
        role_resource = test_org.get_role_resource(role_name)
        role = Role(CLIENT, resource=role_resource)
        initial_right_set = set([r['name'] for r in role.list_rights()])
        right_set = set(right_list)
        initial_right_set.update(right_set)
        role.add_rights(list(initial_right_set), test_org)
    except Exception as e:
        logger.warning(f"Failed to assign native rights "
                       f"{right_list} to role {role_name}: {e} ")


def cleanup_rde_artifacts(logger=NULL_LOGGER):
    """Cleanup all defined entity related artifacts.

    Deletes the following -
    - CSE interface
    - Native entity type
    """
    try:
        rde_version_in_use = rde_utils.get_runtime_rde_version_by_vcd_api_version(CLIENT.get_api_version())  # noqa: E501
        rde_metadata = rde_utils.get_rde_metadata(rde_version_in_use)
        cloudapi_client = pyvcloud_utils.get_cloudapi_client_from_vcd_client(
            client=CLIENT,
            logger_debug=logger,
            logger_wire=SERVER_CLOUDAPI_WIRE_LOGGER)
        schema_svc = def_schema_svc.DefSchemaService(cloudapi_client=cloudapi_client)  # noqa: E501
        if rde_constants.RDEMetadataKey.ENTITY_TYPE in rde_metadata:
            # delete entity_type
            entity_type: common_models.DefEntityType = \
                rde_metadata[rde_constants.RDEMetadataKey.ENTITY_TYPE]
            schema_svc.delete_entity_type(entity_type.get_id())
            logger.debug(f"Deleted entity type: {entity_type.name}")
        if rde_constants.RDEMetadataKey.INTERFACES in rde_metadata:
            # delete interface
            interfaces: List[common_models.DefInterface] = \
                rde_metadata[rde_constants.RDEMetadataKey.INTERFACES]
            for i in interfaces:
                interface_id = i.get_id()
                if interface_id != common_models.K8Interface.VCD_INTERFACE.value.get_id():  # noqa: E501
                    schema_svc.delete_interface(interface_id)
                    logger.debug(f"Deleted interface: {i.name}")
    except Exception as e:
        logger.warning(f"Failed to clean up RDE artifacts: {e}")


def cleanup_roles_and_users(logger=NULL_LOGGER):
    """Cleanup all the new roles and users created.

    Deletes the following
    - cluster_author User
    - cluster_author_role Role
    - cluster_admin User
    - cluster_admin_role ROle
    """
    user_and_role_list = [
        (CLUSTER_AUTHOR_NAME, CLUSTER_AUTHOR_ROLE_NAME),
        (CLUSTER_ADMIN_NAME, CLUSTER_ADMIN_ROLE_NAME)
    ]
    org = Org(CLIENT, href=TEST_ORG_HREF)
    for user_and_role in user_and_role_list:
        try:
            logger.debug(f"cleaning up user {user_and_role[0]} and "
                         f"role {user_and_role[1]}")
            org.delete_user(user_and_role[0])
            org.delete_role(user_and_role[1])
        except Exception as e:
            logger.warning("Exception occurred when "
                           f"cleaning up roles and users: {e}")


def catalog_item_exists(catalog_item, catalog_name=None, logger=NULL_LOGGER):
    if catalog_name is None:
        catalog_name = CATALOG_NAME
    org = Org(CLIENT, href=ORG_HREF)
    try:
        # DEV NOTE: With api v33.0 and onwards, get_catalog_item operation will
        # fail for non admin users of an an org which is not hosting the
        # catalog, even if the catalog is explicitly shared with the org in
        # question. Please use this method only for org admin and sys admins.
        org.get_catalog_item(catalog_name, catalog_item)
        return True
    except EntityNotFoundException as e:
        logger.error(f"Catalog item not found: {e}")
        return False


def vapp_with_prefix_exists(prefix, vdc_href, logger=NULL_LOGGER):
    q = CLIENT.get_typed_query(
        ResourceType.ADMIN_VAPP.value,
        qfilter=f"name=={prefix}*&",
        equality_filter=("vdc", vdc_href))
    vapp_records = q.execute()
    if len(vapp_records) > 0:
        return True
    return False


def delete_all_vapps_with_prefix(prefix, vdc_href, logger=NULL_LOGGER):
    q = CLIENT.get_typed_query(
        ResourceType.ADMIN_VAPP.value,
        qfilter=f"name=={prefix}*&",
        equality_filter=("vdc", vdc_href))
    vapp_records = q.execute()
    for vapp_record in vapp_records:
        delete_vapp(vapp_record.get('name'), vdc_href, logger=logger)


def vapp_exists(vapp_name, vdc_href, logger=NULL_LOGGER):
    vdc = VDC(CLIENT, href=vdc_href)
    try:
        vdc.get_vapp(vapp_name)
        logger.debug(f"Vapp {vapp_name} found in vdc {vdc.name}")
        return True
    except EntityNotFoundException:
        logger.warning(f"Vapp {vapp_name} not found in vdc {vdc.name}")
        return False


def rde_with_prefix_exists(prefix, logger=NULL_LOGGER):
    return rde_exists(f"{prefix}*")


def delete_all_rde_with_prefix(prefix, logger=NULL_LOGGER):
    return delete_rde(f"{prefix}*", logger=logger)


def rde_exists(rde_name, logger=NULL_LOGGER):
    try:
        cloudapi_client: CloudApiClient = \
            pyvcloud_utils.get_cloudapi_client_from_vcd_client(
                CLIENT,
                logger_debug=logger,
                logger_wire=SERVER_CLOUDAPI_WIRE_LOGGER)
        # To avoid cyclic import
        from container_service_extension.rde.common.entity_service import \
            DefEntityService
        entity_svc = DefEntityService(cloudapi_client)
        rde_version = rde_utils.get_runtime_rde_version_by_vcd_api_version(
            CLIENT.get_api_version())
        entity = \
            entity_svc.get_native_rde_by_name_and_rde_version(
                rde_name, rde_version)
        return bool(entity)
    except Exception as e:
        logger.warning(f"Exception occured when checking if rde exists: {e}")
        return False


# TODO remove after deprecating non-rde tests
def is_cse_registered():
    try:
        APIExtension(CLIENT).get_extension(
            server_constants.CSE_SERVICE_NAME,
            namespace=server_constants.CSE_SERVICE_NAMESPACE)
        return True
    except MissingRecordException:
        return False


def is_cse_registered_as_mqtt_ext(logger=NULL_LOGGER):
    try:
        mqtt_ext_manager = MQTTExtensionManager(CLIENT, debug_logger=logger)
        return mqtt_ext_manager.check_extension_exists(
            server_constants.MQTT_EXTENSION_URN)
    except MissingRecordException as e:
        logger.error(f"Error occurred when checking if CSE is registered: {e}")
        return False


def is_cse_registration_valid(routing_key, exchange):
    try:
        ext = APIExtension(CLIENT).get_extension(
            server_constants.CSE_SERVICE_NAME,
            namespace=server_constants.CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        return False

    if ext['routingKey'] != routing_key or ext['exchange'] != exchange:
        return False

    return True


def check_cse_registration(routing_key, exchange):
    cse_is_registered = is_cse_registered()
    assert cse_is_registered, \
        'CSE is not registered as an extension when it should be.'
    if cse_is_registered:
        assert is_cse_registration_valid(routing_key, exchange), \
            'CSE is registered as an extension, but the extension settings ' \
            'on vCD are not the same as config settings.'


def check_cse_registration_as_mqtt_extension(logger=NULL_LOGGER):
    mqtt_ext_manager = MQTTExtensionManager(CLIENT, debug_logger=logger)
    is_cse_registered_bool = mqtt_ext_manager.check_extension_exists(
        server_constants.MQTT_EXTENSION_URN)
    assert is_cse_registered_bool, \
        'CSE is not registered as an extension when it should be.'
    if is_cse_registered_bool:
        assert mqtt_ext_manager.is_extension_enabled(
            server_constants.MQTT_EXTENSION_URN), "CSE is registered as an " \
            "extension but the extension is not enabled"
