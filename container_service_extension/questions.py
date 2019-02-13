# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
This module runs through the various config options, and can
be configured to create a sample config, verify without any
interaction, do an interactive interview on the console, or
some things in-between.

It stores its state in global variables, so it is not
reentrant.
"""

from __future__ import unicode_literals

import click
import pika
import yaml
from prompt_toolkit.styles import Style
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException, \
    MultipleRecordsException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.org import Org
from vcd_cli.utils import stdout

from container_service_extension.interview.comment import Comment
from container_service_extension.interview.confirmation import Confirmation
from container_service_extension.interview.group import Group
from container_service_extension.interview.indexed_group import IndexedGroup
from container_service_extension.interview.question import Question
from container_service_extension.interview.top_level_context import \
    TopLevelContext
from container_service_extension.logger import INSTALL_LOGGER as LOGGER
from container_service_extension.server_constants import CSE_SERVICE_NAME, \
    CSE_SERVICE_NAMESPACE
from container_service_extension.utils import EXCHANGE_TYPE
from container_service_extension.utils import SYSTEM_ORG_NAME
from container_service_extension.utils import catalog_exists
from container_service_extension.utils import catalog_item_exists
from container_service_extension.utils import check_file_permissions
from container_service_extension.utils import get_org

SAMPLE_TEMPLATE_PHOTON_V2 = {
    'name': 'photon-v2',
    'catalog_item': 'photon-custom-hw11-2.0-304b817-k8s',
    'source_ova_name': 'photon-custom-hw11-2.0-304b817.ova',
    'source_ova': 'http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova',
    # noqa
    'sha256_ova': 'cb51e4b6d899c3588f961e73282709a0d054bb421787e140a1d80c24d4fd89e1',
    # noqa
    'temp_vapp': 'photon2-temp',
    'cleanup': True,
    'cpu': 2,
    'mem': 2048,
    'admin_password': 'guest_os_admin_password',
    'description': 'PhotonOS v2\nDocker 17.06.0-4\nKubernetes 1.9.1\nweave 2.3.0'
    # noqa
}

SAMPLE_TEMPLATE_UBUNTU_16_04 = {
    'name': 'ubuntu-16.04',
    'catalog_item': 'ubuntu-16.04-server-cloudimg-amd64-k8s',
    'source_ova_name': 'ubuntu-16.04-server-cloudimg-amd64.ova',
    'source_ova': 'https://cloud-images.ubuntu.com/releases/xenial/release-20180418/ubuntu-16.04-server-cloudimg-amd64.ova',
    # noqa
    'sha256_ova': '3c1bec8e2770af5b9b0462e20b7b24633666feedff43c099a6fb1330fcc869a9',
    # noqa
    'temp_vapp': 'ubuntu1604-temp',
    'cleanup': True,
    'cpu': 2,
    'mem': 2048,
    'admin_password': 'guest_os_admin_password',
    'description': 'Ubuntu 16.04\nDocker 18.03.0~ce\nKubernetes 1.10.1\nweave 2.3.0'
    # noqa
}


def capture_vapp_to_template(ctx, vapp, catalog_name, catalog_item_name,
                             desc='', power_on=False, org=None, org_name=None):
    """Shutdown and capture existing VApp as a template in @catalog.

    VApp should have tools ready, or shutdown will fail, and VApp will be
    unavailable to be captured.

    :param click.core.Context ctx: click context object needed for stdout.
    :param pyvcloud.vcd.vapp.VApp vapp:
    :param str catalog_name:
    :param str catalog_item_name: catalog item name for the template.
    :param str desc: template description.
    :param bool power_on: if True, turns on VApp after capturing.
    :param pyvcloud.vcd.org.Org org: specific org to use.
    :param str org_name: specific org to use if @org is not given.
        If None, uses currently logged-in org from @vapp (vapp.client).

    :raises EntityNotFoundException: if the org could not be found.
    """
    if org is None:
        org = get_org(vapp.client, org_name=org_name)
    catalog = org.get_catalog(catalog_name)
    try:
        task = vapp.shutdown()
        stdout(task, ctx=ctx)
        vapp.reload()
    except OperationNotSupportedException:
        pass

    task = org.capture_vapp(catalog, vapp.href, catalog_item_name, desc,
                            customize_on_instantiate=True, overwrite=True)
    stdout(task, ctx=ctx)
    org.reload()

    if power_on:
        task = vapp.power_on()
        stdout(task, ctx=ctx)
        vapp.reload()


def TemplateQuestions():
    def __init__(self, group):
        self.group = group

    def create_questions(self):
        return [
            Question(
                yaml_field="name",
                description="Unique name of the template"),
            Question(
                yaml_field="description",
                description="Multi-line edit of the catalog item description"),
            Question(
                yaml_field="source_ova",
                description="URL of the source OVA to download"),
            Question(
                yaml_field="sha256_ova",
                description="sha256 of the source OVA"),
            Question(
                yaml_field="source_ova_name",
                description="Name of the source OVA in the catalog"),
            Question(
                yaml_field="catalog_item",
                description="Name of the template in the catalog"),
            Question(
                yaml_field="description",
                description="Information about the template"),
            Question(
                yaml_field="temp_vapp",
                description="Name of the temporary vApp used to build the "
                            "template. Once the template is created, this vApp can be "
                            "deleted. It will be deleted by default during the "
                            "installation based on the value of the cleanup property"),
            Question(
                yaml_field="cleanup",
                description="If True, temp_vapp will be deleted by the "
                            "install process after the master template is created"),
            Question(
                yaml_field="admin_password",
                description="root password for the template and instantiated "
                            "VMs. This password should not be shared with tenants"),
            Question(
                yaml_field="cpu",
                default=2,
                description="Number of virtual CPUs to be allocated "
                            "for each VM"),
            Question(
                yaml_field="mem",
                default=2048,
                description="Memory in MB to be allocated for each VM")
        ]


def str2bool(v):
    return v is not None and v.lower() in ("y", "yes", "t", "true", "1")


def is_detailed_interview(question):
    return question.context.get_shared_value("detailed")


def load_vcd_versions(question):
    """
    Log into the vCD host, and configure the context with the authorized client
    """
    vcd_uri = question.context.get_yaml_value("host") + ":" \
              + question.context.get_yaml_value("port")
    vcd_client = Client(vcd_uri,
                        verify_ssl_certs=str2bool(
                            question.context.get_yaml_value('verify')))
    versions = vcd_client.get_supported_versions_list()

    question.set_choices(versions)
    question.set_default(versions[-1])


def load_vcd_client(question):
    """
    Log into the vCD host, and configure the context with the authorized client
    """
    top_context = question.context.get_top_context()

    # Clear the old client before trying to load the new one
    top_context.get_top_context().set_shared_value('vcd_client', None)

    vcd_uri = top_context.get_yaml_value("vcd.host") + ":" \
              + top_context.get_yaml_value("vcd.port")
    vcd_client = Client(vcd_uri,
                        api_version=top_context.get_yaml_value(
                            'vcd.api_version'),
                        verify_ssl_certs=str2bool(
                            question.context.get_yaml_value('vcd.verify')))
    vcd_client.set_credentials(
        BasicLoginCredentials(top_context.get_yaml_value('vcd.username'),
                              SYSTEM_ORG_NAME,
                              top_context.get_yaml_value("vcd.password")))

    # Save in the shared context for all validators
    top_context.set_shared_value('vcd_client', vcd_client)

    # TODO use prompt instead of click.secho?
    click.secho(f"Connected to vCloud Director "
                f"({vcd_uri})", fg='green')

    # Load defaults from vcd
    amqp_settings = vcd_client.get_resource(
        vcd_client.get_api_uri() + "/admin/extension/settings/amqp")

    top_context.set_yaml_value_default('amqp.host', amqp_settings.AmqpHost)
    top_context.set_yaml_value_default('amqp.port',
                                       str(amqp_settings.AmqpPort))
    top_context.set_yaml_value_default('amqp.use_ssl',
                                       str(amqp_settings.AmqpUseSSL))
    top_context.set_yaml_value_default('amqp.username',
                                       amqp_settings.AmqpUsername)
    top_context.set_yaml_value_default('amqp.exchange',
                                       amqp_settings.AmqpExchange)
    top_context.set_yaml_value_default('amqp.ssl_accept_all',
                                       str(amqp_settings.AmqpSslAcceptAll))
    top_context.set_yaml_value_default('amqp.vhost',
                                       str(amqp_settings.AmqpVHost))


def get_amqp_settings(question):
    """
    Talk to the vCD client and get the AMQP service
    :return: current server AMQP settings
    :rtype: dict
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    amqp_settings = question.context.get_shared_value('amqp_settings')

    if amqp_settings is None:
        amqp_settings = vcd_client.get_resource(
            vcd_client.get_api_uri() + "/admin/extension/settings/amqp")
        question.context.get_top_context().set_shared_value('amqp_settings',
                                                            amqp_settings)
    return amqp_settings


def test_amqp_connection(question):
    """
    TODO!
    :param question:
    :return:
    """
    return True


def load_vc_choices(question):
    """
    Log into the vCD, and get the available VC instances
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    query = vcd_client.get_typed_query("virtualCenter")
    records = list(query.execute())
    names = list(map(lambda r: r.get('name'), records))
    question.set_choices(names)
    question.set_default(names[-1])


def load_org_choices(question):
    """
    TODO
    Log into the vCD, and get the available organizations
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    query = vcd_client.get_typed_query("organization")
    records = list(query.execute())
    names = list(map(lambda r: r.get('name'), records))
    question.set_choices(names)
    question.set_default(names[-1])


def load_vdc_choices(question):
    """
    TODO
    Log into the vCD, and get the available VC instances
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    organization_name = question.context.get_yaml_value("broker.org")
    query = vcd_client.get_typed_query("adminOrgVdc",
                                       equality_filter=(
                                       'orgName', organization_name))
    records = list(query.execute())
    names = list(map(lambda r: r.get('name'), records))
    question.set_choices(names)
    question.set_default(names[-1])


def load_catalog_choices(question):
    """
    TODO
    Log into the vCD, and get the available VC instances
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    organization_name = question.context.get_yaml_value("broker.org")
    query = vcd_client.get_typed_query("adminCatalog",
                                       equality_filter=(
                                       'orgName', organization_name))
    records = list(query.execute())
    names = list(map(lambda r: r.get('name'), records))
    question.set_choices(names)
    question.set_default(names[-1])


def load_storage_profile_choices(question):
    """
    TODO
    Log into the vCD, and get the available VC instances
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    vdc_name = question.context.get_yaml_value("broker.vdc")
    query = vcd_client.get_typed_query("adminOrgVdcStorageProfile",
                                       equality_filter=('vdcName', vdc_name))
    records = list(query.execute())
    names = list(map(lambda r: r.get('name'), records))
    question.set_choices(names)
    question.set_default(names[-1])


def load_network_choices(question):
    """
    TODO
    Log into the vCD, and get the available VC instances
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    vdc_name = question.context.get_yaml_value("broker.vdc")
    query = vcd_client.get_typed_query("orgVdcNetwork",
                                       equality_filter=('vdcName', vdc_name))
    records = list(query.execute())
    names = list(map(lambda r: r.get('name'), records))
    question.set_choices(names)
    question.set_default(names[-1])


def initialize_vc_username(question):
    """
    Log into the vCD, and get the username of the selected VC instance
    """
    vcd_client = question.context.get_shared_value('vcd_client')
    vc_name = question.context.get_yaml_value("name")
    query = vcd_client.get_typed_query("virtualCenter",
                                       equality_filter=('name', vc_name))
    records = list(query.execute())
    if len(records) == 0:
        raise EntityNotFoundException('vcenter \'%s\' not found' % vc_name)
    elif len(records) > 1:
        raise MultipleRecordsException('multiple vcenters found')

    vc_object = vcd_client.get_resource(records[0].get('href'))
    question.set_default(str(vc_object.Username))


def validate_amqp(group):
    """
    Configures vCD AMQP settings/exchange using parameter values.
    """
    vcd_client = group.get_shared_value('vcd_client')
    amqp_service = AmqpService(vcd_client)

    amqp = {
        'AmqpExchange': group.get_yaml_value("exchange"),
        'AmqpHost': group.get_yaml_value("host"),
        'AmqpPort': group.get_yaml_value("port"),
        'AmqpPrefix': group.get_yaml_value("prefix"),
        'AmqpSslAcceptAll': group.get_yaml_value("ssl_accept_all"),
        'AmqpUseSSL': group.get_yaml_value("use_ssl"),
        'AmqpUsername': group.get_yaml_value("username"),
        'AmqpVHost': group.get_yaml_value("vhost")
    }

    password = group.get_yaml_value("password")
    result = amqp_service.test_config(amqp, password)

    msg = f"AMQP test settings, result: {result['Valid'].text}"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)


all_questions = [
    Comment(
        """
           ___ ___ ___ 
          / __/ __| __|
         | (__\__ \ _| 
          \___|___/___|    version x.y
        
        This command will review the current configuration, and prompt for
        missing and important information.
        
        Press 'Enter' after each question.  To go back to a previous question,
        press the 'up-arrow' key.  To exit the interview (without saving changes),
        press 'Ctrl-C'."""),
    Comment(
        """
        You are performing a basic interview, and uncommon features will be
        assigned default values.  To get asked more questions
        use `cse interview --detailed`.""",
        skip_function=is_detailed_interview),
    Group("vcd",
          skip_if_valid=True,
          questions=[
              Question("host",
                       prompt="Host name of the vCD instance?",
                       example="vcloud-director.corp.com",
                       description="IP or hostname of the vCloud Director "
                                   "server"),
              Question("verify",
                       prompt="Verify host certificates?",
                       default="true",
                       validation="t(rue)?|f(alse)?",
                       validation_message="Please enter true or false",
                       description="Enable host name and certificate checking "
                                   "of the vCD server"),
              Question("port",
                       # hidden=True,
                       prompt="Port number to reach vCloud Director",
                       default="443",
                       validation="([1-6]\\d{0-4})?",
                       validation_message="Please enter a valid port number",
                       description="port number of the vCloud Director "
                                   "server"),
              Question("api_version",
                       initialize=load_vcd_versions,
                       validation="(\\d+\\.\\d+)?",
                       validation_message="Please enter a valid API version "
                                          "of the form 'x.y'",
                       description="API version of the vCD server"),
              Question("username",
                       default="administrator",
                       description="Username of the vCD administrator "
                                   "account"),
              Question("password",
                       description="Password of the vCD administrator "
                                   "account"),
          ],
          validation_function=load_vcd_client),
    Comment(
        "Connected to vCD server {vcd.host} as user {vcd.username}"
    ),
    Group("amqp",
          skip_if_valid=True,
          questions=[
              Question("host",
                       prompt="vCD AMQP host",
                       description="IP or hostname of the vCloud Director "
                                   "AMQP server (may be different from the "
                                   "vCD cell hosts)"),
              Question("use_ssl",
                       description="Boolean to use SSL when connecting to the "
                                   "AMQP server"),
              Question("port",
                       prompt="vCD AMQP port",
                       default="5632",
                       validation=r"^(([1-5]?\d{0,4})|(6[0-4]\d{3})|(65[0-4]\d{2})|(655[0-2]\d)|(6553[0-5]))$",
                       validation_message="Please enter a valid port number",
                       description="Port of the vCloud Director "
                                   "AMQP server"),
              Question("ssl_accept_all",
                       default="False",
                       description="True to disable host name and certificate "
                                   "checking of the AMQP server"),
              Question("username",
                       prompt="vCD AMQP user name",
                       description="Username of the vCD service account with "
                                   "minimum roles and rights"),
              Question("password",
                       prompt="vCD AMQP password",
                       description="Password of the vCD service account"),
              Question("exchange",
                       default="cse_exchange",
                       description="Name of the exchange to use communicating "
                                   "with the extension")
              #   prefix: vcd
              #   vhost: /

              #   routing_key: cse
          ],
          validation_function=test_amqp_connection),
    Comment(
        "Verified AMQP server ${amqp.host} as user ${amqp.username}"
    ),

    IndexedGroup("vcs.vc",
                 description="A list of vCenters",
                 item_prompt="${name}/${username}: ",
                 required=1,
                 questions=[
                     Question("name",
                              initialize=load_vc_choices,
                              description="name of the vSphere server in"
                                          "vCloud Director"),
                     Question("username",
                              initialize=initialize_vc_username,
                              description="Username of a vSphere service account"
                                          " with correct roles and rights"),
                     Question("password",
                              example="my-secret-password",
                              description="Password of the vCD service "
                                          "account"),
                     Question("verify",
                              default=True,
                              description="False to disable host name and "
                                          "certificate checking of the vCD "
                                          "server")
                 ]),

    Question("service.listeners",
             default="5",
             validation="([1-9]\\d{0,2})?",
             validation_message="Please enter number between 1 and 999",
             skip_function=is_detailed_interview,
             description="Number of threads to run in the CSE server process."
                         "Change this value if you need to handle"
                         "more concurrent cluster operations."),

    Question("broker.org",
             # TODO get org choices
             initialize=load_org_choices,
             description="vCD organization that contains the shared catalog "
                         "where the master templates will be stored"),

    Question("broker.type",
             choices=["default"],
             default="default",
             description="Broker type",
             skip_function=is_detailed_interview),

    Question("broker.vdc",
             # TODO get vdc choices for the org
             initialize=load_vdc_choices,
             description="Select a virtual datacenter within org that will be used "
                         "during the install process to build the template"),

    Question("broker.catalog",
             # TODO get catalog choices for the VDC
             initialize=load_catalog_choices,
             # create_option=create_catalog,
             description="Select a publicly shared catalog within org where VM "
                         "templates will be published"),

    Question("broker.network",
             # TODO get network choices for the VDC
             initialize=load_network_choices,
             description="Org Network within vdc that will be used during "
                         "the install process to build the template. It "
                         "should have outbound access to the public Internet. "
                         "The CSE appliance doesn't need to be connected "
                         "to this network"),

    Question("broker.ip_allocation_mode",
             choices=["dhcp", "pool"],
             default="pool",
             description="IP allocation mode to be used during the install "
                         "process to build the template. Possible values are "
                         "dhcp or pool. During creation of clusters for "
                         "tenants, pool IP allocation mode is always used"),

    Question("broker.storage_profile",
             # TODO get storage choices for the VDC
             initialize=load_storage_profile_choices,
             choices=None,
             description="Name of the storage profile to use when creating "
                         "the temporary vApp used to build the template"),

    Question("broker.cleanup",
             default="true",
             validation="t(rue)?|f(alse)?",
             validation_message="Please enter true or false",
             description="Set to false to keep VMs used for templates from "
                         "being cleaned up (helpful for debugging as well as "
                         "workaround for Issue #170)"),

    # IndexedGroup("broker.templates",
    #              # description = "A list of templates available for clusters",
    #              questions=TemplateQuestions()),
    # Copy from default.

    Question("broker.default_template",
             description="Name of the default template to use if none is "
                         "specified"),

    Confirmation()
]


def generate_sample_config():
    """Generates a sample config file for cse.

    TODO: Take existing config as input

    :return: sample config as dict.
    :rtype: dict
    """

    interview = TopLevelContext(all_questions)
    interview.set_shared_value('interactive', False)
    interview.set_shared_value('mode', "generate")
    interview.run()

    return interview.get_content()


def validate_config(config_file_name):
    """Gets the config file as a dictionary and checks for validity.

    Ensures that all properties exist and all values are the expected type.
    Checks that AMQP connection is available, and vCD/VCs are valid.
    Does not guarantee that CSE has been installed according to this
    config file.

    :param str config_file_name: path to config file.

    :return: CSE config.

    :rtype: dict

    :raises KeyError: if config file has missing or extra properties.
    :raises ValueError: if the value type for a config file property
        is incorrect.
    :raises AmqpConnectionError: if AMQP connection failed.
    """
    check_file_permissions(config_file_name)
    with open(config_file_name) as config_file:
        config = yaml.safe_load(config_file)

        click.secho(f"Validating config file '{config_file_name}'",
                    fg='yellow')

        interview = TopLevelContext(config, all_questions)
        interview.set_shared_value("mode", "validate")
        interview.run()

        click.secho(f"Config file '{config_file_name}' is valid", fg='green')

        return interview.get_content()


def cse_interview(config_file_name, detailed):
    """Generates a sample config file for cse.

    :param config_file_name file name of configuration file to update
    :param detailed boolean flag, set true for detailed interview
    :return: sample config as dict.
    :rtype: dict
    """

    interview = TopLevelContext(all_questions)
    interview.set_shared_value('mode', "interview")
    interview.set_shared_value('detailed', detailed)
    interview.run()

    return interview.get_content()


def validate_amqp_config(amqp_dict):
    """Ensures that 'amqp' section of config is correct.

    Checks that 'amqp' section of config has correct keys and value types.
    Also ensures that connection to AMQP server is valid.

    :param dict amqp_dict: 'amqp' section of config file as a dict.

    :raises KeyError: if @amqp_dict has missing or extra properties.
    :raises ValueError: if the value type for an @amqp_dict property
        is incorrect.
    :raises AmqpConnectionError: if AMQP connection failed.
    check_keys_and_value_types(amqp_dict, SAMPLE_AMQP_CONFIG['amqp'],
                               location="config file 'amqp' section")
    credentials = pika.PlainCredentials(amqp_dict['username'],
                                        amqp_dict['password'])
    parameters = pika.ConnectionParameters(amqp_dict['host'],
                                           amqp_dict['port'],
                                           amqp_dict['vhost'],
                                           credentials,
                                           ssl=amqp_dict['ssl'],
                                           connection_attempts=3,
                                           retry_delay=2,
                                           socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        click.secho(f"Connected to AMQP server "
                    f"({amqp_dict['host']}:{amqp_dict['port']})", fg='green')
    except Exception as err:
        raise AmqpConnectionError("Amqp connection failed:", str(err))
    finally:
        if connection is not None:
            connection.close()
    """


def validate_vcd_and_vcs_config(vcd_dict, vcs):
    """Ensures that 'vcd' and vcs' section of config are correct.

    Checks that 'vcd' and 'vcs' section of config have correct keys and value
    types. Also checks that vCD and all registered VCs in vCD are accessible.

    :param dict vcd_dict: 'vcd' section of config file as a dict.
    :param list vcs: 'vcs' section of config file as a list of dicts.

    :raises KeyError: if @vcd_dict or a vc in @vcs has missing or
        extra properties.
    :raises: ValueError: if the value type for a @vcd_dict or vc property
        is incorrect, or if vCD has a VC that is not listed in the config file.
    check_keys_and_value_types(vcd_dict, SAMPLE_VCD_CONFIG['vcd'],
                               location="config file 'vcd' section")
    if not vcd_dict['verify']:
        click.secho('InsecureRequestWarning: Unverified HTTPS request is '
                    'being made. Adding certificate verification is '
                    'strongly advised.', fg='yellow', err=True)
        requests.packages.urllib3.disable_warnings()

    client = None
    try:
        client = Client(vcd_dict['host'],
                        api_version=vcd_dict['api_version'],
                        verify_ssl_certs=vcd_dict['verify'])
        client.set_credentials(BasicLoginCredentials(vcd_dict['username'],
                                                     SYSTEM_ORG_NAME,
                                                     vcd_dict['password']))
        click.secho(f"Connected to vCloud Director "
                    f"({vcd_dict['host']}:{vcd_dict['port']})", fg='green')

        for index, vc in enumerate(vcs, 1):
            check_keys_and_value_types(vc, SAMPLE_VCS_CONFIG['vcs'][0],
                                       location=f"config file 'vcs' section, "
                                                f"vc #{index}")

        # Check that all registered VCs in vCD are listed in config file
        platform = Platform(client)
        config_vc_names = [vc['name'] for vc in vcs]
        for platform_vc in platform.list_vcenters():
            platform_vc_name = platform_vc.get('name')
            if platform_vc_name not in config_vc_names:
                raise ValueError(f"vCenter '{platform_vc_name}' registered in "
                                 f"vCD but not found in config file")

        # Check that all VCs listed in config file are registered in vCD
        for vc in vcs:
            vcenter = platform.get_vcenter(vc['name'])
            vsphere_url = urlparse(vcenter.Url.text)
            v = VSphere(vsphere_url.hostname, vc['username'],
                        vc['password'], vsphere_url.port)
            v.connect()
            click.secho(f"Connected to vCenter Server '{vc['name']}' as "
                        f"'{vc['username']}' ({vsphere_url.hostname}:"
                        f"{vsphere_url.port})", fg='green')
    finally:
        if client is not None:
            client.logout()

    """


def validate_broker_config(broker_dict):
    """Ensures that 'broker' section of config is correct.

    Checks that 'broker' section of config has correct keys and value
    types. Also checks that 'default_broker' property is a valid template.

    :param dict broker_dict: 'broker' section of config file as a dict.

    :raises KeyError: if @broker_dict has missing or extra properties.
    :raises ValueError: if the value type for a @broker_dict property is
        incorrect, or if 'default_template' has a value not listed in the
        'templates' property.

    check_keys_and_value_types(broker_dict, SAMPLE_BROKER_CONFIG['broker'],
                               location="config file 'broker' section")

    default_exists = False
    for template in broker_dict['templates']:
        check_keys_and_value_types(template, SAMPLE_TEMPLATE_PHOTON_V2,
                                   location="config file broker "
                                            "template section")
        if template['name'] == broker_dict['default_template']:
            default_exists = True

    if not default_exists:
        msg = f"Default template '{broker_dict['default_template']}' not " \
              f"found in listed templates"
        click.secho(msg, fg='red')
        raise ValueError(msg)
   """


def check_cse_installation(config, check_template='*'):
    """Ensures that CSE is installed on vCD according to the config file.

    Checks if CSE is registered to vCD, if catalog exists, and if templates
    exist.

    :param dict config: config yaml file as a dictionary
    :param str check_template: which template to check for. Default value of
        '*' means to check all templates specified in @config

    :raises EntityNotFoundException: if CSE is not registered to vCD as an
        extension, or if specified catalog does not exist, or if specified
        template(s) do not exist.
    """
    click.secho(f"Validating CSE installation according to config file",
                fg='yellow')
    err_msgs = []
    client = None
    try:
        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'])
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)

        # check that AMQP exchange exists
        amqp = config['amqp']
        credentials = pika.PlainCredentials(amqp['username'], amqp['password'])
        parameters = pika.ConnectionParameters(amqp['host'], amqp['port'],
                                               amqp['vhost'], credentials,
                                               ssl=amqp['ssl'],
                                               connection_attempts=3,
                                               retry_delay=2, socket_timeout=5)
        connection = None
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            try:
                channel.exchange_declare(exchange=amqp['exchange'],
                                         exchange_type=EXCHANGE_TYPE,
                                         durable=True,
                                         passive=True,
                                         auto_delete=False)
                click.secho(f"AMQP exchange '{amqp['exchange']}' exists",
                            fg='green')
            except pika.exceptions.ChannelClosed:
                msg = f"AMQP exchange '{amqp['exchange']}' does not exist"
                click.secho(msg, fg='red')
                err_msgs.append(msg)
        except Exception:  # TODO replace raw exception with specific
            msg = f"Could not connect to AMQP exchange '{amqp['exchange']}'"
            click.secho(msg, fg='red')
            err_msgs.append(msg)
        finally:
            if connection is not None:
                connection.close()

        # check that CSE is registered to vCD
        ext = APIExtension(client)
        try:
            cse_info = ext.get_extension(CSE_SERVICE_NAME,
                                         namespace=CSE_SERVICE_NAMESPACE)
            if cse_info['enabled'] == 'true':
                click.secho("CSE is registered to vCD and is currently "
                            "enabled", fg='green')
            else:
                click.secho("CSE is registered to vCD and is currently "
                            "disabled", fg='yellow')
        except MissingRecordException:
            msg = "CSE is not registered to vCD"
            click.secho(msg, fg='red')
            err_msgs.append(msg)

        # check that catalog exists in vCD
        org = Org(client, resource=client.get_org())
        catalog_name = config['broker']['catalog']
        if catalog_exists(org, catalog_name):
            click.secho(f"Found catalog '{catalog_name}'", fg='green')
            # check that templates exist in vCD
            for template in config['broker']['templates']:
                if check_template != '*' and \
                        check_template != template['name']:
                    continue
                catalog_item_name = template['catalog_item']
                if catalog_item_exists(org, catalog_name, catalog_item_name):
                    click.secho(f"Found template '{catalog_item_name}' in "
                                f"catalog '{catalog_name}'", fg='green')
                else:
                    msg = f"Template '{catalog_item_name}' not found in " \
                        f"catalog '{catalog_name}'"
                    click.secho(msg, fg='red')
                    err_msgs.append(msg)
        else:
            msg = f"Catalog '{catalog_name}' not found"
            click.secho(msg, fg='red')
            err_msgs.append(msg)
    finally:
        if client is not None:
            client.logout()

    if err_msgs:
        raise EntityNotFoundException(err_msgs)

    click.secho(f"CSE installation is valid", fg='green')


# Create prompt object.
style = Style.from_dict({
    # User input (default text).
    '': '#000033',

    # Prompt.
    'username': '#884444',
    'at': '#00aa00',
    'colon': '#0000aa',
    'pound': '#00aa00',
    'host': '#00ffff bg:#444400',
    'path': 'ansicyan underline',
})
