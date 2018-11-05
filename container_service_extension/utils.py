# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
import hashlib
import logging
import os
import pathlib
import random
import requests
import socket
import ssl
import string
import sys
from urllib.parse import urlparse

from cachetools import LRUCache
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from vsphere_guest_run.vsphere import VSphere

cache = LRUCache(maxsize=1024)
SYSTEM_ORG_NAME = "System"

# chunk size for downloading files
SIZE_1MB = 1024 * 1024

# chunk size for reading files
BUF_SIZE = 65536


def download_file(url, filepath, sha256=None):
    """Downloads a file from a url to local filepath.

    Will not overwrite files unless @sha256 is given.
    Recursively creates specified directories in @filepath.

    :param str url: source url.
    :param str filepath: destination filepath.
    :param str sha256: without this argument, if a file already exists at
        @filepath, download will be skipped. If @sha256 matches the file's
        sha256, download will be skipped.
    """
    path = pathlib.Path(filepath)
    if path.is_file() and (sha256 is None or get_sha256(filepath) == sha256):
        click.secho(f"Skipping download of '{filepath}'. File already exists.",
                    fg='green')
        return
    path.parent.mkdir(parents=True, exist_ok=True)

    click.secho(f"Downloading file from '{url}' to '{filepath}'...",
                fg='yellow')
    response = requests.get(url, stream=True)
    with path.open(mode='wb') as f:
        for chunk in response.iter_content(chunk_size=SIZE_1MB):
            f.write(chunk)
    click.secho(f"Download complete", fg='green')


def get_data_file(filename):
    """Used to retrieve builtin script files (as str) that users have installed
    via pip install or setup.py. Looks inside virtualenv site-packages, cwd,
    user/global site-packages, python libs, usr bins/Cellars, as well
    as any subdirectories in these paths named 'scripts' or 'cse'.

    :param str filename: name of file (script) we want to get

    :return: the file contents as a string

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


def hex_chunks(s):
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def get_thumbprint(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    wrappedSocket = ssl.wrap_socket(sock)
    wrappedSocket.connect((host, port))
    der_cert_bin = wrappedSocket.getpeercert(True)
    thumb_sha1 = hashlib.sha1(der_cert_bin).hexdigest()
    wrappedSocket.close()
    return ':'.join(map(str, hex_chunks(thumb_sha1))).upper()


def random_word(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def get_vsphere(config, vapp, vm_name):
    global cache
    vm_resource = vapp.get_vm(vm_name)
    vm_id = vm_resource.get('id')
    if vm_id not in cache:
        client = Client(uri=config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_headers=True,
                        log_bodies=True)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)

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

def get_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()
