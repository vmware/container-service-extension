# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import print_function

import hashlib
import logging
import os

import click
from container_service_extension.broker import get_sample_broker_config
from container_service_extension.broker import validate_broker_config_content
from container_service_extension.broker import validate_broker_config_elements
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import SIZE_1MB
from pyvcloud.vcd.extension import Extension
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC

import pika
import requests
import site
import time
from vcd_cli.utils import stdout
from vsphere_guest_run.vsphere import VSphere
import yaml

LOGGER = logging.getLogger(__name__)
BUF_SIZE = 65536

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
    'vcs': {
        'host': 'vcs.vmware.com',
        'port': 443,
        'username': 'administrator@vsphere.local',
        'password': 'my_secret_password',
        'verify': False
    }
}

SAMPLE_SERVICE_CONFIG = {
    'service': {
        'listeners':
        2,
        'logging_level':
        5,
        'logging_format':
        '%(levelname) -8s %(asctime)s %(name) -40s %(funcName) -35s %(lineno) -5d: %(message)s',  # NOQA
    }
}


def generate_sample_config(labels=[]):
    sample_config = yaml.safe_dump(
        SAMPLE_AMQP_CONFIG, default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(
        SAMPLE_VCD_CONFIG, default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(
        SAMPLE_VCS_CONFIG, default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(
        SAMPLE_SERVICE_CONFIG, default_flow_style=False) + '\n'
    sample_config += get_sample_broker_config(labels)

    return sample_config.strip() + '\n'


def bool_to_msg(value):
    if value:
        return 'success'
    else:
        return 'fail'


def get_config(config_file_name):
    config = {}
    with open(config_file_name, 'r') as f:
        config = yaml.load(f)
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


def check_config(config_file_name, template):
    click.secho('Validating CSE on vCD from file: %s' % config_file_name)
    config = get_config(config_file_name)
    validate_broker_config_elements(config['broker'])
    amqp = config['amqp']
    credentials = pika.PlainCredentials(amqp['username'], amqp['password'])
    parameters = pika.ConnectionParameters(
        amqp['host'], amqp['port'], '/', credentials, ssl=amqp['ssl'])
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
        log_file='cse.log',
        log_headers=True,
        log_bodies=True)
    client.set_credentials(
        BasicLoginCredentials(config['vcd']['username'], 'System',
                              config['vcd']['password']))
    click.echo('Connected to vCloud Director as system '
               'administrator (%s:%s): %s' % (config['vcd']['host'],
                                              config['vcd']['port'],
                                              bool_to_msg(True)))
    click.secho('Validating \'%s\' service broker' % config['broker']['type'])
    if config['broker']['type'] == 'default':
        validate_broker_config_content(config, client, template)

    v = VSphere(
        config['vcs']['host'],
        config['vcs']['username'],
        config['vcs']['password'],
        port=int(config['vcs']['port']))
    v.connect()
    click.echo('Connected to vCenter Server as %s '
               '(%s:%s): %s' % (config['vcs']['username'],
                                config['vcs']['host'], config['vcs']['port'],
                                bool_to_msg(True)))
    return config


def uninstall_cse(ctx, config_file_name, template_name):
    click.secho('Uninstalling CSE from vCD from file: %s, template: %s' %
                (config_file_name, template_name))
    config = get_config(config_file_name)
    client = Client(
        config['vcd']['host'],
        api_version=config['vcd']['api_version'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file='cse.log',
        log_headers=True,
        log_bodies=True)
    client.set_credentials(
        BasicLoginCredentials(config['vcd']['username'], 'System',
                              config['vcd']['password']))
    click.echo('Connected to vCloud Director as system '
               'administrator (%s:%s): %s' % (config['vcd']['host'],
                                              config['vcd']['port'],
                                              bool_to_msg(True)))
    ctx.obj = {}
    ctx.obj['client'] = client
    if config['broker']['type'] == 'default':
        ctx.obj = {}
        ctx.obj['client'] = client
        orgs = client.get_org_list()
        for org in [o for o in orgs.Org if hasattr(orgs, 'Org')]:
            if org.get('name') == config['broker']['org']:
                org_href = org.get('href')
        org = Org(client, href=org_href)
        click.echo('Find org \'%s\': %s' % (org.get_name(), bool_to_msg(True)))
        vdc_resource = org.get_vdc(config['broker']['vdc'])
        click.echo('Find vdc \'%s\': %s' % (vdc_resource.get('name'),
                                            bool_to_msg(True)))
        vdc = VDC(client, resource=vdc_resource)
        assert vdc
        for template in config['broker']['templates']:
            if template_name == '*' or template['name'] == template_name:
                click.secho('Deleting template: %s (%s:%s)' %
                            (template['name'], config['broker']['catalog'],
                             template['catalog_item']))
                org.delete_catalog_item(config['broker']['catalog'],
                                        template['catalog_item'])


def install_cse(ctx, config_file_name, template_name, no_capture):
    click.secho('Installing CSE on vCD from file: %s, template: %s' %
                (config_file_name, template_name))
    config = get_config(config_file_name)
    client = Client(
        config['vcd']['host'],
        api_version=config['vcd']['api_version'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file='cse.log',
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
        orgs = client.get_org_list()
        org_href = None
        for org in [o for o in orgs.Org if hasattr(orgs, 'Org')]:
            if org.get('name') == config['broker']['org']:
                org_href = org.get('href')
        org = Org(client, href=org_href)
        click.echo('Find org \'%s\': %s' % (org.get_name(), bool_to_msg(True)))
        vdc_resource = org.get_vdc(config['broker']['vdc'])
        click.echo('Find vdc \'%s\': %s' % (vdc_resource.get('name'),
                                            bool_to_msg(True)))
        try:
            catalog = org.get_catalog(config['broker']['catalog'])
        except Exception:
            click.secho(
                'Creating catalog %s ' % config['broker']['catalog'],
                nl=False,
                fg='green')
            catalog = org.create_catalog(config['broker']['catalog'],
                                         'CSE catalog')
            org.share_catalog(config['broker']['catalog'])
            click.secho('done', fg='blue')
            catalog = org.get_catalog(config['broker']['catalog'])
        click.echo('Find catalog \'%s\': %s' %
                   (config['broker']['catalog'],
                    bool_to_msg(catalog is not None)))
        for template in config['broker']['templates']:
            if template_name == '*' or template['name'] == template_name:
                click.secho('Processing template: %s' % template['name'])
                try:
                    org.get_catalog_item(config['broker']['catalog'],
                                         template['catalog_item'])
                except Exception:
                    create_template(ctx, config, client, org, vdc_resource,
                                    catalog, no_capture, template)
                k8s_template = None
                try:
                    k8s_template = org.get_catalog_item(
                        config['broker']['catalog'], template['catalog_item'])
                except Exception:
                    pass
                click.echo('Find template \'%s\', \'%s\': %s' %
                           (config['broker']['catalog'],
                            template['catalog_item'],
                            bool_to_msg(k8s_template is not None)))
        configure_amqp_settings(client, config)
        register_extension(client, config)
        click.secho('Start CSE with: \'cse run %s\'' % config_file_name)


def get_sha1(file):
    sha1 = hashlib.sha1()
    with open(file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


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
        click.secho('Reading data file: %s' % path)
    else:
        click.secho('Data file not found: %s' % path)
    return content


def upload_source_ova(config, client, org, template):
    cse_cache_dir = os.path.join(os.getcwd(), 'cse_cache')
    cse_ova_file = os.path.join(cse_cache_dir,
                                template['source_ova_name'])
    if not os.path.exists(cse_ova_file):
        if not os.path.isdir(cse_cache_dir):
            os.makedirs(cse_cache_dir)
        click.secho(
            'Downloading %s' % template['source_ova_name'], fg='green')
        r = requests.get(template['source_ova'], stream=True)
        with open(cse_ova_file, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=SIZE_1MB):
                fd.write(chunk)
    if os.path.exists(cse_ova_file):
        sha1 = get_sha1(cse_ova_file)
        assert sha1 == template['sha1_ova']
        click.secho(
            'Uploading %s' % template['source_ova_name'], fg='green')
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
        print('  exception: %s' % str(exception))


def wait_for_guest_execution_callback(message, exception=None):
    click.secho(message)
    if exception is not None:
        print('  exception: %s' % str(exception))


def create_template(ctx, config, client, org, vdc_resource, catalog,
                    no_capture, template):
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
        vapp_resource = vdc.instantiate_vapp(
            template['temp_vapp'],
            catalog.get('name'),
            template['source_ova_name'],
            network=config['broker']['network'],
            fence_mode='bridged',
            ip_allocation_mode=config['broker']['ip_allocation_mode'],
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
        vapp.reload()
        moid = vapp.get_vm_moid(template['temp_vapp'])
        vs = VSphere(
            config['vcs']['host'],
            config['vcs']['username'],
            config['vcs']['password'],
            port=int(config['vcs']['port']))
        vs.connect()
        vm = vs.get_vm_by_moid(moid)
        vs.wait_until_tools_ready(
            vm, sleep=5, callback=wait_for_tools_ready_callback)

        click.secho(
            'Customizing vApp template \'%s\'' % template['temp_vapp'],
            fg='green')
        vapp.reload()
        password_auto = vapp.get_admin_password(template['temp_vapp'])
        cust_script = get_data_file('cust-%s.sh' % template['name'])

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
        click.secho('Result: %s' % result, fg='green')
        result_stdout = result[1].content.decode()
        result_stderr = result[2].content.decode()
        click.secho('stderr:')
        if len(result_stderr) > 0:
            click.secho(result_stderr, err=True)
        click.secho('stdout:')
        if len(result_stdout) > 0:
            click.secho(result_stdout, err=False)

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
        customize_on_instantiate=True)
    stdout(task, ctx)
    return True


def configure_amqp_settings(client, config):
    amqp_service = AmqpService(client)
    amqp = config['amqp']
    amqp_config = {
        'AmqpExchange': amqp['exchange'],
        'AmqpHost': amqp['host'],
        'AmqpPort': amqp['port'],
        'AmqpPrefix': amqp['prefix'],
        'AmqpSslAcceptAll': amqp['ssl_accept_all'],
        'AmqpUseSSL': amqp['ssl'],
        'AmqpUsername': amqp['username'],
        'AmqpVHost': amqp['vhost']
    }
    result = amqp_service.test_config(amqp_config, amqp['password'])
    click.secho('AMQP test settings, result: %s' % result['Valid'].text)

    if result['Valid'].text == 'true':
        amqp_service.set_config(amqp_config, amqp['password'])
        click.secho('Updated vCD AMQP configuration.')
    else:
        click.secho('Couldn\'t set vCD AMQP configuration.')


def register_extension(client, config):
    ext = Extension(client)
    try:
        name = 'cse'
        cse_ext = ext.get_extension(name)
        click.secho('Find extension \'%s\', enabled: %s: %s' %
                    (name, cse_ext['enabled'], bool_to_msg(True)))
    except Exception:
        exchange = 'vcdext'
        patterns = '/api/cse,/api/cse/.*,/api/cse/.*/.*'
        ext.add_extension(name, name, name, exchange, patterns.split(','))
        click.secho('Registered extension \'%s\': %s' % (name,
                                                         bool_to_msg(True)))
