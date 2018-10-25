# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import hashlib
import logging
import os
import pathlib
import random
import socket
import ssl
import stat
import string
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
LOGGER = logging.getLogger('cse.utils')
CSE_SCRIPTS_DIR = 'container_service_extension_scripts'

# used for registering CSE to vCD
CSE_EXT_NAME = 'cse'
CSE_EXT_NAMESPACE = 'cse'
EXCHANGE_TYPE = 'direct'

# chunk size in bytes for file reading
BUF_SIZE = 65536

_type_to_string = {
    str: 'string',
    int: 'number',
    bool: 'true/false',
    dict: 'mapping',
    list: 'sequence',
}


def catalog_exists(org, catalog_name):
    try:
        org.get_catalog(catalog_name)
        return True
    except EntityNotFoundException:
        return False


def catalog_item_exists(org, catalog_name, catalog_item):
    try:
        org.get_catalog_item(catalog_name, catalog_item)
        return True
    except EntityNotFoundException:
        return False


def bool_to_msg(value):
    if value:
        return 'success'
    return 'fail'


def get_sha256(filepath):
    """Gets sha256 hash of file as a string.

    :param str filepath: path to file.

    :return: sha256 string for the file.

    :rtype: str
    """
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def check_keys_and_value_types(dikt, ref_dict, location='dictionary'):
    """Compares a dictionary with a reference dictionary to ensure that
    all keys and value types are the same.

    :param dict dikt: the dictionary to check for validity
    :param dict ref_dict: the dictionary to check against
    :param str location: where this check is taking place, so error messages
        can be more descriptive.

    :raises KeyError: if @dikt has missing or invalid keys
    :raises ValueError: if the value of a property in @dikt does not match with
        the value of the same property in @ref_dict
    """
    ref_keys = set(ref_dict.keys())
    keys = set(dikt.keys())

    missing_keys = ref_keys - keys
    invalid_keys = keys - ref_keys

    if missing_keys:
        click.secho(f"Missing keys in {location}: {missing_keys}", fg='red')
    if invalid_keys:
        click.secho(f"Invalid keys in {location}: {invalid_keys}", fg='red')

    bad_value = False
    for k in ref_keys:
        if k not in keys:
            continue
        value_type = type(ref_dict[k])
        if not isinstance(dikt[k], value_type):
            click.secho(f"{location} key '{k}': value type should be "
                        f"'{_type_to_string[value_type]}'", fg='red')
            bad_value = True

    if missing_keys or invalid_keys:
        raise KeyError(f"Missing and/or invalid key in {location}")
    if bad_value:
        raise ValueError(f"Incorrect type for property value(s) in {location}")


def check_python_version():
    """Ensures that user's Python version >= 3.6.

    :raises Exception: if user's Python version < 3.6.
    """
    major = sys.version_info.major
    minor = sys.version_info.minor
    click.echo(f"Required Python version: >= 3.6\nInstalled Python version: "
               f"{major}.{minor}.{sys.version_info.micro}")
    if major < 3 or (major == 3 and minor < 6):
        raise Exception("Python version should be 3.6 or greater")


def check_file_permissions(filename):
    """Ensures that the file only has rw permission for Owner, and no
    permissions for anyone else.

    :param str filename: path to file.

    :raises Exception: if file has 'x' permissions for Owner or 'rwx'
        permissions for 'Others' or 'Group'.
    """
    err_msgs = []
    file_mode = os.stat(filename).st_mode
    if file_mode & stat.S_IXUSR:
        msg = f"Remove execute permission of the Owner for the file {filename}"
        click.secho(msg, fg='red')
        err_msgs.append(msg)
    if file_mode & stat.S_IROTH or file_mode & stat.S_IWOTH \
            or file_mode & stat.S_IXOTH:
        msg = f"Remove read, write and execute permissions of Others for " \
              f"the file {filename}"
        click.secho(msg, fg='red')
        err_msgs.append(msg)
    if file_mode & stat.S_IRGRP or file_mode & stat.S_IWGRP \
            or file_mode & stat.S_IXGRP:
        msg = f"Remove read, write and execute permissions of Group for the " \
              f"file {filename}"
        click.secho(msg, fg='red')
        err_msgs.append(msg)

    if err_msgs:
        raise IOError(err_msgs)


def get_data_file(filename):
    """Searches paths from sys.path to retrieve file contents

    Looks for @filename at paths listed by sys.path, as well as any
    subdirectory named container_service_extension_scripts.
    Paths along sys.path include: virtualenv site-packages, cwd,
    user/global site-packages, python libs, usr bins/Cellars.

    :param str filename: name of file (script) we want to get.

    :return: the file contents as a string.

    :rtype: str

    :raises FileNotFoundError: if requested data file cannot be
        found.
    """
    path = None
    for base_path in sys.path:
        possible_paths = [
            pathlib.Path(f"{base_path}/{CSE_SCRIPTS_DIR}/{filename}"),
            pathlib.Path(f"{base_path}/{filename}"),
            pathlib.Path(f"{base_path}/scripts/{filename}")
        ]
        for p in possible_paths:
            if p.is_file():
                path = p
                break
        if path is not None:
            break

    if path is None:
        msg = f"Requested data file '{filename}' not found"
        LOGGER.error(msg)
        click.secho(msg, fg='red')
        raise FileNotFoundError(msg)

    LOGGER.info(f"Found data file: {path}")
    click.secho(f"Found data file: {path}", fg='green')
    return path.read_text()


def register_extension(client, ext_name, exchange_name, patterns=None):
    """Registers an API extension in vCD.

    :param pyvcloud.vcd.client.Client client:
    :param str ext_name: extension name
    :param str exchange_name: AMQP exchange name
    :param list patterns: list of urls that map to this API extension
    """
    ext = APIExtension(client)
    if patterns is None:
        patterns = [
            f'/api/{ext_name}',
            f'/api/{ext_name}/.*',
            f'/api/{ext_name}/.*/.*'
        ]

    ext.add_extension(ext_name, ext_name, ext_name, exchange_name, patterns)
    click.secho(f"Registered extension {ext_name} as an API extension in vCD.",
                fg='green')


def configure_vcd_amqp(client, exchange_name, host, port, prefix,
                       ssl_accept_all, use_ssl, vhost, username, password):
    """Configures vCD AMQP settings/exchange using parameter values.

    :param pyvcloud.vcd.client.Client client:
    :param str exchange_name: name of exchange
    :param str host: AMQP host name
    :param str password: AMQP password
    :param int port: AMQP port
    :param str prefix:
    :param bool ssl_accept_all:
    :param bool use_ssl: Enable ssl
    :param str username: AMQP username
    :param str vhost: AMQP vhost
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
        click.secho('Updated vCD AMQP configuration.', fg='green')
    else:
        click.secho("Couldn't set vCD AMQP configuration.", fg='red')


def create_amqp_exchange(exchange_name, host, port, vhost, use_ssl,
                         username, password):
    """Creates the specified AMQP exchange if it does not exist.

    If specified AMQP exchange exists already, does nothing.

    :param str exchange_name: The AMQP exchange name to check for or create
    :param str host: AMQP host name
    :param str password: AMQP password
    :param int port: AMQP port number
    :param bool use_ssl: Enable ssl
    :param str username: AMQP username
    :param str vhost: AMQP vhost
    """
    click.secho(f"Checking for AMQP exchange '{exchange_name}'", fg='yellow')
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, port, vhost, credentials,
                                           ssl=use_ssl, connection_attempts=3,
                                           retry_delay=2, socket_timeout=5)
    connection = pika.BlockingConnection(parameters)
    click.secho(f"Connected to AMQP server: {host}:{port}", fg='green')

    channel = connection.channel()
    try:
        channel.exchange_declare(exchange=exchange_name,
                                 exchange_type=EXCHANGE_TYPE,
                                 durable=True, auto_delete=False)
    except Exception:
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
