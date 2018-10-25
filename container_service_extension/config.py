# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import logging
import os
import stat
import sys
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

from container_service_extension.broker import validate_broker_config_content
from container_service_extension.utils import bool_to_msg
from container_service_extension.utils import configure_vcd_amqp
from container_service_extension.utils import create_amqp_exchange
from container_service_extension.utils import get_data_file
from container_service_extension.utils import get_vsphere
from container_service_extension.utils import get_sha256
from container_service_extension.utils import register_extension


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


def generate_sample_config():
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




def get_config(config_file_name):
    config = {}
    with open(config_file_name, 'r') as f:
        config = yaml.safe_load(f)
    if not config['vcd']['verify']:
        click.secho(
            'InsecureRequestWarning: '
            'Unverified HTTPS request is being made. '
            'Adding certificate verification is strongly '
            'advised.',
            fg='yellow',
            err=True)
        requests.packages.urllib3.disable_warnings()
    return config


def check_config(config_file_name, template=None):
    click.secho('Validating CSE on vCD from file: %s' % config_file_name)
    file_mode = os.stat(config_file_name).st_mode
    invalid_file_permissions = False
    if file_mode & stat.S_IXUSR:
        click.secho('Remove execute permission of the Owner for the '
                    'file %s' % config_file_name, fg='red')
        invalid_file_permissions = True
    if file_mode & stat.S_IROTH or file_mode & stat.S_IWOTH or file_mode & stat.S_IXOTH:
        click.secho('Remove read, write and execute permissions of Others'
                    ' for the file %s' % config_file_name, fg='red')
        invalid_file_permissions = True
    if file_mode & stat.S_IRGRP or file_mode & stat.S_IWGRP or file_mode & stat.S_IXGRP:
        click.secho('Remove read, write and execute permissions of Group'
                    ' for the file %s' % config_file_name, fg='red')
        invalid_file_permissions = True
    if invalid_file_permissions:
        sys.exit(1)
    if sys.version_info.major >= 3 and sys.version_info.minor >= 6:
        python_valid = True
    else:
        python_valid = False
    click.echo('Python version >= 3.6 (installed: %s.%s.%s): %s' %
               (sys.version_info.major, sys.version_info.minor,
                sys.version_info.micro, bool_to_msg(python_valid)))
    if not python_valid:
        raise Exception('Python version not supported')
    config = get_config(config_file_name)
    validate_broker_config(config['broker'])
    amqp = config['amqp']
    credentials = pika.PlainCredentials(amqp['username'], amqp['password'])
    parameters = pika.ConnectionParameters(
        amqp['host'],
        amqp['port'],
        amqp['vhost'],
        credentials,
        ssl=amqp['ssl'],
        connection_attempts=3,
        retry_delay=2,
        socket_timeout=5)
    connection = pika.BlockingConnection(parameters)
    click.echo('Connected to AMQP server (%s:%s): %s' %
               (amqp['host'], amqp['port'], bool_to_msg(connection.is_open)))
    connection.close()

    if not config['vcd']['verify']:
        click.secho(
            'InsecureRequestWarning: '
            'Unverified HTTPS request is being made. '
            'Adding certificate verification is strongly '
            'advised.',
            fg='yellow',
            err=True)
        requests.packages.urllib3.disable_warnings()
    client = Client(
        config['vcd']['host'],
        api_version=config['vcd']['api_version'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file='cse-check.log',
        log_headers=True,
        log_bodies=True)
    client.set_credentials(
        BasicLoginCredentials(config['vcd']['username'], 'System',
                              config['vcd']['password']))
    click.echo('Connected to vCloud Director as system '
               'administrator (%s:%s): %s' % (config['vcd']['host'],
                                              config['vcd']['port'],
                                              bool_to_msg(True)))
    platform = Platform(client)
    for vc in platform.list_vcenters():
        found = False
        for config_vc in config['vcs']:
            if vc.get('name') == config_vc.get('name'):
                found = True
                break
        if not found:
            raise Exception('vCenter \'%s\' defined in vCloud Director '
                            'but not in CSE config file' % vc.get('name'))
            return None

    for vc in config['vcs']:
        vcenter = platform.get_vcenter(vc['name'])
        vsphere_url = urlparse(vcenter.Url.text)
        v = VSphere(vsphere_url.hostname, vc['username'],
                    vc['password'], vsphere_url.port)
        v.connect()
        click.echo('Connected to vCenter Server %s as %s '
                   '(%s:%s): %s' % (vc['name'], vc['username'],
                                    vsphere_url.hostname, vsphere_url.port,
                                    bool_to_msg(True)))

    if template is None:
        pass
    else:
        click.secho(
            'Validating \'%s\' service broker' % config['broker']['type'])
        if config['broker']['type'] == 'default':
            validate_broker_config_content(config, client, template)

    return config


def validate_broker_config(broker_dict):
    sample_keys = set(SAMPLE_BROKER_CONFIG['broker'].keys())
    config_keys = set(broker_dict.keys())

    missing_keys = sample_keys - config_keys
    invalid_keys = config_keys - sample_keys

    if missing_keys:
        click.secho(f"Missing keys in broker section:\n{missing_keys}",
                    fg='red')
    if invalid_keys:
        click.secho(f"Invalid keys in broker section:\n{invalid_keys}",
                    fg='red')
    if missing_keys or invalid_keys:
        raise Exception("Add missing keys/remove invalid keys from config "
                        "file's broker section")

    default_exists = False
    for template in broker_dict['templates']:
        sample_keys = set(SAMPLE_TEMPLATE_PHOTON_V2.keys())
        config_keys = set(template.keys())

        missing_keys = sample_keys - config_keys
        invalid_keys = config_keys - sample_keys

        if missing_keys:
            click.secho(f"Missing keys in template section:\n{missing_keys}",
                        fg='red')
        if invalid_keys:
            click.secho(f"Invalid keys in template section:\n{invalid_keys}",
                        fg='red')
        if missing_keys or invalid_keys:
            raise Exception("Add missing keys/remove invalid keys from "
                            "config file broker templates section")

        if template['name'] == broker_dict['default_template']:
            default_exists = True

    if not default_exists:
        raise Exception("Default template not found in listed templates")


def install_cse(ctx, config_file_name, template_name, update, no_capture,
                ssh_key, amqp_install, ext_install):
    check_config(config_file_name)
    click.secho('Installing CSE on vCD from file: %s, template: %s' %
                (config_file_name, template_name))
    config = get_config(config_file_name)
    click.secho(f"Installing CSE on vCloud Director using config file "
                f"'{config_file_name}'")

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
                                                 'System',
                                                 config['vcd']['password']))
    click.secho(f"Connected to vCD as system administrator: "
                f"{config['vcd']['host']}:{config['vcd']['port']}", fg='green')
    org = Org(client, resource=client.get_org_by_name(org_name))
    click.secho(f"Found organization '{org_name}'", fg='green')
    vdc_resource = org.get_vdc(vdc_name)
    vdc = VDC(client, resource=vdc_resource)
    click.secho(f"Found VDC '{vdc_name}'", fg='green')

    # set up cse catalog
    try:
        org.get_catalog(catalog_name)
    except EntityNotFoundException:
        org.create_catalog(catalog_name, 'CSE Catalog')
        org.reload()
    org.share_catalog(catalog_name)
    org.reload()
    catalog = org.get_catalog(catalog_name)

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
        register_extension(client, 'cse', amqp['exchange'])

    # create, customize, capture VM templates
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
            configure_vcd_amqp(client, config['amqp']['exchange'],
                               config['amqp']['host'],
                               config['amqp']['port'],
                               config['amqp']['prefix'],
                               config['amqp']['ssl_accept_all'],
                               config['amqp']['ssl'],
                               config['amqp']['vhost'],
                               config['amqp']['username'],
                               config['amqp']['password'])

        if should_register_cse(client, ext_install):
            register_extension(client, 'cse', config['amqp']['exchange'])

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
        click.secho(f"Skipping AMQP configuration. vCD and config file may "
                    f"have different AMQP settings.", fg='yellow')
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
        click.echo('current vCD AMQP setting(s):')
        for setting in diff_settings:
            click.echo(f"{setting}: {current_settings[setting]}")
        click.echo('\nconfig file AMQP setting(s):')
        for setting in diff_settings:
            click.echo(f"{setting}: {amqp[setting]}")
        msg = '\nConfigure AMQP with the config file settings?'
        if amqp_install == 'prompt' and not click.confirm(msg):
            click.secho(f"Skipping AMQP configuration. vCD and config file "
                        f"may have different AMQP settings.", fg='yellow')
            return False

    return True


def should_register_cse(client, ext_install):
    """Decides if CSE should be registered, depending on user inputs.

    Returns False if CSE is already registered, or if the user declines
    registration.

    :param pyvcloud.vcd.client.Client client:
    :param str ext_install: 'skip' skips registration,
        'config' allows registration without prompting user,
        'prompt' asks user before registration.

    :rtype: bool
    """
    if ext_install == 'skip':
        return False

    ext = APIExtension(client)
    try:
        cse_info_dict = ext.get_extension_info('cse')
        click.echo(f"Found cse', enabled={cse_info_dict['enabled']}")
        return False
    except MissingRecordException:
        prompt_msg = "Register 'cse' as an API extension in vCD?"
        if ext_install == 'prompt' and not click.confirm(prompt_msg):
            return False

    return True
