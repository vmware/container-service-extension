# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import logging
import traceback
from urllib.parse import urlparse

import click
import pika
import requests
import yaml
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import FenceMode
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from vcd_cli.utils import stdout
from vcd_cli.utils import to_dict
from vsphere_guest_run.vsphere import VSphere

from container_service_extension.consumer import EXCHANGE_TYPE
from container_service_extension.utils import bool_to_msg
from container_service_extension.utils import catalog_exists
from container_service_extension.utils import catalog_item_exists
from container_service_extension.utils import check_file_permissions
from container_service_extension.utils import check_keys_and_value_types
from container_service_extension.utils import CSE_EXT_NAME
from container_service_extension.utils import CSE_EXT_NAMESPACE
from container_service_extension.utils import download_file
from container_service_extension.utils import get_data_file
from container_service_extension.utils import get_org
from container_service_extension.utils import get_vdc
from container_service_extension.utils import get_vsphere
from container_service_extension.utils import upload_ova_to_catalog
from container_service_extension.utils import vgr_callback
from container_service_extension.utils import wait_until_tools_ready
from container_service_extension.utils import wait_for_catalog_item_to_resolve

LOGGER = logging.getLogger('cse.config')
TEMP_VAPP_NETWORK_ADAPTER_TYPE = 'vmxnet3'
TEMP_VAPP_FENCE_MODE = FenceMode.BRIDGED.value

SAMPLE_AMQP_CONFIG = {
    'amqp': {
        'host': 'amqp.vmware.com',
        'port': 5672,
        'prefix': 'vcd',
        'username': 'guest',
        'password': 'guest',
        'exchange': 'vcdext',
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
    'vcs': [{
        'name': 'vc1',
        'username': 'cse_user@vsphere.local',
        'password': 'my_secret_password',
        'verify': False
    }, {
        'name': 'vc2',
        'username': 'cse_user@vsphere.local',
        'password': 'my_secret_password',
        'verify': False
    }]
}

SAMPLE_SERVICE_CONFIG = {'service': {'listeners': 5}}

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


def generate_sample_config():
    """Generates a sample config file for cse.

    :return: sample config as dict.

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
    return sample_config.strip() + '\n'


def get_validated_config(config_file_name):
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
    :raises Exception: if AMQP connection failed.
    """
    check_file_permissions(config_file_name)
    with open(config_file_name) as config_file:
        config = yaml.safe_load(config_file)

    click.secho(f"Validating config file '{config_file_name}'", fg='yellow')
    check_keys_and_value_types(config, SAMPLE_CONFIG, location='config file')
    validate_amqp_config(config['amqp'])
    validate_vcd_and_vcs_config(config['vcd'], config['vcs'])
    validate_broker_config(config['broker'])
    check_keys_and_value_types(config['service'],
                               SAMPLE_SERVICE_CONFIG['service'],
                               location="config file 'service' section")
    click.secho(f"Config file '{config_file_name}' is valid", fg='green')
    return config


def validate_amqp_config(amqp_dict):
    """Ensures that 'amqp' section of config is correct.

    Checks that 'amqp' section of config has correct keys and value types.
    Also ensures that connection to AMQP server is valid.

    :param dict amqp_dict: 'amqp' section of config file as a dict.

    :raises KeyError: if @amqp_dict has missing or extra properties.
    :raises ValueError: if the value type for an @amqp_dict property
        is incorrect.
    :raises Exception: if AMQP connection failed.
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
        if not connection.is_open:
            click.secho(f"AMQP connection is not open", fg='red')
            # TODO replace raw exception with specific
            raise Exception('AMQP connection is not open')
        click.secho(f"Connected to AMQP server "
                    f"({amqp_dict['host']}:{amqp_dict['port']})", fg='green')
    finally:
        if connection is not None:
            connection.close()


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
        client = Client(vcd_dict['host'],
                        api_version=vcd_dict['api_version'],
                        verify_ssl_certs=vcd_dict['verify'],
                        log_file='cse-check.log',
                        log_headers=True,
                        log_bodies=True)
        client.set_credentials(BasicLoginCredentials(vcd_dict['username'],
                                                     'System',
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


def validate_broker_config(broker_dict):
    """Ensures that 'broker' section of config is correct.

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
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file='cse-check.log',
                        log_headers=True,
                        log_bodies=True)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            'System',
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
            cse_info = ext.get_extension(CSE_EXT_NAME,
                                         namespace=CSE_EXT_NAMESPACE)
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


def install_cse(ctx, config_file_name, template_name, update, no_capture,
                ssh_key, amqp_install, ext_install):
    click.secho('Installing CSE on vCD from file: %s, template: %s' %
                (config_file_name, template_name))
    config = get_validated_config(config_file_name)
    client = Client(
        config['vcd']['host'],
        api_version=config['vcd']['api_version'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file='cse-install.log',
        log_headers=True,
        log_bodies=True)
    client.set_credentials(
        BasicLoginCredentials(config['vcd']['username'], 'System',
                              config['vcd']['password']))
    click.echo('Connected to vCloud Director as system '
               'administrator (%s:%s): %s' % (config['vcd']['host'],
                                              config['vcd']['port'],
                                              bool_to_msg(True)))
    click.secho('Installing  \'%s\' service broker' % config['broker']['type'])
    if config['broker']['type'] == 'default':
        org_resource = client.get_org_by_name(config['broker']['org'])
        org = Org(client, resource=org_resource)
        click.echo('Find org \'%s\': %s' % (org.get_name(), bool_to_msg(True)))
        vdc_resource = org.get_vdc(config['broker']['vdc'])
        click.echo('Find vdc \'%s\': %s' % (vdc_resource.get('name'),
                                            bool_to_msg(True)))

        catalog_name = config['broker']['catalog']
        try:
            org.get_catalog(catalog_name)
            click.echo(f"Found catalog {catalog_name}")
        except EntityNotFoundException:
            click.secho(f"Creating catalog {catalog_name}", fg='green')
            org.create_catalog(catalog_name, 'CSE Catalog')
            org.reload()
            click.secho(f"Created catalog {catalog_name}", fg='blue')
        org.share_catalog(catalog_name)
        org.reload()

        for template in config['broker']['templates']:
            if template_name == '*' or template['name'] == template_name:
                create_template(ctx, client, config, template, update=update,
                                no_capture=no_capture, ssh_key=ssh_key)


def create_template(ctx, client, config, template_config, update=False,
                    no_capture=False, ssh_key=None):
    """Handles template creation phase during CSE installation.

    :param click.core.Context ctx: click context object.
    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template section of @config.
    :param bool update: if True and templates already exist in vCD, overwrites
        existing templates.
    :param bool no_capture: if True, temporary vApp will not be captured or
        destroyed, so the user can ssh into the VM and debug.
    :param str ssh_key: public ssh key to place into the template vApp(s).
    """
    org_name = config['broker']['org']
    vdc_name = config['broker']['vdc']
    org = get_org(client, org_name=org_name)
    vdc = get_vdc(client, vdc_name, org_name=org_name)
    ctx.obj = {'client': client}
    catalog_name = config['broker']['catalog']
    template_name = template_config['catalog_item']
    vapp_name = template_config['temp_vapp']
    ova_name = template_config['source_ova_name']
    ova_url = template_config['source_ova']

    if not update and catalog_item_exists(org, catalog_name, template_name):
        click.secho(f"Found template '{template_name}' in catalog "
                    f"'{catalog_name}'", fg='green')
        return

    # if update flag is set, delete existing template/ova file/temp vapp
    if update:
        click.secho(f"Update flag set. If template, source ova file, and "
                    f"temporary vApp exist, they will be deleted", fg='yellow')
        try:
            org.delete_catalog_item(catalog_name, template_name)
            wait_for_catalog_item_to_resolve(client, catalog_name,
                                             template_name, org_name=org_name)
            org.reload()
            click.secho("Deleted vApp template", fg='green')
        except EntityNotFoundException:
            pass
        try:
            org.delete_catalog_item(catalog_name, ova_name)
            wait_for_catalog_item_to_resolve(client, catalog_name,
                                             ova_name, org_name=org_name)
            org.reload()
            click.secho("Deleted ova file", fg='green')
        except EntityNotFoundException:
            pass
        try:
            task = vdc.delete_vapp(vapp_name, force=True)
            stdout(task, ctx=ctx)
            vdc.reload()
            click.secho("Deleted temporary vApp", fg='green')
        except EntityNotFoundException:
            pass

    click.secho(f"Creating template '{template_name}' in catalog "
                f"'{catalog_name}'", fg='yellow')
    try:
        vapp = VApp(client, resource=vdc.get_vapp(vapp_name))
        click.secho(f"Found vApp '{vapp_name}'", fg='green')
    except EntityNotFoundException:
        if catalog_item_exists(org, catalog_name, ova_name):
            click.secho(f"Found ova file '{ova_name}' in catalog "
                        f"'{catalog_name}'", fg='green')
        else:
            # download/upload files to catalog if necessary
            ova_filepath = f"cse_cache/{ova_name}"
            download_file(ova_url, ova_filepath,
                          sha256=template_config['sha256_ova'])
            upload_ova_to_catalog(client, catalog_name, ova_filepath,
                                  org_name=org_name)

        vapp = _create_temp_vapp(ctx, client, config, template_config, ssh_key)

    if no_capture:
        click.secho(f"'no-capture' flag set. Not capturing vApp '{vapp.name}' "
                    f"as a template", fg='yellow')
        return

    click.secho(f"Creating template '{template_name}' from vApp '{vapp.name}'",
                fg='yellow')
    capture_vapp_to_template(ctx, vapp, catalog_name, template_name,
                             desc=template_config['description'],
                             power_on=not template_config['cleanup'],
                             org_name=org_name)
    click.secho(f"Created template '{template_name}' from vApp '{vapp_name}'",
                fg='green')

    if template_config['cleanup']:
        click.secho(f"Deleting vApp '{vapp_name}'", fg='yellow')
        task = vdc.delete_vapp(vapp_name, force=True)
        stdout(task, ctx=ctx)
        vdc.reload()
        click.secho(f"Deleted vApp '{vapp_name}'", fg='green')


def _create_temp_vapp(ctx, client, config, template_config, ssh_key):
    """Handles temporary VApp creation and customization step of CSE install.

    Initializes and customizes VApp.

    :param click.core.Context ctx: click context object.
    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template config section of @config.
    :param str ssh_key: ssh key to use in temporary VApp's VM. Can be None.

    :return: VApp object for temporary VApp.

    :rtype: pyvcloud.vcd.vapp.VApp
    """
    vapp_name = template_config['temp_vapp']
    init_script = get_data_file(f"init-{template_config['name']}.sh")
    if ssh_key is not None:
        init_script += \
            f"""
            mkdir -p /root/.ssh
            echo '{ssh_key}' >> /root/.ssh/authorized_keys
            chmod -R go-rwx /root/.ssh
            """
    click.secho(f"Creating vApp '{vapp_name}'", fg='yellow')
    vapp = _create_vapp_from_config(client, config, template_config,
                                    init_script)
    click.secho(f"Created vApp '{vapp_name}'", fg='green')

    click.secho(f"Customizing vApp '{vapp_name}'", fg='yellow')
    cust_script = get_data_file(f"cust-{template_config['name']}.sh")
    ova_name = template_config['source_ova_name']
    is_photon = True if 'photon' in ova_name else False
    _customize_vm(ctx, config, vapp, vapp.name, cust_script,
                  is_photon=is_photon)
    click.secho(f"Customized vApp '{vapp_name}'", fg='green')

    return vapp


def _create_vapp_from_config(client, config, template_config, init_script):
    """Creates a VApp from a specific template config.

    This vApp is intended to be captured as a vApp template for CSE.
    Fence mode and network adapter type are fixed.

    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template section of CSE config.
    :param str init_script: initialization script for VApp.

    :return: initialized VApp object.

    :rtype: pyvcloud.vcd.vapp.VApp
    """
    vdc = get_vdc(client, config['broker']['vdc'],
                  org_name=config['broker']['org'])
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
    vapp = VApp(client, resource=vapp_sparse_resource)
    vapp.reload()
    return vapp


def _customize_vm(ctx, config, vapp, vm_name, cust_script, is_photon=False):
    """Customizes a VM in a VApp using the customization script @cust_script.

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
        vs = get_vsphere(config, vapp, vm_name)
        wait_until_tools_ready(vapp, vs, callback=callback)

        vapp.reload()
        task = vapp.shutdown()
        stdout(task, ctx=ctx)
        vapp.reload()
        task = vapp.power_on()
        stdout(task, ctx=ctx)
        vapp.reload()

    vs = get_vsphere(config, vapp, vm_name)
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
    except Exception:
        # TODO replace raw exception with specific exception
        # unsure what exception execute_script_in_guest can throw
        LOGGER.error(traceback.format_exc())
        click.secho(traceback.format_exc(), fg='red')
        raise

    if len(result) > 0:
        click.secho('Result: %s' % result)
        result_stdout = result[1].content.decode()
        result_stderr = result[2].content.decode()
        click.secho('stderr:')
        if len(result_stderr) > 0:
            click.secho(result_stderr, err=True)
        click.secho('stdout:')
        if len(result_stdout) > 0:
            click.secho(result_stdout, err=False)
    if len(result) == 0 or result[0] != 0:
        msg = 'Failed to customize VM'
        click.secho(msg, fg='red')
        # TODO replace raw exception with specific exception
        raise Exception(msg)


def capture_vapp_to_template(ctx, vapp, catalog_name, catalog_item_name,
                             desc='', power_on=False, org_name=None):
    """Shutdown and capture existing VApp as a template in @catalog.

    VApp should have tools ready, or shutdown will fail, and VApp will be
    unavailable to be captured.

    :param click.core.Context ctx: click context object needed for stdout.
    :param pyvcloud.vcd.vapp.VApp vapp:
    :param str catalog_name:
    :param str catalog_item_name: catalog item name for the template.
    :param str desc: template description.
    :param bool power_on: if True, turns on VApp after capturing.
    :param str org_name: which org to use. If None, uses currently logged-in
        org from @client.

    :raises EntityNotFoundException: if the org could not be found.
    """
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
    vapp.reload()

    if power_on:
        task = vapp.power_on()
        stdout(task, ctx=ctx)
        vapp.reload()


def should_configure_amqp(client, amqp_config, amqp_install):
    """Handles the logic in deciding whether CSE installation should
    configure vCD AMQP settings/exchange

    :param pyvcloud.vcd.client.Client client:
    :param dict amqp_config: The 'amqp' section of the config file
    :param str amqp_install: One of: prompt/skip/config

    :return: boolean that signals whether we should configure AMQP settings

    :rtype: bool
    """
    if amqp_install == 'skip':
        return False

    amqp_service = AmqpService(client)
    current_settings = to_dict(amqp_service.get_settings())
    amqp = {
        'AmqpExchange': amqp_config['exchange'],
        'AmqpHost': amqp_config['host'],
        'AmqpPort': str(amqp_config['port']),
        'AmqpPrefix': amqp_config['prefix'],
        'AmqpSslAcceptAll': str(amqp_config['ssl_accept_all']).lower(),
        'AmqpUseSSL': str(amqp_config['ssl']).lower(),
        'AmqpUsername': amqp_config['username'],
        'AmqpVHost': amqp_config['vhost']
    }

    diff_settings = [k for k, v in current_settings.items() if amqp[k] != v]
    if diff_settings:
        click.echo('current vCD AMQP setting:')
        for setting in diff_settings:
            click.echo(f"{setting}: {current_settings[setting]}")
        click.echo('\nconfig AMQP setting:')
        for setting in diff_settings:
            click.echo(f"{setting}: {amqp[setting]}")
        prompt_msg = '\nConfigure AMQP with the config file settings?'
    else:
        click.echo('vCD and config AMQP settings are the same')
        prompt_msg = f"\nConfigure/create AMQP exchange " \
                     f"'{amqp_config['exchange']}'?"

    if amqp_install == 'prompt' and not click.confirm(prompt_msg):
        return False

    return True


def configure_amqp(client, amqp_config):
    """Configures vCD AMQP settings/exchange to match those in the config file

    :param pyvcloud.vcd.client.Client client:
    :param dict amqp_config: The 'amqp' section of the config file
    """
    amqp_service = AmqpService(client)
    amqp = {
        'AmqpExchange': amqp_config['exchange'],
        'AmqpHost': amqp_config['host'],
        'AmqpPort': amqp_config['port'],
        'AmqpPrefix': amqp_config['prefix'],
        'AmqpSslAcceptAll': amqp_config['ssl_accept_all'],
        'AmqpUseSSL': amqp_config['ssl'],
        'AmqpUsername': amqp_config['username'],
        'AmqpVHost': amqp_config['vhost']
    }

    # This block sets the AMQP setting values on the
    # vCD "System Administration Extensibility page"
    result = amqp_service.test_config(amqp, amqp_config['password'])
    click.echo(f"AMQP test settings, result: {result['Valid'].text}")
    if result['Valid'].text == 'true':
        amqp_service.set_config(amqp, amqp_config['password'])
        click.echo('Updated vCD AMQP configuration.')
    else:
        click.echo("Couldn't set vCD AMQP configuration.")

    # Simply applying the AMQP settings to vCD does not mean that the
    # exchange exists or has been created. We have to go into the AMQP
    # connection and create the exchange.
    create_amqp_exchange(amqp_config['exchange'], amqp_config['username'],
                         amqp_config['password'], amqp_config['host'],
                         amqp_config['port'], amqp_config['vhost'],
                         amqp_config['ssl'])


def create_amqp_exchange(exchange_name, username, password, host, port, vhost,
                         use_ssl):
    """Checks if the specified AMQP exchange exists. If it doesn't exist,
    creates it

    :param str exchange_name: The AMQP exchange name to check for or create
    :param str username: AMQP username
    :param str password: AMQP password
    :param str host: AMQP host name
    :param int port: AMQP port number
    :param str vhost: AMQP vhost
    :param bool use_ssl: Enable ssl

    :raises Exception: if AMQP exchange cannot be created
    """
    click.echo(f"Checking for AMQP exchange '{exchange_name}'")
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, port, vhost, credentials,
                                           ssl=use_ssl, connection_attempts=3,
                                           retry_delay=2, socket_timeout=5)
    connection = pika.BlockingConnection(parameters)
    click.echo(f"Connected to AMQP server ({host}:{port}): "
               f"{bool_to_msg(connection.is_open)}")

    channel = connection.channel()
    try:
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=EXCHANGE_TYPE,
            durable=True,
            auto_delete=False)
    except Exception:
        LOGGER.error(traceback.format_exc())
        click.echo(f"Couldn't create exchange '{exchange_name}'")
    finally:
        connection.close()
    click.echo(f"AMQP exchange '{exchange_name}' created")


def register_extension(ctx, client, config, ext_install):
    if ext_install == 'skip':
        click.secho('Extension configuration: skipped')
        return
    ext = APIExtension(client)
    try:
        name = 'cse'
        cse_ext = ext.get_extension_info(name)
        click.secho('Find extension \'%s\', enabled=%s: %s' %
                    (name, cse_ext['enabled'], bool_to_msg(True)))
    except Exception:
        if ext_install == 'prompt':
            if not click.confirm('Do you want to register CSE as an API '
                                 'extension in vCD?'):
                click.secho('CSE not registered')
                return
        amqp = config['amqp']
        exchange = amqp['exchange']
        patterns = '/api/cse,/api/cse/.*,/api/cse/.*/.*'
        ext.add_extension(name, name, name, exchange, patterns.split(','))
        click.secho('Registered extension \'%s\': %s' % (name,
                                                         bool_to_msg(True)))
