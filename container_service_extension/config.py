# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import logging
import os
import site
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
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
import requests
from vcd_cli.utils import stdout
from vcd_cli.utils import to_dict
from vsphere_guest_run.vsphere import VSphere
import yaml

from container_service_extension.consumer import EXCHANGE_TYPE
from container_service_extension.utils import bool_to_msg
from container_service_extension.utils import check_file_permissions
from container_service_extension.utils import check_keys_and_value_types
from container_service_extension.utils import check_python_version
from container_service_extension.utils import get_sha256
from container_service_extension.utils import get_vsphere

LOGGER = logging.getLogger('cse.config')

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
    """Generates a sample config file for cse."""
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


def get_validated_config(filename):
    """Gets the config file as a dictionary, then ensures that all properties
    exist and are valid.

    :param str filename: path to config file.

    :return: cse config

    :rtype: dict
    """
    check_file_permissions(filename)
    with open(filename) as f:
        config = yaml.safe_load(f)

    check_keys_and_value_types(config, SAMPLE_CONFIG, location='config file')
    validate_amqp_config(config['amqp'])
    validate_broker_config(config['broker'])
    check_keys_and_value_types(config['service'],
                               SAMPLE_SERVICE_CONFIG['service'],
                               location="config file 'service' property")
    check_keys_and_value_types(config['vcd'], SAMPLE_VCD_CONFIG['vcd'],
                               location="config file 'vcd' property")

    if not config['vcd']['verify']:
        click.secho('InsecureRequestWarning: Unverified HTTPS request is '
                    'being made. Adding certificate verification is '
                    'strongly advised.', fg='yellow', err=True)
        requests.packages.urllib3.disable_warnings()

    client = Client(config['vcd']['host'],
                    api_version=config['vcd']['api_version'],
                    verify_ssl_certs=config['vcd']['verify'],
                    log_file='cse-check.log',
                    log_headers=True,
                    log_bodies=True)
    client.set_credentials(BasicLoginCredentials(config['vcd']['username'],
                                                 'System',
                                                 config['vcd']['password']))
    click.echo(f"Connected to vCloud Director as system administrator "
               f"({config['vcd']['host']}:{config['vcd']['port']})")

    validate_vcs_config(config['vcs'], client)

    return config


def validate_amqp_config(amqp_dict):
    """Ensures that 'amqp' section of config has correct keys and value types.
    Also ensures that connection to AMQP server is valid.

    :param dict amqp_dict: 'amqp' section of config file as a dict.

    :raises KeyError: if @amqp_dict has missing or extra properties.
    :raises ValueError: if the value type for an @amqp_dict property
        is incorrect.
    """
    check_keys_and_value_types(amqp_dict, SAMPLE_AMQP_CONFIG['amqp'],
                               location="config file 'amqp' property")
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
    connection = pika.BlockingConnection(parameters)
    click.echo(f"Connected to AMQP server "
               f"({amqp_dict['host']}:{amqp_dict['port']}): "
               f"{bool_to_msg(connection.is_open)}")
    connection.close()


def validate_vcs_config(vcs, client):
    """Ensures that 'vcs' section of config has correct keys and value types.
    Also ensures that all vCD VCs are listed in config file and are accessible.

    :param list vcs: 'vcs' section of config file as a list.

    :raises KeyError: if a vc in @vcs has missing or extra properties.
    :raises: ValueError: if the value type for a vc property is incorrect, or
        if vCD has a VC that is not listed in the config file.
    """
    for vc in vcs:
        check_keys_and_value_types(vc, SAMPLE_VCS_CONFIG['vcs'][0],
                                   location="config file 'vcs' property")

    # Check that all vCD VCs are listed in config file
    platform = Platform(client)
    config_vc_names = [vc['name'] for vc in vcs]
    for platform_vc in platform.list_vcenters():
        platform_vc_name = platform_vc.get('name')
        if platform_vc_name not in config_vc_names:
            raise ValueError(f"vCenter '{platform_vc_name}' defined in vCloud "
                             f"Director but not found in config file")

    # Check that all VCs listed in config file are accessible
    for vc in vcs:
        vcenter = platform.get_vcenter(vc['name'])
        vsphere_url = urlparse(vcenter.Url.text)
        v = VSphere(vsphere_url.hostname, vc['username'],
                    vc['password'], vsphere_url.port)
        v.connect()
        click.echo(f"Connected to vCenter Server {vc['name']} as "
                   f"{vc['username']} ({vsphere_url.hostname}:"
                   f"{vsphere_url.port})")


def validate_broker_config(broker_dict):
    """Ensures that 'broker' section of config has correct keys and value
    types. Also checks that 'default_broker' property is a valid template.

    :param dict broker_dict: 'broker' section of config file as a dict.

    :raises KeyError: if @broker_dict has missing or extra properties.
    :raises ValueError: if the value type for a @broker_dict property is
        incorrect, or if 'default_template' has a value not listed in the
        'templates' property
    """
    check_keys_and_value_types(broker_dict, SAMPLE_BROKER_CONFIG['broker'],
                               location="config file 'broker' property")

    default_exists = False
    for template in broker_dict['templates']:
        check_keys_and_value_types(template, SAMPLE_TEMPLATE_PHOTON_V2,
                                   location="config file broker "
                                            "template section")
        if template['name'] == broker_dict['default_template']:
            default_exists = True

    if not default_exists:
        raise ValueError('Default template not found in listed templates')


# TODO need a better way to validate templates (not just name checking)
def validate_cse_templates(config, client, template='*'):
    """Ensures that specified templates from config file exist in vCD.

    :param dict config:
    :param pyvcloud.vcd.client.Client client:
    :param str template:

    :raises pyvcloud.vcd.exceptions.EntityNotFoundException: if catalog or
        template is not found in vCD
    """
    logged_in_org = client.get_org()
    org = Org(client, resource=logged_in_org)
    catalog_name = config['broker']['catalog']
    org.get_catalog(catalog_name)
    click.echo(f"Found catalog '{catalog_name}")

    for t in config['broker']['templates']:
        if template == '*' or template == t['name']:
            click.echo(f"Validating template: {t['name']}")
            org.get_catalog_item(catalog_name, t['catalog_item'])
            click.echo(f"Found template in '{catalog_name}': "
                       f"'{t['catalog_item']}")


# TODO also need to validate cse registration and whatever
def check_config(config_file_name, template=None):
    click.echo(f'Validating CSE on vCD from file: {config_file_name}')

    check_python_version()

    config = get_validated_config(config_file_name)
    if template is not None:
        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file='cse-check.log',
                        log_headers=True,
                        log_bodies=True)
        client.set_credentials(
            BasicLoginCredentials(config['vcd']['username'],
                                  'System',
                                  config['vcd']['password']))
        validate_cse_templates(config, client, template)


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
        catalog = org.get_catalog(catalog_name)

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

        if should_configure_amqp(client, config['amqp'], amqp_install):
            configure_amqp(client, config['amqp'])

        register_extension(ctx, client, config, ext_install)
        click.echo(f'Start CSE with: \'cse run --config {config_file_name}\'')


def get_data_file(file_name):
    path = None
    try:
        if os.path.isfile('./%s' % file_name):
            path = './%s' % file_name
        elif os.path.isfile('scripts/%s' % file_name):
            path = 'scripts/%s' % file_name
        elif os.path.isfile(site.getusersitepackages() + '/cse/' + file_name):
            path = site.getusersitepackages() + '/cse/' + file_name
        else:
            sp = site.getsitepackages()
            if isinstance(sp, list):
                for item in sp:
                    if os.path.isfile(item + '/cse/' + file_name):
                        path = item + '/cse/' + file_name
                        break
            elif os.path.isfile(sp + '/cse/' + file_name):
                path = sp + '/cse/' + file_name
    except Exception:
        pass
    content = ''
    if path is not None:
        with open(path) as f:
            content = f.read()
        LOGGER.info('Reading data file: %s' % path)
    else:
        LOGGER.error('Data file not found: %s' % path)
    return content


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
