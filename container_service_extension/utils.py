# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import hashlib
import logging
import os
import sys
import traceback
from urllib.parse import urlparse

import click
import pika
from cachetools import LRUCache
from pyvcloud.vcd.amqp import AmqpService
from pyvcloud.vcd.api_extension import APIExtension
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from vsphere_guest_run.vsphere import VSphere

cache = LRUCache(maxsize=1024)
BUF_SIZE = 65536
EXCHANGE_TYPE = 'direct'
LOGGER = logging.getLogger('cse.utils')


def get_data_file(filename):
    """Retrieves CSE script file content as a string.

    Used to retrieve builtin script files that users have installed
    via pip install or setup.py. Looks inside virtualenv site-packages, cwd,
    user/global site-packages, python libs, usr bins/Cellars, as well
    as any subdirectories in these paths named 'scripts' or 'cse'.

    :param str filename: name of file (script) we want to get.

    :return: the file contents as a string.

    :rtype: str
    """
    path = None
    for base_path in sys.path:
        possible_paths = [
            os.path.join(base_path, filename),
            os.path.join(base_path, 'scripts', filename),
            os.path.join(base_path, 'cse', filename),
        ]
        for p in possible_paths:
            if os.path.isfile(p):
                path = p
                break
        if path is not None:
            break

    content = ''
    if path is None:
        LOGGER.error('Data file not found!')
        click.secho('Data file not found!', fg='yellow')
        return content

    with open(path) as f:
        content = f.read()
    LOGGER.info(f"Found data file: {path}")
    click.secho(f"Found data file: {path}", fg='green')
    return content


def catalog_exists(org, catalog_name):
    try:
        org.get_catalog(catalog_name)
        return True
    except EntityNotFoundException:
        return False


def create_and_share_catalog(org, catalog_name, catalog_desc=''):
    """Creates and shares specified catalog.

    If catalog does not exist in vCD, create it. Share the specified catalog
    to all orgs.

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:
    :param str catalog_desc:

    :return: XML representation of specified catalog.

    :rtype: lxml.objectify.ObjectifiedElement

    :raises pyvcloud.vcd.exceptions.EntityNotFoundException: if catalog sharing
        fails due to catalog creation failing.
    """
    if catalog_exists(org, catalog_name):
        click.secho(f"Found catalog '{catalog_name}'", fg='green')
    else:
        click.secho(f"Creating catalog '{catalog_name}'", fg='yellow')
        org.create_catalog(catalog_name, catalog_desc)
        click.secho(f"Created catalog '{catalog_name}'", fg='green')
        org.reload()
    org.share_catalog(catalog_name)
    org.reload()
    return org.get_catalog(catalog_name)


def register_extension(client, ext_name, exchange_name, patterns=None):
    """Registers an API extension in vCD.

    :param pyvcloud.vcd.client.Client client:
    :param str ext_name: extension name.
    :param str exchange_name: AMQP exchange name.
    :param list patterns: list of urls that map to this API extension.
    """
    ext = APIExtension(client)
    if patterns is None:
        patterns = [
            f'/api/{ext_name}',
            f'/api/{ext_name}/.*',
            f'/api/{ext_name}/.*/.*'
        ]

    ext.add_extension(ext_name, ext_name, ext_name, exchange_name, patterns)
    click.secho(f"Registered extension {ext_name} as an API extension in vCD",
                fg='green')


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
        click.secho(f"Connected to AMQP server: {host}:{port}", fg='green')
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name,
                                 exchange_type=EXCHANGE_TYPE,
                                 durable=True, auto_delete=False)
    except Exception:  # TODO replace with specific exception
        LOGGER.error(traceback.format_exc())
        click.secho(f"Couldn't create exchange '{exchange_name}'", fg='red')
        raise
    finally:
        connection.close()
    click.secho(f"AMQP exchange '{exchange_name}' is ready", fg='green')


def bool_to_msg(b):
    if b:
        return 'success'
    return 'fail'


def get_sha256(file):
    sha256 = hashlib.sha256()
    with open(file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def get_vsphere(config, vapp, vm_name):
    global cache
    vm_resource = vapp.get_vm(vm_name)
    vm_id = vm_resource.get('id')
    if vm_id not in cache:
        client_sysadmin = Client(
            uri=config['vcd']['host'],
            api_version=config['vcd']['api_version'],
            verify_ssl_certs=config['vcd']['verify'],
            log_headers=True,
            log_bodies=True)
        client_sysadmin.set_credentials(
            BasicLoginCredentials(config['vcd']['username'], 'System',
                                  config['vcd']['password']))

        vapp_sys = VApp(client_sysadmin, href=vapp.href)
        vm_resource = vapp_sys.get_vm(vm_name)
        vm_sys = VM(client_sysadmin, resource=vm_resource)
        vcenter_name = vm_sys.get_vc()
        platform = Platform(client_sysadmin)
        vcenter = platform.get_vcenter(vcenter_name)
        vcenter_url = urlparse(vcenter.Url.text)
        cache_item = {
            'hostname': vcenter_url.hostname,
            'port': vcenter_url.port
        }
        for vc in config['vcs']:
            if vc['name'] == vcenter_name:
                cache_item['username'] = vc['username']
                cache_item['password'] = vc['password']
                break
        cache[vm_id] = cache_item
    else:
        LOGGER.debug('vCenter retrieved from cache: %s / %s' %
                     (vm_id, cache[vm_id]['hostname']))

    v = VSphere(cache[vm_id]['hostname'], cache[vm_id]['username'],
                cache[vm_id]['password'], cache[vm_id]['port'])

    return v


# unused functions, unsure what to do with these
# import hashlib
# import random
# import socket
# import ssl
# import string
# def hex_chunks(s):
#     return [s[i:i + 2] for i in range(0, len(s), 2)]


# def get_thumbprint(host, port):
#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     sock.settimeout(10)
#     wrappedSocket = ssl.wrap_socket(sock)
#     wrappedSocket.connect((host, port))
#     der_cert_bin = wrappedSocket.getpeercert(True)
#     thumb_sha1 = hashlib.sha1(der_cert_bin).hexdigest()
#     wrappedSocket.close()
#     return ':'.join(map(str, hex_chunks(thumb_sha1))).upper()


# def random_word(length):
#     letters = string.ascii_lowercase
#     return ''.join(random.choice(letters) for i in range(length))
