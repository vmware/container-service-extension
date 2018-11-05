# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import hashlib
import logging
import os
import stat
import sys
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
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from vcd_cli.utils import stdout
from vcd_cli.utils import to_dict
from vsphere_guest_run.vsphere import VSphere

from container_service_extension.broker import validate_broker_config_content
from container_service_extension.consumer import EXCHANGE_TYPE
from container_service_extension.utils import catalog_item_exists
from container_service_extension.utils import download_file
from container_service_extension.utils import get_data_file
from container_service_extension.utils import get_vsphere
from container_service_extension.utils import upload_ova_to_catalog
from container_service_extension.utils import vgr_callback
from container_service_extension.utils import wait_until_tools_ready
from container_service_extension.utils import wait_for_catalog_item_to_resolve

LOGGER = logging.getLogger('cse.config')
BUF_SIZE = 65536
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


def bool_to_msg(value):
    if value:
        return 'success'
    else:
        return 'fail'


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
        vdc = VDC(client, resource=vdc_resource)
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
                create_template(ctx, client, config, template, catalog, org,
                                vdc, update=update, no_capture=no_capture,
                                ssh_key=ssh_key)


def create_template(ctx, client, config, template_config, catalog, org, vdc,
                    update=False, no_capture=False, ssh_key=None):
    """Handles template creation phase during CSE installation.

    :param click.core.Context ctx: click context object.
    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template section of @config.
    :param lxml.objectify.ObjectifiedElement catalog: XML representation of
        a catalog.
    :param pyvcloud.vcd.org.Org org:
    :param pyvcloud.vcd.vdc.VDC vdc:
    :param bool update: '--update' flag from 'cse install' command.
    :param bool no_capture: '--no-capture' flag from 'cse install' command.
    :param str ssh_key: ssh key from file given from '--ssh-key' option from
        'cse install' command.
    """
    ctx.obj = {'client': client}
    catalog_name = catalog.get('name')
    catalog_item = template_config['catalog_item']
    vapp_name = template_config['temp_vapp']
    ova_name = template_config['source_ova_name']
    ova_url = template_config['source_ova']

    if not update and catalog_item_exists(org, catalog_name, catalog_item):
        click.secho(f"Found template '{catalog_item}' in catalog "
                    f"'{catalog_name}'", fg='green')
        return

    # if update flag is set, delete existing template/ova file/temp vapp
    if update:
        click.secho(f"Update flag set. If template, source ova file, and "
                    f"temporary vApp exist, they will be deleted", fg='yellow')
        try:
            org.delete_catalog_item(catalog_name, catalog_item)
            wait_for_catalog_item_to_resolve(client, org, catalog_name,
                                             catalog_item)
            org.reload()
            click.secho("Deleted vApp template", fg='green')
        except EntityNotFoundException:
            pass
        try:
            org.delete_catalog_item(catalog_name, ova_name)
            wait_for_catalog_item_to_resolve(client, org, catalog_name,
                                             ova_name)
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

    click.secho(f"Creating template '{catalog_item}' in catalog "
                f"'{catalog_name}'", fg='green')
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
            upload_ova_to_catalog(client, org, catalog_name, ova_filepath)

        vapp = create_temp_vapp(ctx, client, config, template_config, vdc,
                                ssh_key)

    if no_capture:
        click.secho(f"'no-capture' flag set. Not capturing vApp '{vapp.name}' "
                    f"as a template", fg='yellow')
        return

    click.secho(f"Creating template '{catalog_item}' from vApp '{vapp.name}'",
                fg='yellow')
    capture_vapp_to_template(ctx, org, catalog, vapp, catalog_item,
                             desc=template_config['description'])
    click.secho(f"Created template '{catalog_item}' from vApp '{vapp_name}'",
                fg='green')

    if template_config['cleanup']:
        click.secho(f"Deleting vApp '{vapp_name}'", fg='yellow')
        task = vdc.delete_vapp(vapp_name, force=True)
        stdout(task, ctx=ctx)
        vdc.reload()
        click.secho(f"Deleted vApp '{vapp_name}'", fg='green')


def get_sha256(file):
    sha256 = hashlib.sha256()
    with open(file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def create_temp_vapp(ctx, client, config, template_config, vdc, ssh_key):
    """Handles temporary VApp creation and customization step of CSE install.

    Initializes and customizes VApp.

    :param click.core.Context ctx: click context object.
    :param pyvcloud.vcd.client.Client client:
    :param dict config: CSE config.
    :param dict template_config: specific template config section of @config.
    :param pyvcloud.vcd.vdc.VDC vdc:
    :param str ssh_key: ssh key to use in temporary VApp's VM. Can be None.

    :return: VApp object for temporary VApp.

    :rtype: pyvcloud.vdc.vapp.VApp
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
    vapp = create_vapp_from_config(client, vdc, config, template_config,
                                   init_script)
    click.secho(f"Created vApp '{vapp_name}'", fg='green')

    click.secho(f"Customizing vApp '{vapp_name}'", fg='yellow')
    cust_script = get_data_file(f"cust-{template_config['name']}.sh")
    ova_name = template_config['source_ova_name']
    is_photon = True if 'photon' in ova_name else False
    customize_vm(ctx, config, vapp, vapp.name, cust_script,
                 is_photon=is_photon)
    click.secho(f"Customized vApp '{vapp_name}'", fg='green')

    return vapp


def create_vapp_from_config(client, vdc, config, template_config, init_script):
    """Creates a VApp from a specific template config.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.vdc.VDC vdc:
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
    vapp = VApp(client, resource=vapp_sparse_resource)
    vapp.reload()
    return vapp


def customize_vm(ctx, config, vapp, vm_name, cust_script, is_photon=False):
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
            vs.get_vm_by_moid(vapp.get_vm_moid((vm_name))),
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
        raise Exception(msg)


def capture_vapp_to_template(ctx, org, catalog, vapp, catalog_item, desc=''):
    """Captures existing VApp as a template in @catalog.

    VApp should have tools ready, or shutdown will fail, and VApp will be
    unavailable to be captured.

    :param click.core.Context ctx: click context object needed for stdout.
    :param pyvcloud.vcd.org.Org org:
    :param lxml.objectify.ObjectifiedElement catalog: XML representation of
        a catalog.
    :param pyvcloud.vcd.vapp.VApp vapp:
    :param str catalog_item: catalog item name for the template.
    :param str desc: template description.
    """
    try:
        task = vapp.shutdown()
        stdout(task, ctx=ctx)
        vapp.reload()
    except OperationNotSupportedException:
        pass

    task = org.capture_vapp(catalog, vapp.href, catalog_item, desc,
                            customize_on_instantiate=True, overwrite=True)
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

    :raises: Exception if AMQP exchange cannot be created
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
