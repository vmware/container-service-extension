# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import logging
import os
import time
import traceback
from urllib.parse import urlparse

import click
import pika
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import SIZE_1MB
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingRecordException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
import requests
from vcd_cli.utils import stdout
from vcd_cli.utils import to_dict
from vsphere_guest_run.vsphere import VSphere
import yaml

from container_service_extension.utils import bool_to_msg
from container_service_extension.utils import catalog_exists
from container_service_extension.utils import catalog_item_exists
from container_service_extension.utils import check_file_permissions
from container_service_extension.utils import check_keys_and_value_types
from container_service_extension.utils import create_and_share_catalog
from container_service_extension.utils import EXCHANGE_TYPE
from container_service_extension.utils import get_data_file
from container_service_extension.utils import get_sha256
from container_service_extension.utils import get_vsphere
from container_service_extension.utils import SYSTEM_ORG_NAME


LOGGER = logging.getLogger('cse.config')

# used for registering CSE to vCD
CSE_NAME = 'cse'
CSE_NAMESPACE = 'cse'

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
        except Exception:
            msg = f"Could not connect to AMQP exchange '{amqp['exchange']}'"
            click.secho(msg, fg='red')
            err_msgs.append(msg)
        finally:
            if connection is not None:
                connection.close()

        # check that CSE is registered to vCD
        ext = APIExtension(client)
        try:
            cse_info = ext.get_extension(CSE_NAME,
                                         namespace=CSE_NAMESPACE)
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
                catalog_item = template['catalog_item']
                if catalog_item_exists(org, catalog_name, catalog_item):
                    click.secho(f"Found template '{catalog_item}' in catalog "
                                f"'{catalog_name}'", fg='green')
                else:
                    msg = f"Template '{catalog_item}' not found in catalog " \
                          f"'{catalog_name}'"
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
                amqp_install='prompt', ext_install='prompt'):
    """Handles logistics for CSE installation.

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
    :param str amqp_install: 'prompt' asks the user if vCD AMQP should be
        configured. 'skip' does not configure vCD AMQP. 'config' configures
        vCD AMQP without asking the user.
    :param str ext_install: 'prompt' asks the user if CSE should be registered
        to vCD. 'skip' does not register CSE to vCD. 'config' registers CSE
        to vCD without asking the user.

    :raises Exception: if AMQP connection fails.
    """
    config = get_validated_config(config_file_name)
    click.secho(f"Installing CSE on vCloud Director using config file "
                f"'{config_file_name}'", fg='yellow')

    org_name = config['broker']['org']
    vdc_name = config['broker']['vdc']
    catalog_name = config['broker']['catalog']

    client = Client(config['vcd']['host'],
                    api_version=config['vcd']['api_version'],
                    verify_ssl_certs=config['vcd']['verify'],
                    log_file='cse-install.log',
                    log_headers=True,
                    log_bodies=True)
    client.set_credentials(BasicLoginCredentials(config['vcd']['username'],
                                                 SYSTEM_ORG_NAME,
                                                 config['vcd']['password']))
    click.secho(f"Connected to vCD as system administrator: "
                f"{config['vcd']['host']}:{config['vcd']['port']}", fg='green')
    org = Org(client, resource=client.get_org_by_name(org_name))
    click.secho(f"Found organization '{org_name}'", fg='green')
    vdc_resource = org.get_vdc(vdc_name)
    click.secho(f"Found VDC '{vdc_name}'", fg='green')

    # configure amqp
    amqp = config['amqp']
    create_amqp_exchange(amqp['exchange'], amqp['host'], amqp['port'],
                         amqp['vhost'], amqp['ssl'], amqp['username'],
                         amqp['password'])
    if should_configure_amqp(client, amqp, amqp_install):
        configure_vcd_amqp(client, amqp['exchange'], amqp['host'],
                           amqp['port'], amqp['prefix'],
                           amqp['ssl_accept_all'], amqp['ssl'],
                           amqp['vhost'], amqp['username'],
                           amqp['password'])

    # register cse as extension to vCD
    if should_register_cse(client, ext_install):
        register_cse(client, amqp['routing_key'], amqp['exchange'])

    # set up cse catalog
    catalog = create_and_share_catalog(org, catalog_name,
                                       catalog_desc='CSE templates')

    # create, customize, capture VM templates
    click.secho('Installing  \'%s\' service broker' % config['broker']['type'])
    if config['broker']['type'] == 'default':
        for template in config['broker']['templates']:
            if template_name == '*' or template['name'] == template_name:
                click.secho('Processing template: %s' % template['name'])
                k8s_template = None
                try:
                    k8s_template = org.get_catalog_item(
                        config['broker']['catalog'], template['catalog_item'])
                    click.echo('Find template \'%s\', \'%s\': %s' %
                               (config['broker']['catalog'],
                                template['catalog_item'],
                                bool_to_msg(k8s_template is not None)))
                except Exception:
                    pass
                try:
                    if k8s_template is None or update:
                        if update:
                            click.secho('Updating template')
                        else:
                            click.secho('Creating template')
                        create_template(ctx, config, client, org, vdc_resource,
                                        catalog, no_capture, template, ssh_key)
                        k8s_template = org.get_catalog_item(
                            config['broker']['catalog'],
                            template['catalog_item'])
                        if update:
                            click.echo('Updated template \'%s\', \'%s\': %s' %
                                       (config['broker']['catalog'],
                                        template['catalog_item'],
                                        bool_to_msg(k8s_template is not None)))
                        else:
                            click.echo('Find template \'%s\', \'%s\': %s' %
                                       (config['broker']['catalog'],
                                        template['catalog_item'],
                                        bool_to_msg(k8s_template is not None)))
                except Exception:
                    LOGGER.error(traceback.format_exc())
                    click.echo('Can\'t create or update template \'%s\' '
                               '\'%s\': %s' %
                               (template['name'], config['broker']['catalog'],
                                template['catalog_item']))

        click.echo(f'Start CSE with: \'cse run --config {config_file_name}\'')


def upload_source_ova(config, client, org, template):
    cse_cache_dir = os.path.join(os.getcwd(), 'cse_cache')
    cse_ova_file = os.path.join(cse_cache_dir, template['source_ova_name'])
    if not os.path.exists(cse_ova_file):
        if not os.path.isdir(cse_cache_dir):
            os.makedirs(cse_cache_dir)
        click.secho('Downloading %s' % template['source_ova_name'], fg='green')
        r = requests.get(template['source_ova'], stream=True)
        with open(cse_ova_file, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=SIZE_1MB):
                fd.write(chunk)
    if os.path.exists(cse_ova_file):
        sha256 = get_sha256(cse_ova_file)
        assert sha256 == template['sha256_ova']
        click.secho('Uploading %s' % template['source_ova_name'], fg='green')
        org.upload_ovf(
            config['broker']['catalog'],
            cse_ova_file,
            template['source_ova_name'],
            callback=None)
        return org.get_catalog_item(config['broker']['catalog'],
                                    template['source_ova_name'])
    else:
        return None


def wait_for_tools_ready_callback(message, exception=None):
    click.secho('waiting for guest tools, status: %s' % message)
    if exception is not None:
        click.secho('  exception: %s' % str(exception))


def wait_for_guest_execution_callback(message, exception=None):
    click.secho(message)
    if exception is not None:
        click.secho('  exception: %s' % str(exception))
        LOGGER.error(traceback.format_exc())


def create_template(ctx, config, client, org, vdc_resource, catalog,
                    no_capture, template, ssh_key):
    ctx.obj = {}
    ctx.obj['client'] = client
    try:
        source_ova_item = org.get_catalog_item(config['broker']['catalog'],
                                               template['source_ova_name'])
    except Exception:
        source_ova_item = upload_source_ova(config, client, org, template)
    click.secho('Find source ova \'%s\': %s' %
                (template['source_ova_name'],
                 bool_to_msg(source_ova_item is not None)))
    if source_ova_item is None:
        return None
    item_id = source_ova_item.get('id')
    flag = False
    while True:
        q = client.get_typed_query(
            'adminCatalogItem',
            query_result_format=QueryResultFormat.ID_RECORDS,
            qfilter='id==%s' % item_id)
        records = list(q.execute())
        if records[0].get('status') == 'RESOLVED':
            if flag:
                click.secho('done', fg='blue')
            break
        else:
            if flag:
                click.secho('.', nl=False, fg='green')
            else:
                click.secho(
                    'Waiting for upload to complete...', nl=False, fg='green')
                flag = True
            time.sleep(5)
    vdc = VDC(client, resource=vdc_resource)
    try:
        vapp_resource = vdc.get_vapp(template['temp_vapp'])
    except Exception:
        vapp_resource = None
    if vapp_resource is None:
        click.secho(
            'Creating vApp template \'%s\'' % template['temp_vapp'],
            fg='green')

        init_script = get_data_file('init-%s.sh' % template['name'])
        if ssh_key is not None:
            init_script += \
                f"""
mkdir -p /root/.ssh
echo '{ssh_key}' >> /root/.ssh/authorized_keys
chmod -R go-rwx /root/.ssh
"""

        vapp_resource = vdc.instantiate_vapp(
            template['temp_vapp'],
            catalog.get('name'),
            template['source_ova_name'],
            network=config['broker']['network'],
            fence_mode='bridged',
            ip_allocation_mode=config['broker']['ip_allocation_mode'],
            network_adapter_type='vmxnet3',
            deploy=True,
            power_on=True,
            memory=template['mem'],
            cpu=template['cpu'],
            password=None,
            cust_script=init_script,
            accept_all_eulas=True,
            vm_name=template['temp_vapp'],
            hostname=template['temp_vapp'],
            storage_profile=config['broker']['storage_profile'])
        stdout(vapp_resource.Tasks.Task[0], ctx)
        vapp = VApp(client, resource=vapp_resource)
        if template[
                'source_ova_name'] == 'ubuntu-16.04-server-cloudimg-amd64.ova':
            vapp.reload()
            vs = get_vsphere(config, vapp, template['temp_vapp'])
            vs.connect()
            moid = vapp.get_vm_moid(template['temp_vapp'])
            vm = vs.get_vm_by_moid(moid)
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            click.secho('Rebooting vApp (Ubuntu)', fg='green')
            vapp.reload()
            task = vapp.shutdown()
            stdout(task, ctx)
            while True:
                vapp.reload()
                try:
                    task = vapp.power_on()
                    stdout(task, ctx)
                    break
                except Exception:
                    time.sleep(5)
        click.secho(
            'Customizing vApp template \'%s\'' % template['temp_vapp'],
            fg='green')
        vapp.reload()
        password_auto = vapp.get_admin_password(template['temp_vapp'])
        cust_script = get_data_file('cust-%s.sh' % template['name'])
        for attempt in range(5):
            click.secho('Attempt #%s' % str(attempt + 1), fg='green')
            vs = get_vsphere(config, vapp, template['temp_vapp'])
            vs.connect()
            moid = vapp.get_vm_moid(template['temp_vapp'])
            vm = vs.get_vm_by_moid(moid)
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            result = []
            try:
                result = vs.execute_script_in_guest(
                    vm,
                    'root',
                    password_auto,
                    cust_script,
                    target_file=None,
                    wait_for_completion=True,
                    wait_time=10,
                    get_output=True,
                    delete_script=True,
                    callback=wait_for_guest_execution_callback)
            except Exception as e:
                LOGGER.error(traceback.format_exc())
                click.secho(traceback.format_exc(), fg='red')
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
                if result[0] == 0:
                    break
            if len(result) == 0 or result[0] != 0:
                click.secho(
                    'Customization attempt #%s failed' % int(attempt + 1),
                    fg='red')
                if attempt < 4:
                    click.secho('Will try again')
                    time.sleep(5)
                else:
                    raise Exception('Failed to customize VM')

    if not no_capture:
        capture_as_template(ctx, config, vapp_resource, org, catalog, template)
        if template['cleanup']:
            click.secho(
                'Deleting vApp template \'%s\' ' % template['temp_vapp'],
                fg='green')
            vdc.reload()
            task = vdc.delete_vapp(template['temp_vapp'], force=True)
            stdout(task, ctx)


def capture_as_template(ctx, config, vapp_resource, org, catalog, template):
    vapp_name = vapp_resource.get('name')
    click.secho(
        'Found vApp \'%s\', capturing as template on catalog \'%s\'' %
        (vapp_name, catalog.get('name')),
        fg='green')
    client = ctx.obj['client']
    vapp = VApp(client, href=vapp_resource.get('href'))
    vapp.reload()
    if vapp.resource.get('status') == '4':
        task = vapp.shutdown()
        stdout(task, ctx)
    time.sleep(4)
    task = org.capture_vapp(
        catalog,
        vapp_resource.get('href'),
        template['catalog_item'],
        'CSE Kubernetes template',
        customize_on_instantiate=True,
        overwrite=True)
    stdout(task, ctx)
    return True


def create_amqp_exchange(exchange_name, host, port, vhost, use_ssl,
                         username, password):
    """Creates the specified AMQP exchange if it does not exist.

    If specified AMQP exchange exists already, does nothing.

    :param str exchange_name: The AMQP exchange name to check for or create.
    :param str host: AMQP host name.
    :param str password: AMQP password.
    :param int port: AMQP port number.
    :param bool use_ssl: Enable ssl.
    :param str username: AMQP username.
    :param str vhost: AMQP vhost.

    :raises Exception: if AMQP exchange could not be created.
    """
    click.secho(f"Checking for AMQP exchange '{exchange_name}'", fg='yellow')
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, port, vhost, credentials,
                                           ssl=use_ssl, connection_attempts=3,
                                           retry_delay=2, socket_timeout=5)
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name,
                                 exchange_type=EXCHANGE_TYPE,
                                 durable=True, auto_delete=False)
    except Exception:  # TODO replace with specific exception
        LOGGER.error(traceback.format_exc())
        click.secho(f"Cannot create AMQP exchange '{exchange_name}'", fg='red')
        raise
    finally:
        connection.close()
    click.secho(f"AMQP exchange '{exchange_name}' is ready", fg='green')


def should_configure_amqp(client, amqp_config, amqp_install):
    """Decides if CSE installation should configure vCD AMQP settings.

    Returns False if config file AMQP settings are the same as vCD AMQP
    settings, or if the user declines configuration.

    :param pyvcloud.vcd.client.Client client:
    :param dict amqp_config: 'amqp' section of the config file
    :param str amqp_install: 'skip' skips vCD AMQP configuration,
        'config' configures vCD AMQP settings without prompting user,
        'prompt' asks user before configuring vCD AMQP settings.

    :return: boolean that signals whether we should configure AMQP settings.

    :rtype: bool
    """
    if amqp_install == 'skip':
        click.secho(f"Skipping AMQP configuration. vCD and config file may "
                    f"have different AMQP settings.", fg='yellow')
        return False

    current_settings = to_dict(AmqpService(client).get_settings())
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
        click.secho('current vCD AMQP setting(s):', fg='blue')
        for setting in diff_settings:
            click.echo(f"{setting}: {current_settings[setting]}")
        click.secho('\nconfig file AMQP setting(s):', fg='blue')
        for setting in diff_settings:
            click.echo(f"{setting}: {amqp[setting]}")
        msg = '\nConfigure AMQP with the config file settings?'
        if amqp_install == 'prompt' and not click.confirm(msg):
            click.secho(f"Skipping AMQP configuration. vCD and config file "
                        f"may have different AMQP settings.", fg='yellow')
            return False
        return True

    click.secho("vCD and config file AMQP settings are the same. "
                "Skipping AMQP configuration", fg='green')
    return False


def configure_vcd_amqp(client, exchange_name, host, port, prefix,
                       ssl_accept_all, use_ssl, vhost, username, password):
    """Configures vCD AMQP settings/exchange using parameter values.

    :param pyvcloud.vcd.client.Client client:
    :param str exchange_name: name of exchange.
    :param str host: AMQP host name.
    :param str password: AMQP password.
    :param int port: AMQP port.
    :param str prefix:
    :param bool ssl_accept_all:
    :param bool use_ssl: Enable ssl.
    :param str username: AMQP username.
    :param str vhost: AMQP vhost.

    :raises Exception: if could not set AMQP configuration.
    """
    amqp_service = AmqpService(client)
    amqp = {
        'AmqpExchange': exchange_name,
        'AmqpHost': host,
        'AmqpPort': port,
        'AmqpPrefix': prefix,
        'AmqpSslAcceptAll': ssl_accept_all,
        'AmqpUseSSL': use_ssl,
        'AmqpUsername': username,
        'AmqpVHost': vhost
    }

    # This block sets the AMQP setting values on the
    # vCD "System Administration Extensibility page"
    result = amqp_service.test_config(amqp, password)
    click.secho(f"AMQP test settings, result: {result['Valid'].text}",
                fg='yellow')
    if result['Valid'].text == 'true':
        amqp_service.set_config(amqp, password)
        click.secho("Updated vCD AMQP configuration", fg='green')
    else:
        msg = "Couldn't set vCD AMQP configuration"
        click.secho(msg, fg='red')
        # TODO replace raw exception with specific
        raise Exception(msg)


def should_register_cse(client, ext_install):
    """Decides if CSE installation should register CSE to vCD.

    Returns False if CSE is already registered, or if the user declines
    registration.

    :param pyvcloud.vcd.client.Client client:
    :param str ext_install: 'skip' skips registration,
        'config' allows registration without prompting user,
        'prompt' asks user before registration.

    :return: boolean that signals whether we should register CSE to vCD.

    :rtype: bool
    """
    if ext_install == 'skip':
        return False

    ext = APIExtension(client)

    try:
        cse_info_dict = ext.get_extension_info(CSE_NAME,
                                               namespace=CSE_NAMESPACE)
        click.secho(f"Found 'cse' extension on vCD, "
                    f"enabled={cse_info_dict['enabled']}", fg='green')
        return False
    except MissingRecordException:
        prompt_msg = "Register 'cse' as an API extension in vCD?"
        if ext_install == 'prompt' and not click.confirm(prompt_msg):
            return False

    return True


def register_cse(client, amqp_routing_key, exchange_name):
    """Registers CSE to vCD.

    :param pyvcloud.vcd.client.Client client:
    :param str amqp_routing_key:
    :param str exchange_name: AMQP exchange name.
    """
    ext = APIExtension(client)
    patterns = [
        f'/api/{CSE_NAME}',
        f'/api/{CSE_NAME}/.*',
        f'/api/{CSE_NAME}/.*/.*'
    ]

    ext.add_extension(CSE_NAME, CSE_NAMESPACE, amqp_routing_key,
                      exchange_name, patterns)
    click.secho(f"Registered {CSE_NAME} as an API extension in vCD",
                fg='green')
