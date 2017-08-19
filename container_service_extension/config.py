# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
import logging
import pika
import requests
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
import yaml


LOGGER = logging.getLogger(__name__)


def generate_sample_config():
    sample_config = """amqp:
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

service:
    listeners: 2
    logging_level: 5
    logging_format: %s
    key_filename: 'id_rsa_cse'
    key_filename_pub: 'id_rsa_cse.pub'

    """ % '%(levelname) -8s %(asctime)s %(name) -40s %(funcName) ' \
          '-35s %(lineno) -5d: %(message)s'
    return sample_config


def bool_to_msg(value):
    if value:
        return 'success'
    else:
        return 'fail'


def check_config(file_name):
    config = {}
    with open(file_name, 'r') as f:
        config = yaml.load(f)
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
    return config
