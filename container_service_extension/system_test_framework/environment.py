# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
from pathlib import Path

from click.testing import CliRunner
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vdc import VDC
from vcd_cli.vcd import vcd

from container_service_extension.common.constants.server_constants import CSE_SERVICE_NAME  # noqa: E501
from container_service_extension.common.constants.server_constants import CSE_SERVICE_NAMESPACE  # noqa: E501
from container_service_extension.common.constants.shared_constants import SYSTEM_ORG_NAME  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as pyvcloud_utils  # noqa: E501
from container_service_extension.installer.templates.remote_template_manager import RemoteTemplateManager  # noqa: E501
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

SCRIPTS_DIR = 'scripts'

SSH_KEY_FILEPATH = str(Path.home() / '.ssh' / 'id_rsa.pub')
CLI_RUNNER = CliRunner()
SYS_ADMIN_TEST_CLUSTER_NAME = 'testclustersystem'
ORG_ADMIN_TEST_CLUSTER_NAME = 'testclusteradmin'
K8_AUTHOR_TEST_CLUSTER_NAME = 'testclusterk8'

# required user info
SYS_ADMIN_NAME = 'sys_admin'
ORG_ADMIN_NAME = 'org_admin'
ORG_ADMIN_PASSWORD = 'password'  # nosec: test environment
ORG_ADMIN_ROLE_NAME = 'Organization Administrator'
VAPP_AUTHOR_ROLE_NAME = 'vApp Author'
K8_AUTHOR_NAME = 'k8_author'
K8_AUTHOR_PASSWORD = 'password'  # nosec: test environment
K8_AUTHOR_ROLE_NAME = 'k8 Author'

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


def init_environment(config_filepath=BASE_CONFIG_FILEPATH):
    """Set up module variables according to config dict.

    :param str config_filepath:
    """
    global AMQP_USERNAME, AMQP_PASSWORD, CLIENT, ORG_HREF, VDC_HREF, \
        CATALOG_NAME, TEARDOWN_INSTALLATION, TEARDOWN_CLUSTERS, \
        TEMPLATE_DEFINITIONS, TEST_ALL_TEMPLATES, SYS_ADMIN_LOGIN_CMD, \
        ORG_ADMIN_LOGIN_CMD, K8_AUTHOR_LOGIN_CMD, USERNAME_TO_LOGIN_CMD, \
        USERNAME_TO_CLUSTER_NAME, TEST_ORG_HREF, TEST_VDC_HREF

    config = testutils.yaml_to_dict(config_filepath)

    rtm = \
        RemoteTemplateManager(config['broker']['remote_template_cookbook_url'],
                              legacy_mode=config['service']['legacy_mode'])
    template_cookbook = rtm.get_filtered_remote_template_cookbook()
    TEMPLATE_DEFINITIONS = template_cookbook['templates']
    rtm.download_all_template_scripts(force_overwrite=True)

    init_test_vars(config.get('test'))

    CLIENT = Client(config['vcd']['host'],
                    api_version=config['vcd']['api_version'],
                    verify_ssl_certs=config['vcd']['verify'])
    credentials = BasicLoginCredentials(config['vcd']['username'],
                                        SYSTEM_ORG_NAME,
                                        config['vcd']['password'])
    CLIENT.set_credentials(credentials)

    CATALOG_NAME = config['broker']['catalog']
    AMQP_USERNAME = config['amqp']['username']
    AMQP_PASSWORD = config['amqp']['password']

    SYS_ADMIN_LOGIN_CMD = f"login {config['vcd']['host']} system " \
                          f"{config['vcd']['username']} " \
                          f"-iwp {config['vcd']['password']} " \
                          f"-V {config['vcd']['api_version']}"
    ORG_ADMIN_LOGIN_CMD = f"login {config['vcd']['host']} " \
                          f"{TEST_ORG}" \
                          f" {ORG_ADMIN_NAME} -iwp {ORG_ADMIN_PASSWORD} " \
                          f"-V {config['vcd']['api_version']}"
    K8_AUTHOR_LOGIN_CMD = f"login {config['vcd']['host']} " \
        f"{TEST_ORG} " \
        f"{K8_AUTHOR_NAME} -iwp {K8_AUTHOR_PASSWORD}" \
        f" -V {config['vcd']['api_version']}"

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


def init_test_vars(test_config):
    """Initialize all the environment variables that are used for test.

    :param dict test_config: test section of config.yaml
    """
    global TEMPLATE_DEFINITIONS, TEARDOWN_INSTALLATION, TEARDOWN_CLUSTERS, \
        TEST_ALL_TEMPLATES, TEST_ORG, TEST_VDC, TEST_NETWORK

    if test_config is not None:
        TEARDOWN_INSTALLATION = test_config.get('teardown_installation', True)
        TEARDOWN_CLUSTERS = test_config.get('teardown_clusters', True)
        TEST_ALL_TEMPLATES = test_config.get('test_all_templates', False)
        TEST_ORG = test_config.get('org', 'test-org')
        TEST_VDC = test_config.get('vdc', 'test-vdc')
        TEST_NETWORK = test_config.get('network', 'test-network')
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


def cleanup_environment():
    if CLIENT is not None:
        CLIENT.logout()


def setup_active_config():
    """Set up the active config file from BASE_CONFIG.

    'test' section is removed if it exists in base config, active config is
    created at ACTIVE_CONFIG_FILEPATH.

    :returns: config dict without 'test' key

    :rtype: dict
    """
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


def create_k8_author_role(vcd_config: dict):
    cmd = f"login {vcd_config['host']} {SYSTEM_ORG_NAME} " \
        f"{vcd_config['username']} -iwp {vcd_config['password']} " \
        f"-V {vcd_config['api_version']}"
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


def create_user(username, password, role):
    config = testutils.yaml_to_dict(BASE_CONFIG_FILEPATH)
    cmd = f"login {config['vcd']['host']} {SYSTEM_ORG_NAME} " \
          f"{config['vcd']['username']} -iwp {config['vcd']['password']} " \
          f"-V {config['vcd']['api_version']}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0
    cmd = f"org use {TEST_ORG}"
    result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    assert result.exit_code == 0

    # cannot use cmd.split() here because the role name
    # "Organization Administrator" gets split into 2 arguments
    result = CLI_RUNNER.invoke(vcd,
                               ['user', 'create', username, password, role,
                                '--enabled'],
                               catch_exceptions=False)
    # no assert here because if the user exists, the exit code will be 2

    # user can already exist but be disabled
    # cmd = f"user update {username} --enable"
    # result = CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
    # assert result.exit_code == 0,\
    #    testutils.format_command_info('vcd', cmd, result.exit_code,
    #                                  result.output)


def delete_catalog_item(item_name):
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.delete_catalog_item(CATALOG_NAME, item_name)
        pyvcloud_utils.wait_for_catalog_item_to_resolve(CLIENT, CATALOG_NAME,
                                                        item_name, org=org)
        org.reload()
    except EntityNotFoundException:
        pass


def delete_vapp(vapp_name, vdc_href):
    vdc = VDC(CLIENT, href=vdc_href)
    try:
        task = vdc.delete_vapp(vapp_name, force=True)
        CLIENT.get_task_monitor().wait_for_success(task)
        vdc.reload()
    except EntityNotFoundException:
        pass


def delete_catalog(catalog_name=None):
    if catalog_name is None:
        catalog_name = CATALOG_NAME
    org = Org(CLIENT, href=ORG_HREF)
    try:
        org.delete_catalog(catalog_name)
        # TODO() no way currently to wait for catalog deletion.
        # https://github.com/vmware/pyvcloud/issues/334
        # below causes EntityNotFoundException, catalog not found.
        # time.sleep(15)
        # org.reload()
    except EntityNotFoundException:
        pass


def unregister_cse():
    try:
        APIExtension(CLIENT).delete_extension(CSE_SERVICE_NAME,
                                              CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        pass


def catalog_item_exists(catalog_item, catalog_name=None):
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
    except EntityNotFoundException:
        return False


def vapp_exists(vapp_name, vdc_href):
    vdc = VDC(CLIENT, href=vdc_href)
    try:
        vdc.get_vapp(vapp_name)
        return True
    except EntityNotFoundException:
        return False


def is_cse_registered():
    try:
        APIExtension(CLIENT).get_extension(CSE_SERVICE_NAME,
                                           namespace=CSE_SERVICE_NAMESPACE)
        return True
    except MissingRecordException:
        return False


def is_cse_registration_valid(routing_key, exchange):
    try:
        ext = APIExtension(CLIENT).get_extension(CSE_SERVICE_NAME,
                                                 namespace=CSE_SERVICE_NAMESPACE)  # noqa: E501
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
