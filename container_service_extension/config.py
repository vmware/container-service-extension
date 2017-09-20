# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
import logging
import pika
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vsphere import VSphere
import requests
import yaml


LOGGER = logging.getLogger(__name__)


def generate_sample_config():
    sample_config = """
amqp:
    host: amqp.vmware.com
    port: 5672
    user: 'guest'
    password: 'guest'
    exchange: vcdext
    routing_key: cse

vcd:
    host: vcd.vmware.com
    port: 443
    username: 'administrator'
    password: 'my_secret_password'
    api_version: '6.0'
    verify: False
    log: True

vcs:
    host: vcenter.vmware.com
    port: 443
    username: 'administrator@vsphere.local'
    password: 'my_secret_password'
    verify: False

service:
    listeners: 2
    logging_level: 5
    logging_format: %s

broker:
    type: default
    catalog: cse
    master_template: k8s-u.ova
    node_template: k8s-u.ova
    username: cse
    password: 'cse_user_template_password'
    master_cpu: 4
    master_mem: 4096
    node_cpu: 4
    node_mem: 4096

    """ % '%(levelname) -8s %(asctime)s %(name) -40s %(funcName) ' \
          '-35s %(lineno) -5d: %(message)s'
    return sample_config.strip() + '\n'


def bool_to_msg(value):
    if value:
        return 'success'
    else:
        return 'fail'


def get_config(file_name):
    config = {}
    with open(file_name, 'r') as f:
        config = yaml.load(f)
    if not config['vcd']['verify']:
        click.secho('InsecureRequestWarning: '
                    'Unverified HTTPS request is being made. '
                    'Adding certificate verification is strongly '
                    'advised.', fg='yellow', err=True)
        requests.packages.urllib3.disable_warnings()
    return config


def check_config(file_name):
    config = get_config(file_name)
    amqp = config['amqp']
    credentials = pika.PlainCredentials(amqp['user'], amqp['password'])
    parameters = pika.ConnectionParameters(amqp['host'], amqp['port'],
                                           '/',
                                           credentials)
    connection = pika.BlockingConnection(parameters)
    click.echo('Connection to AMQP server (%s:%s): %s' % (amqp['host'],
               amqp['port'],
               bool_to_msg(connection.is_open)))
    connection.close()
    if not config['vcd']['verify']:
        click.secho('InsecureRequestWarning: '
                    'Unverified HTTPS request is being made. '
                    'Adding certificate verification is strongly '
                    'advised.', fg='yellow', err=True)
        requests.packages.urllib3.disable_warnings()
    client = Client(config['vcd']['host'],
                    api_version=config['vcd']['api_version'],
                    verify_ssl_certs=config['vcd']['verify'],
                    log_file='cse.log',
                    log_headers=True,
                    log_bodies=True
                    )
    client.set_credentials(BasicLoginCredentials(config['vcd']['username'],
                                                 'System',
                                                 config['vcd']['password']))
    click.echo('Connection to vCloud Director as system '
               'administrator (%s:%s): %s' %
               (config['vcd']['host'], config['vcd']['port'],
                bool_to_msg(True)))

    if config['broker']['type'] == 'default':
        logged_in_org = client.get_org()
        org = Org(client, org_resource=logged_in_org)
        org.get_catalog(config['broker']['catalog'])
        click.echo('Find catalog \'%s\': %s' %
                   (config['broker']['catalog'], bool_to_msg(True)))
        org.get_catalog_item(config['broker']['catalog'],
                             config['broker']['master_template'])
        click.echo('Find master template \'%s\': %s' %
                   (config['broker']['master_template'], bool_to_msg(True)))
        org.get_catalog_item(config['broker']['catalog'],
                             config['broker']['node_template'])
        click.echo('Find node template \'%s\': %s' %
                   (config['broker']['node_template'], bool_to_msg(True)))

    v = VSphere(config['vcs']['host'],
                config['vcs']['username'],
                config['vcs']['password'],
                port=int(config['vcs']['port']))
    v.connect()
    click.echo('Connection to vCenter Server as %s '
               '(%s:%s): %s' %
               (config['vcs']['username'],
                config['vcs']['host'],
                config['vcs']['port'],
                bool_to_msg(True)))
    return config
