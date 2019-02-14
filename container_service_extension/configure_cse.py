# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from urllib.parse import urlparse

import click
import pika
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import FenceMode
from pyvcloud.vcd.exceptions import BadRequestException
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
import requests
from vcd_cli.utils import stdout
from vsphere_guest_run.vsphere import VSphere
import yaml

from container_service_extension.exceptions import AmqpConnectionError
from container_service_extension.exceptions import AmqpError
from container_service_extension.logger import configure_install_logger
from container_service_extension.logger import INSTALL_LOG_FILEPATH
from container_service_extension.logger import INSTALL_LOGGER as LOGGER
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import setup_log_file_directory
from container_service_extension.server_constants import \
    CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY, CSE_NATIVE_DEPLOY_RIGHT_CATEGORY, \
    CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION, CSE_NATIVE_DEPLOY_RIGHT_NAME, \
    CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY, CSE_PKS_DEPLOY_RIGHT_CATEGORY, \
    CSE_PKS_DEPLOY_RIGHT_DESCRIPTION, CSE_PKS_DEPLOY_RIGHT_NAME, \
    CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE  # noqa
from container_service_extension.utils import catalog_exists
from container_service_extension.utils import catalog_item_exists
from container_service_extension.utils import check_file_permissions
from container_service_extension.utils import check_keys_and_value_types
from container_service_extension.utils import create_and_share_catalog
from container_service_extension.utils import download_file
from container_service_extension.utils import EXCHANGE_TYPE
from container_service_extension.utils import get_data_file
from container_service_extension.utils import get_org
from container_service_extension.utils import get_vdc
from container_service_extension.utils import get_vsphere
from container_service_extension.utils import is_cse_registered
from container_service_extension.utils import SYSTEM_ORG_NAME
from container_service_extension.utils import upload_ova_to_catalog
from container_service_extension.utils import vgr_callback
from container_service_extension.utils import wait_for_catalog_item_to_resolve
from container_service_extension.utils import wait_until_tools_ready

# used for creating temp vapp
TEMP_VAPP_NETWORK_ADAPTER_TYPE = 'vmxnet3'
TEMP_VAPP_FENCE_MODE = FenceMode.BRIDGED.value

INSTRUCTIONS_FOR_PKS_CONFIG_FILE = '''# Config file for PKS enabled CSE Server to be filled by the administrator.
# This config file has the following three sections:
#   1. pks_accounts:
#       a. Cloud Admins can specify PKS service account for every (PKS managed) vCenter in vCD
#          i.e. a common PKS account per vCenter will be used for all the
#          organizations.
#       b. Cloud Admin can choose to create separate PKS service
#          account per organization per vCenter, if this option is chosen,
#          admins need to ensure that PKS accounts are correctly mapped to
#          their respective organization in the 'orgs' section of this
#          config file.
#   2. orgs: [OPTIONAL SECTION for admins who chose 1a above]
#       a. If cloud admin chooses to define PKS service account per
#          organization per vCenter, include the organization and respective
#          pks_account names in this section, else should be left blank with empty values.
#   3. pvdcs:
#       a. List of Provider vDCs dedicated for PKS enabled CSE set up only\n
# Each PKS service account needs to have the following information fields to be filled in:
#       1. PKS account name
#       2. vCenter name in vCD for this PKS account
#       3. PKS server host
#       4. PKS server port
#       5. PKS UAAC account information
# For more information, please refer to CSE documentation page:
#       https://vmware.github.io/container-service-extension/INSTALLATION.html\n'''  # noqa

NOTE_FOR_PKS_KEY_IN_CONFIG_FILE = '''# Filling out this key for regular CSE set up is optional and should be left as is.
# Only for CSE set up enabled for PKS container provider, this value needs to point to a valid PKS config file name.
'''  # noqa
PKS_CONFIG_NOTE = '''# [OPTIONAL] PKS CONFIGS
# These configs are required only for customers with PKS enabled CSE. Regular CSE users with
# no PKS container provider do not need these configs to be filled out in a separate yaml file.
'''  # noqa

SAMPLE_AMQP_CONFIG = {
    'amqp': {
        'host': 'amqp.vmware.com',
        'port': 5672,
        'prefix': 'vcd',
        'username': 'guest',
        'password': 'guest',
        'exchange': 'cse-ext',
        'routing_key': 'cse',
        'ssl': False,
        'ssl_accept_all': False,
        'vhost': '/'
    }
}

SAMPLE_VCD_CONFIG = {
    'vcd': {
        'host': 'vcd.vmware.com',
        'port': 443,
        'username': 'administrator',
        'password': 'my_secret_password',
        'api_version': '29.0',
        'verify': False,
        'log': True
    }
}

SAMPLE_VCS_CONFIG = {
    'vcs': [
        {
            'name': 'vc1',
            'username': 'cse_user@vsphere.local',
            'password': 'my_secret_password',
            'verify': False
        },
        {
            'name': 'vc2',
            'username': 'cse_user@vsphere.local',
            'password': 'my_secret_password',
            'verify': False
        }
    ]
}

SAMPLE_PKS_CONFIG_FILE_LOCATION = {
    # Path to pks config file location
    'pks_config': None
}

SAMPLE_PKS_CONFIG = {
    'orgs': [
        {
            'name': 'Org1',
            'pks_accounts': ['Org1ServiceAccount1', 'Org1ServiceAccount2']
        },
        {
            'name': 'Org2',
            'pks_accounts': ['Org2ServiceAccount']
        }
    ],
    'pks_accounts': [
        {
            'name': 'Org1ServiceAccount1',
            'vc': 'vc1',
            'host': 'https://deadend-12345.eng.vmware.com',
            'port': '9021',
            'uaac': {
                'port': '8443',
                'secret': 'secret',
                'username': 'org1Admin'
            }
        },
        {
            'name': 'Org1ServiceAccount2',
            'vc': 'vc2',
            'host': 'https://deadend-12345.eng.vmware.com',
            'port': '9021',
            'uaac': {
                'port': '8443',
                'secret': 'secret',
                'username': 'org1Admin'
            }
        },
        {
            'name': 'Org2ServiceAccount',
            'vc': 'vc1',
            'host': 'https://deadend-12345.eng.vmware.com',
            'port': '9021',
            'uaac': {
                'port': '8443',
                'secret': 'secret',
                'username': 'org2Admin'
            }
        }
    ],
    'pvdcs': [
        {
            'name': 'pvdc1',
            'vc': 'vc1',
            'rp_paths': ['datacenter1/cluster1/rp1']
        },
        {
            'name': 'pvdc2',
            'vc': 'vc1',
            'rp_paths': ['HA_datacenter/HA_cluster1/gold_rp/sub-rp']
        },
        {
            'name': 'pvdc3',
            'vc': 'vc2',
            'rp_paths': ['datacenter/cluster1/rp1/sub-rp1/sub-rp2']
        }
    ]
}

SAMPLE_SERVICE_CONFIG = {
    'service': {
        'listeners': 5,
        'enforce_authorization': False
    }
}

SAMPLE_TEMPLATE_PHOTON_V2 = {
    'name': 'photon-v2',
    'catalog_item': 'photon-custom-hw11-2.0-304b817-k8s',
    'source_ova_name': 'photon-custom-hw11-2.0-304b817.ova',
    'source_ova': 'http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova',  # noqa
    'sha256_ova': 'cb51e4b6d899c3588f961e73282709a0d054bb421787e140a1d80c24d4fd89e1',  # noqa
    'temp_vapp': 'photon2-temp',
    'cleanup': True,
    'cpu': 2,
    'mem': 2048,
    'admin_password': 'guest_os_admin_password',
    'description': 'PhotonOS v2\nDocker 17.06.0-4\nKubernetes 1.9.1\nweave 2.3.0'  # noqa
}

SAMPLE_TEMPLATE_UBUNTU_16_04 = {
    'name': 'ubuntu-16.04',
    'catalog_item': 'ubuntu-16.04-server-cloudimg-amd64-k8s',
    'source_ova_name': 'ubuntu-16.04-server-cloudimg-amd64.ova',
    'source_ova': 'https://cloud-images.ubuntu.com/releases/xenial/release-20180418/ubuntu-16.04-server-cloudimg-amd64.ova',  # noqa
    'sha256_ova': '3c1bec8e2770af5b9b0462e20b7b24633666feedff43c099a6fb1330fcc869a9',  # noqa
    'temp_vapp': 'ubuntu1604-temp',
    'cleanup': True,
    'cpu': 2,
    'mem': 2048,
    'admin_password': 'guest_os_admin_password',
    'description': 'Ubuntu 16.04\nDocker 18.03.0~ce\nKubernetes 1.10.1\nweave 2.3.0'  # noqa
}

SAMPLE_BROKER_CONFIG = {
    'broker': {
        'type': 'default',
        'org': 'Admin',
        'vdc': 'Catalog',
        'catalog': 'cse',
        'network': 'admin_network',
        'ip_allocation_mode': 'pool',
        'storage_profile': '*',
        'default_template': SAMPLE_TEMPLATE_PHOTON_V2['name'],
        'templates': [SAMPLE_TEMPLATE_PHOTON_V2, SAMPLE_TEMPLATE_UBUNTU_16_04],
        'cse_msg_dir': '/tmp/cse'
    }
}

# This allows us to compare top-level config keys and value types
SAMPLE_CONFIG = {**SAMPLE_AMQP_CONFIG, **SAMPLE_VCD_CONFIG,
                 **SAMPLE_VCS_CONFIG, **SAMPLE_SERVICE_CONFIG,
                 **SAMPLE_BROKER_CONFIG}


def generate_sample_config(output=None, pks_output=None):
    """Generate sample configs for cse.

    If config file names are
    provided, configs are dumped into respective files.

    :param str output: name of the config file to dump the CSE configs.
    :param str pks_output: name of the PKS config file to dump the PKS
    configs.

    :return: sample config/ sample config files

    :rtype: dict
    """
    sample_config = yaml.safe_dump(SAMPLE_AMQP_CONFIG,
                                   default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_VCD_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_VCS_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_SERVICE_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_BROKER_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += NOTE_FOR_PKS_KEY_IN_CONFIG_FILE
    sample_config += yaml.safe_dump(SAMPLE_PKS_CONFIG_FILE_LOCATION,
                                    default_flow_style=False) + '\n'
    sample_pks_config = yaml.safe_dump(SAMPLE_PKS_CONFIG,
                                       default_flow_style=False)

    if output is not None:
        with open(output, 'w') as f:
            f.write(sample_config)
    if pks_output is not None:
        with open(pks_output, 'w') as f:
            pks_config_string = yaml.safe_dump(SAMPLE_PKS_CONFIG,
                                               default_flow_style=False)
            f.write(f"{INSTRUCTIONS_FOR_PKS_CONFIG_FILE}\n{pks_config_string}")

    return sample_config.strip() + '\n\n' + PKS_CONFIG_NOTE + '\n' + \
        sample_pks_config.strip()


def get_validated_config(config_file_name):
    """Get the config file as a dictionary and check for validity.

    Ensures that all properties exist and all values are the expected type.
    Checks that AMQP connection is available, and vCD/VCs are valid.
    Does not guarantee that CSE has been installed according to this
    config file.

    :param str config_file_name: path to config file.

    :return: CSE config

    :rtype: dict

    :raises KeyError: if config file has missing or extra properties.
    :raises ValueError: if the value type for a config file property
        is incorrect.
    :raises AmqpConnectionError: if AMQP connection failed.
    """
    check_file_permissions(config_file_name)
    with open(config_file_name) as config_file:
        config = yaml.safe_load(config_file)
    pks_config = config.get('pks_config')
    # Basic validation of Configs
    click.secho(f"Validating config file '{config_file_name}'", fg='yellow')
    if 'pks_config' in config:
        del config['pks_config']
    check_keys_and_value_types(config, SAMPLE_CONFIG,
                               location='config file')
    validate_amqp_config(config['amqp'])
    validate_vcd_and_vcs_config(config['vcd'], config['vcs'])
    validate_broker_config(config['broker'])
    check_keys_and_value_types(config['service'],
                               SAMPLE_SERVICE_CONFIG['service'],
                               location="config file 'service' section")
    click.secho(f"Config file '{config_file_name}' is valid", fg='green')
    # Validation of optional configs if present
    if isinstance(pks_config, str):
        check_file_permissions(pks_config)
        with open(pks_config) as f:
            pks = yaml.safe_load(f)
        click.secho(f"Validating PKS config file '{pks_config}'", fg='yellow')
        check_keys_and_value_types(pks, SAMPLE_PKS_CONFIG,
                                   location='PKS config file')
        click.secho(f"PKS Config file '{pks_config}' is valid", fg='green')
        config['pks_config'] = pks
    else:
        config['pks_config'] = None

    return config


def validate_amqp_config(amqp_dict):
    """Ensure that 'amqp' section of config is correct.

    Checks that 'amqp' section of config has correct keys and value types.
    Also ensures that connection to AMQP server is valid.

    :param dict amqp_dict: 'amqp' section of config file as a dict.

    :raises KeyError: if @amqp_dict has missing or extra properties.
    :raises ValueError: if the value type for an @amqp_dict property
        is incorrect.
    :raises AmqpConnectionError: if AMQP connection failed.
    """
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


def validate_vcd_and_vcs_config(vcd_dict, vcs):
    """Ensure that 'vcd' and vcs' section of config are correct.

    Checks that 'vcd' and 'vcs' section of config have correct keys and value
    types. Also checks that vCD and all registered VCs in vCD are accessible.

    :param dict vcd_dict: 'vcd' section of config file as a dict.
    :param list vcs: 'vcs' section of config file as a list of dicts.

    :raises KeyError: if @vcd_dict or a vc in @vcs has missing or
        extra properties.
    :raises: ValueError: if the value type for a @vcd_dict or vc property
        is incorrect, or if vCD has a VC that is not listed in the config file.
    """
    check_keys_and_value_types(vcd_dict, SAMPLE_VCD_CONFIG['vcd'],
                               location="config file 'vcd' section")
    if not vcd_dict['verify']:
        click.secho('InsecureRequestWarning: Unverified HTTPS request is '
                    'being made. Adding certificate verification is '
                    'strongly advised.', fg='yellow', err=True)
        requests.packages.urllib3.disable_warnings()

    client = None
    try:
        # TODO() we get an error during client initialization if the specified
        # logfile points to the directory which doesn't exist. This issue
        # should be fixed in pyvcloud, where the logging setup creates
        # directories used in the log filepath if they do not exist yet.
        setup_log_file_directory()
        client = Client(vcd_dict['host'],
                        api_version=vcd_dict['api_version'],
                        verify_ssl_certs=vcd_dict['verify'],
                        log_file=SERVER_DEBUG_WIRELOG_FILEPATH,
                        log_requests=True,
                        log_headers=True,
                        log_bodies=True)
        client.set_credentials(BasicLoginCredentials(vcd_dict['username'],
                                                     SYSTEM_ORG_NAME,
                                                     vcd_dict['password']))
        click.secho(f"Connected to vCloud Director "
                    f"({vcd_dict['host']}:{vcd_dict['port']})", fg='green')

        for index, vc in enumerate(vcs, 1):
            check_keys_and_value_types(vc, SAMPLE_VCS_CONFIG['vcs'][0],
                                       location=f"config file 'vcs' section,"
                                                f" "f"vc #{index}")

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


def validate_broker_config(broker_dict):
    """Ensure that 'broker' section of config is correct.

    Checks that 'broker' section of config has correct keys and value
    types. Also checks that 'default_broker' property is a valid template.

    :param dict broker_dict: 'broker' section of config file as a dict.

    :raises KeyError: if @broker_dict has missing or extra properties.
    :raises ValueError: if the value type for a @broker_dict property is
        incorrect, or if 'default_template' has a value not listed in the
        'templates' property.
    """
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


def check_cse_installation(config, check_template='*'):
    """Ensure that CSE is installed on vCD according to the config file.

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
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=SERVER_DEBUG_WIRELOG_FILEPATH,
                        log_requests=True,
                        log_headers=True,
                        log_bodies=True)
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
        except Exception:  # TODO() replace raw exception with specific
            msg = f"Could not connect to AMQP exchange '{amqp['exchange']}'"
            click.secho(msg, fg='red')
            err_msgs.append(msg)
        finally:
            if connection is not None:
                connection.close()

        # check that CSE is registered to vCD correctly
        ext = APIExtension(client)
        try:
            cse_info = ext.get_extension(CSE_SERVICE_NAME,
                                         namespace=CSE_SERVICE_NAMESPACE)
            rkey_matches = cse_info['routingKey'] == amqp['routing_key']
            exchange_matches = cse_info['exchange'] == amqp['exchange']
            if not rkey_matches or not exchange_matches:
                msg = "CSE is registered as an extension, but the extension " \
                      "settings on vCD are not the same as config settings."
                if not rkey_matches:
                    msg += f"\nvCD-CSE routing key: {cse_info['routingKey']}" \
                           f"\nCSE config routing key: {amqp['routing_key']}"
                if not exchange_matches:
                    msg += f"\nvCD-CSE exchange: {cse_info['exchange']}" \
                           f"\nCSE config exchange: {amqp['exchange']}"
                click.secho(msg, fg='yellow')
                err_msgs.append(msg)
            if cse_info['enabled'] == 'true':
                click.secho("CSE on vCD is currently enabled", fg='green')
            else:
                click.secho("CSE on vCD is currently disabled", fg='yellow')
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
                if check_template != '*' \
                        and check_template != template['name']:
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


def install_cse(ctx, config_file_name='config.yaml', template_name='*',
                update=False, no_capture=False, ssh_key=None,
                ext_install='prompt'):
    """Handle logistics for CSE installation.

    Handles decision making for configuring AMQP exchange/settings,
    extension registration, catalog setup, and template creation.

    :param click.core.Context ctx:
    :param str config_file_name: config file name.
    :param str template_name: which templates to create/update. A value of '*'
        means to create/update all templates specified in config file.
    :param bool update: if True and templates already exist in vCD,
        overwrites existing templates.
    :param bool no_capture: if True, temporary vApp will not be captured or
        destroyed, so the user can ssh into and debug the VM.
    :param str ssh_key: public ssh key to place into template vApp(s).
    :param str ext_install: 'prompt' asks the user if CSE should be registered
        to vCD. 'skip' does not register CSE to vCD. 'config' registers CSE
        to vCD without asking the user.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    config = get_validated_config(config_file_name)
    configure_install_logger()
    msg = f"Installing CSE on vCloud Director using config file " \
          f"'{config_file_name}'"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)
    client = None
    try:
        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=INSTALL_LOG_FILEPATH,
                        log_requests=True,
                        log_headers=True,
                        log_bodies=True)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        click.secho(msg, fg='green')
        LOGGER.info(msg)

        # create amqp exchange if it doesn't exist
        amqp = config['amqp']
        create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                             amqp['vhost'], amqp['ssl'], amqp['username'],
                             amqp['password'])

        # register cse as extension to vCD
        if should_register_cse(client, routing_key=amqp['routing_key'],
                               exchange=amqp['exchange'],
                               ext_install=ext_install):
            register_cse(client, amqp['routing_key'], amqp['exchange'])

        # register rights to vCD
        # TODO() should also remove rights when unregistering CSE
        if is_cse_registered(client):
            register_right(client, right_name=CSE_NATIVE_DEPLOY_RIGHT_NAME,
                           description=CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION,
                           category=CSE_NATIVE_DEPLOY_RIGHT_CATEGORY,
                           bundle_key=CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY)
            register_right(client, right_name=CSE_PKS_DEPLOY_RIGHT_NAME,
                           description=CSE_PKS_DEPLOY_RIGHT_DESCRIPTION,
                           category=CSE_PKS_DEPLOY_RIGHT_CATEGORY,
                           bundle_key=CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY)

        # set up cse catalog
        org = get_org(client, org_name=config['broker']['org'])
        create_and_share_catalog(org, config['broker']['catalog'],
                                 catalog_desc='CSE templates')
        # create, customize, capture VM templates
        for template in config['broker']['templates']:
            if template_name == '*' or template['name'] == template_name:
                create_template(ctx, client, config, template, update=update,
                                no_capture=no_capture, ssh_key=ssh_key,
                                org=org)
    except Exception:
        click.secho("CSE Installation Error. Check CSE install logs", fg='red')
        LOGGER.error("CSE Installation Error", exc_info=True)
        raise  # TODO() need installation relevant exceptions for rollback
    finally:
        if client is not None:
            client.logout()


def create_template(ctx, client, config, template_config, update=False,
                    no_capture=False, ssh_key=None, org=None, vdc=None):
    """Handle template creation phase during CSE installation.

    :param click.core.Context ctx: click context object.
    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template section of @config.
    :param bool update: if True and templates already exist in vCD, overwrites
        existing templates.
    :param bool no_capture: if True, temporary vApp will not be captured or
        destroyed, so the user can ssh into the VM and debug.
    :param str ssh_key: public ssh key to place into the template vApp(s).
    :param pyvcloud.vcd.org.Org org: specific org to use. If None, uses org
        specified in @config.
    :param pyvcloud.vcd.vdc.VDC vdc: specific vdc to use. If None, uses vdc
        specified in @config.
    """
    if org is None:
        org = get_org(client, org_name=config['broker']['org'])
    if vdc is None:
        vdc = get_vdc(client, config['broker']['vdc'], org=org)
    ctx.obj = {'client': client}
    catalog_name = config['broker']['catalog']
    template_name = template_config['catalog_item']
    vapp_name = template_config['temp_vapp']
    ova_name = template_config['source_ova_name']

    if not update and catalog_item_exists(org, catalog_name, template_name):
        msg = f"Found template '{template_name}' in catalog '{catalog_name}'"
        click.secho(msg, fg='green')
        LOGGER.info(msg)
        return

    # if update flag is set, delete existing template/ova file/temp vapp
    if update:
        msg = f"--update flag set. If template, source ova file, " \
              f"and temporary vApp exist, they will be deleted"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        try:
            org.delete_catalog_item(catalog_name, template_name)
            wait_for_catalog_item_to_resolve(client, catalog_name,
                                             template_name, org=org)
            org.reload()
            msg = "Deleted vApp template"
            click.secho(msg, fg='green')
            LOGGER.info(msg)
        except EntityNotFoundException:
            pass
        try:
            org.delete_catalog_item(catalog_name, ova_name)
            wait_for_catalog_item_to_resolve(client, catalog_name, ova_name,
                                             org=org)
            org.reload()
            msg = "Deleted ova file"
            click.secho(msg, fg='green')
            LOGGER.info(msg)
        except EntityNotFoundException:
            pass
        try:
            task = vdc.delete_vapp(vapp_name, force=True)
            stdout(task, ctx=ctx)
            vdc.reload()
            msg = "Deleted temporary vApp"
            click.secho(msg, fg='green')
            LOGGER.info(msg)
        except EntityNotFoundException:
            pass

    # if needed, upload ova and create temp vapp
    msg = f"Creating template '{template_name}' in catalog '{catalog_name}'"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)
    temp_vapp_exists = True
    try:
        vapp = VApp(client, resource=vdc.get_vapp(vapp_name))
        msg = f"Found vApp '{vapp_name}'"
        click.secho(msg, fg='green')
        LOGGER.info(msg)
    except EntityNotFoundException:
        temp_vapp_exists = False

    # flag is used to hide previous try/except error if an error occurs below
    if not temp_vapp_exists:
        if catalog_item_exists(org, catalog_name, ova_name):
            msg = f"Found ova file '{ova_name}' in catalog '{catalog_name}'"
            click.secho(msg, fg='green')
            LOGGER.info(msg)
        else:
            # download/upload files to catalog if necessary
            ova_filepath = f"cse_cache/{ova_name}"
            download_file(template_config['source_ova'], ova_filepath,
                          sha256=template_config['sha256_ova'], logger=LOGGER)
            upload_ova_to_catalog(client, catalog_name, ova_filepath, org=org,
                                  logger=LOGGER)

        vapp = _create_temp_vapp(ctx, client, vdc, config, template_config,
                                 ssh_key)

    if no_capture:
        msg = f"'--no-capture' flag set. " \
              f"Not capturing vApp '{vapp.name}' as a template"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        return

    # capture temp vapp as template
    msg = f"Creating template '{template_name}' from vApp '{vapp.name}'"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)
    capture_vapp_to_template(ctx, vapp, catalog_name, template_name,
                             org=org, desc=template_config['description'],
                             power_on=not template_config['cleanup'])
    msg = f"Created template '{template_name}' from vApp '{vapp_name}'"
    click.secho(msg, fg='green')
    LOGGER.info(msg)

    # delete temp vapp
    if template_config['cleanup']:
        msg = f"Deleting vApp '{vapp_name}'"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        task = vdc.delete_vapp(vapp_name, force=True)
        stdout(task, ctx=ctx)
        vdc.reload()
        msg = f"Deleted vApp '{vapp_name}'"
        click.secho(msg, fg='green')
        LOGGER.info(msg)


def _create_temp_vapp(ctx, client, vdc, config, template_config, ssh_key):
    """Handle temporary VApp creation and customization step of CSE install.

    Initializes and customizes VApp.

    :param click.core.Context ctx: click context object.
    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template config section of @config.
    :param str ssh_key: ssh key to use in temporary VApp's VM. Can be None.

    :return: VApp object for temporary VApp.

    :rtype: pyvcloud.vcd.vapp.VApp

    :raises FileNotFoundError: if init/customization scripts are not found.
    :raises Exception: if VM customization fails.
    """
    vapp_name = template_config['temp_vapp']
    init_script = get_data_file(f"init-{template_config['name']}.sh",
                                logger=LOGGER)
    if ssh_key is not None:
        init_script += \
            f"""
            mkdir -p /root/.ssh
            echo '{ssh_key}' >> /root/.ssh/authorized_keys
            chmod -R go-rwx /root/.ssh
            """
    msg = f"Creating vApp '{vapp_name}'"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)
    vapp = _create_vapp_from_config(client, vdc, config, template_config,
                                    init_script)
    msg = f"Created vApp '{vapp_name}'"
    click.secho(msg, fg='green')
    LOGGER.info(msg)
    msg = f"Customizing vApp '{vapp_name}'"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)
    cust_script = get_data_file(f"cust-{template_config['name']}.sh",
                                logger=LOGGER)
    ova_name = template_config['source_ova_name']
    is_photon = True if 'photon' in ova_name else False
    _customize_vm(ctx, config, vapp, vapp.name, cust_script,
                  is_photon=is_photon)
    msg = f"Customized vApp '{vapp_name}'"
    click.secho(msg, fg='green')
    LOGGER.info(msg)

    return vapp


def _create_vapp_from_config(client, vdc, config, template_config,
                             init_script):
    """Create a VApp from a specific template config.

    This vApp is intended to be captured as a vApp template for CSE.
    Fence mode and network adapter type are fixed.

    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template section of CSE config.
    :param str init_script: initialization script for VApp.

    :return: initialized VApp object.

    :rtype: pyvcloud.vcd.vapp.VApp
    """
    vapp_sparse_resource = vdc.instantiate_vapp(
        template_config['temp_vapp'],
        config['broker']['catalog'],
        template_config['source_ova_name'],
        network=config['broker']['network'],
        fence_mode=TEMP_VAPP_FENCE_MODE,
        ip_allocation_mode=config['broker']['ip_allocation_mode'],
        network_adapter_type=TEMP_VAPP_NETWORK_ADAPTER_TYPE,
        deploy=True,
        power_on=True,
        memory=template_config['mem'],
        cpu=template_config['cpu'],
        password=None,
        cust_script=init_script,
        accept_all_eulas=True,
        vm_name=template_config['temp_vapp'],
        hostname=template_config['temp_vapp'],
        storage_profile=config['broker']['storage_profile'])
    task = vapp_sparse_resource.Tasks.Task[0]
    client.get_task_monitor().wait_for_success(task)
    vdc.reload()
    # we don't do lazy loading here using vapp_sparse_resource.get('href'),
    # because VApp would have an uninitialized attribute (vapp.name)
    vapp = VApp(client, resource=vapp_sparse_resource)
    vapp.reload()
    return vapp


def _customize_vm(ctx, config, vapp, vm_name, cust_script, is_photon=False):
    """Customize a VM in a VApp using the customization script @cust_script.

    :param click.core.Context ctx: click context object. Needed to pass to
        stdout.
    :param dict config: CSE config.
    :param pyvcloud.vcd.vapp.VApp vapp:
    :param str vm_name:
    :param str cust_script: the customization script to run on
    :param bool is_photon: True if the vapp was instantiated from
        a 'photon' ova file, False otherwise (False is safe even if
        the vapp is photon-based).

    :raises Exception: if unable to execute the customization script in
        VSphere.
    """
    callback = vgr_callback(prepend_msg='Waiting for guest tools, status: "')
    if not is_photon:
        vs = get_vsphere(config, vapp, vm_name, logger=LOGGER)
        wait_until_tools_ready(vapp, vs, callback=callback)

        vapp.reload()
        task = vapp.shutdown()
        stdout(task, ctx=ctx)
        vapp.reload()
        task = vapp.power_on()
        stdout(task, ctx=ctx)
        vapp.reload()

    vs = get_vsphere(config, vapp, vm_name, logger=LOGGER)
    wait_until_tools_ready(vapp, vs, callback=callback)
    password_auto = vapp.get_admin_password(vm_name)

    try:
        result = vs.execute_script_in_guest(
            vs.get_vm_by_moid(vapp.get_vm_moid(vm_name)),
            'root',
            password_auto,
            cust_script,
            target_file=None,
            wait_for_completion=True,
            wait_time=10,
            get_output=True,
            delete_script=True,
            callback=vgr_callback())
    except Exception as err:
        # TODO() replace raw exception with specific exception
        # unsure all errors execute_script_in_guest can result in
        # Docker TLS handshake timeout can occur when internet is slow
        click.secho("Failed VM customization. Check CSE install log", fg='red')
        LOGGER.error(f"Failed VM customization with error: f{err}",
                     exc_info=True)
        raise

    if len(result) > 0:
        msg = f'Result: {result}'
        click.echo(msg)
        LOGGER.debug(msg)
        result_stdout = result[1].content.decode()
        result_stderr = result[2].content.decode()
        msg = 'stderr:'
        click.echo(msg)
        LOGGER.debug(msg)
        if len(result_stderr) > 0:
            click.echo(result_stderr)
            LOGGER.debug(result_stderr)
        msg = 'stdout:'
        click.echo(msg)
        LOGGER.debug(msg)
        if len(result_stdout) > 0:
            click.echo(result_stdout)
            LOGGER.debug(result_stdout)
    if len(result) == 0 or result[0] != 0:
        msg = "Failed VM customization"
        click.secho(f"{msg}. Check CSE install log", fg='red')
        LOGGER.error(msg, exc_info=True)
        # TODO() replace raw exception with specific exception
        raise Exception(msg)


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


def create_amqp_exchange(exchange_name, host, port, vhost, use_ssl,
                         username, password):
    """Create the specified AMQP exchange if it does not exist.

    If specified AMQP exchange exists already, does nothing.

    :param str exchange_name: The AMQP exchange name to check for or create.
    :param str host: AMQP host name.
    :param str password: AMQP password.
    :param int port: AMQP port number.
    :param bool use_ssl: Enable ssl.
    :param str username: AMQP username.
    :param str vhost: AMQP vhost.

    :raises AmqpError: if AMQP exchange could not be created.
    """
    msg = f"Checking for AMQP exchange '{exchange_name}'"
    click.secho(msg, fg='yellow')
    LOGGER.info(msg)
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, port, vhost, credentials,
                                           ssl=use_ssl, connection_attempts=3,
                                           retry_delay=2, socket_timeout=5)
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name,
                                 exchange_type=EXCHANGE_TYPE,
                                 durable=True, auto_delete=False)
    except Exception as err:
        msg = f"Cannot create AMQP exchange '{exchange_name}'"
        click.secho(msg, fg='red')
        LOGGER.error(msg, exc_info=True)
        raise AmqpError(msg, str(err))
    finally:
        if connection is not None:
            connection.close()
    msg = f"AMQP exchange '{exchange_name}' is ready"
    click.secho(msg, fg='green')
    LOGGER.info(msg)


def should_register_cse(client, routing_key, exchange, ext_install='prompt'):
    """Decides if CSE installation should register CSE to vCD.

    Returns False if @ext_install='skip' or if user declines
    registration/update. Will print relevant information about CSE on vCD
    if it is already registered.

    :param pyvcloud.vcd.client.Client client:
    :param str routing_key: routing_key to use for CSE
    :param str exchange: exchange to use for CSE
    :param str ext_install: 'skip' skips registration,
        'config' allows registration without prompting user,
        'prompt' asks user before registration.

    :return: boolean that signals whether we should register CSE to vCD.

    :rtype: bool
    """
    ext_config = {
        'routingKey': routing_key,
        'exchange': exchange
    }

    ext = APIExtension(client)
    cse_info = None
    try:
        cse_info = ext.get_extension_info(CSE_SERVICE_NAME,
                                          namespace=CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        pass

    if cse_info is None:
        msg = 'Register CSE to vCD?'
        if ext_install == 'skip' \
                or (ext_install == 'prompt' and not click.confirm(msg)):
            msg = 'CSE is not registered to vCD. Skipping API extension ' \
                  'registration'
            click.secho(msg, fg='yellow')
            LOGGER.warning(msg)
            return False
        return True

    # cse is already registered to vCD, but settings might be off
    diff_settings = [p for p, v in ext_config.items() if cse_info[p] != v]
    if diff_settings:
        msg = 'CSE on vCD has different settings than config file' \
              '\n\nCurrent CSE settings on vCD:'
        for setting in diff_settings:
            msg += f"\n{setting}: {cse_info[setting]}"

        msg += '\n\nCurrent config file settings:'
        for setting in diff_settings:
            msg += f"\n{setting}: {ext_config[setting]}"
        click.echo(msg)
        LOGGER.info(msg)

        msg = '\nUpdate CSE on vCD to match config file settings?'
        if ext_install == 'skip' \
                or (ext_install == 'prompt' and not click.confirm(msg)):
            msg = 'Skipping CSE registration to vCD. CSE on vCD has ' \
                  'different settings than config file'
            click.secho(msg, fg='yellow')
            LOGGER.warning(msg)
            return False
        return True

    # cse is already registered to vCD, and the settings match with config file
    msg = 'CSE is registered to vCD and has same settings as config file'
    click.secho(msg, fg='green')
    LOGGER.info(msg)
    return False


def register_cse(client, routing_key, exchange):
    """Register or update CSE on vCD.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.client.Client client:
    :param str routing_key:
    :param str exchange:
    """
    ext = APIExtension(client)
    patterns = [
        f'/api/{CSE_SERVICE_NAME}',
        f'/api/{CSE_SERVICE_NAME}/.*',
        f'/api/{CSE_SERVICE_NAME}/.*/.*'
    ]

    cse_info = None
    try:
        cse_info = ext.get_extension_info(CSE_SERVICE_NAME,
                                          namespace=CSE_SERVICE_NAMESPACE)
    except MissingRecordException:
        pass

    if cse_info is None:
        ext.add_extension(CSE_SERVICE_NAME, CSE_SERVICE_NAMESPACE, routing_key,
                          exchange, patterns)
        msg = f"Registered {CSE_SERVICE_NAME} as an API extension in vCD"
    else:
        ext.update_extension(CSE_SERVICE_NAME, namespace=CSE_SERVICE_NAMESPACE,
                             routing_key=routing_key, exchange=exchange)
        msg = f"Updated {CSE_SERVICE_NAME} API Extension in vCD"

    click.secho(msg, fg='green')
    LOGGER.info(msg)


def register_right(client, right_name, description, category, bundle_key):
    """Register a right for CSE.

    :param pyvcloud.vcd.client.Client client:
    :param str right_name: the name of the new right to be registered.
    :param str description: brief description about the new right.
    :param str category: add the right in existing categories in
        vCD Roles and Rights or specify a new category name.
    :param str bundle_key: is used to identify the right name and change
        its value to different languages using localization bundle.

    :raises BadRequestException: if a right with given name already
        exists in vCD.
    """
    ext = APIExtension(client)
    try:
        ext.add_service_right(right_name, CSE_SERVICE_NAME,
                              CSE_SERVICE_NAMESPACE, description, category,
                              bundle_key)

        msg = f"Register {right_name} as a Right in vCD"
        click.secho(msg, fg='green')
        LOGGER.info(msg)
    except BadRequestException as err:
        # TODO() replace string matching logic to look for specific right
        right_exists_msg = f'Right with name "{{{CSE_SERVICE_NAME}}}:' \
                           f'{right_name}" already exists'
        if right_exists_msg in str(err):
            msg = f"Right: {right_name} already exists in vCD"
            click.secho(msg, fg='green')
            LOGGER.debug(msg)
        else:
            raise err
