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
import traceback
from urllib.parse import urlparse

from cachetools import LRUCache
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vm import VM
from vsphere_guest_run.vsphere import VSphere

LOGGER = logging.getLogger('cse.utils')
cache = LRUCache(maxsize=1024)
SYSTEM_ORG_NAME = "System"

# chunk size for downloading files
SIZE_1MB = 1024 * 1024

# chunk size for reading files
BUF_SIZE = 65536


def download_file(url, filepath, sha256=None):
    """Downloads a file from a url to local.

    Unless @sha256 is given, will overwrite the file at @filepath.
    Recursively creates specified directories in @filepath.

    :param str url: source url.
    :param str filepath: destination filepath.
    :param str sha256: without this argument, any already existing file at
        @filepath will be overwritten. If @sha256 matches the file's
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


def catalog_exists(org, catalog_name):
    """Boolean function to check if catalog exists.

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:

    :return: True if catalog exists, False otherwise.

    :rtype: bool
    """
    try:
        org.get_catalog(catalog_name)
        return True
    except EntityNotFoundException:
        return False


def catalog_item_exists(org, catalog_name, catalog_item):
    """Boolean function to check if catalog item exists (name check).

    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:
    :param str catalog_item:

    :return: True if catalog item exists, False otherwise.

    :rtype: bool
    """
    try:
        org.get_catalog_item(catalog_name, catalog_item)
        return True
    except EntityNotFoundException:
        return False


def upload_ova_to_catalog(client, org, catalog_name, filepath, update=False):
    """Uploads local ova file to vCD catalog.

    :param pyvcloud.vcd.client.Client client:
    :param str filepath: file path to the .ova file.
    :param pyvcloud.vcd.org.Org org: Org to upload to.
    :param str catalog_name: name of catalog.
    :param bool update: signals whether to overwrite an existing catalog
        item with this new one.

    :raises pyvcloud.vcd.exceptions.EntityNotFoundException if catalog
        does not exist.
    :raises pyvcloud.vcd.exceptions.UploadException if upload fails.
    """
    catalog_item = pathlib.Path(filepath).name
    if update:
        try:
            click.secho(f"Update flag set. Checking catalog '{catalog_name}' "
                        f"for '{catalog_item}'", fg='yellow')
            org.delete_catalog_item(catalog_name, catalog_item)
            org.reload()
            wait_for_catalog_item_to_resolve(client, org, catalog_name,
                                             catalog_item)
            click.secho(f"Update flag set. Checking catalog '{catalog_name}' "
                        f"for '{catalog_item}'", fg='yellow')
        except EntityNotFoundException:
            pass
    else:
        try:
            org.get_catalog_item(catalog_name, catalog_item)
            click.secho(f"'{catalog_item}' already exists in catalog "
                        f"'{catalog_name}'", fg='green')
            return
        except EntityNotFoundException:
            pass

    click.secho(f"Uploading '{catalog_item}' to catalog '{catalog_name}'",
                fg='yellow')
    org.upload_ovf(catalog_name, filepath)
    org.reload()
    wait_for_catalog_item_to_resolve(client, org, catalog_name, catalog_item)
    click.secho(f"Uploaded '{catalog_item}' to catalog '{catalog_name}'",
                fg='green')


def wait_for_catalog_item_to_resolve(client, org, catalog_name, catalog_item):
    """Waits for catalog item's most recent task to resolve.

    :param pyvcloud.vcd.client.Client client:
    :param pyvcloud.vcd.org.Org org:
    :param str catalog_name:
    :param str catalog_item:
    """
    item = org.get_catalog_item(catalog_name, catalog_item)
    resource = client.get_resource(item.Entity.get('href'))
    client.get_task_monitor().wait_for_success(resource.Tasks.Task[0])


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
    """Get the VSphere object for a specific VM inside a VApp.

    :param dict config: CSE config as a dictionary
    :param pyvcloud.vcd.vapp.VApp vapp:
    :param str vm_name:

    :return: VSphere object for a specific VM inside a VApp

    :rtype: vsphere_guest_run.vsphere.VSphere
    """
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

        vm_sys = VM(client, resource=vm_resource)
        vcenter_name = vm_sys.get_vc()
        platform = Platform(client)
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
        LOGGER.debug(f"vCenter retrieved from cache\nVM ID: {vm_id}"
                     f"\nHostname: {cache[vm_id]['hostname']}")

    return VSphere(cache[vm_id]['hostname'], cache[vm_id]['username'],
                   cache[vm_id]['password'], cache[vm_id]['port'])


def vgr_callback(prepend_msg='', logger=None):
    """Creates a callback function to use for vsphere-guest-run functions.

    :param str prepend_msg: string to prepend to all messages received from
        vsphere-guest-run function.
    :param logging.Logger logger: logger to use in case of error.

    :return: callback function to print messages received
        from vsphere-guest-run

    :rtype: function
    """
    def callback(message, exception=None):
        click.echo(f"{prepend_msg}{message}")
        if exception is not None:
            click.echo(exception)
            if logger is not None:
                logger.error(traceback.format_exc())
    return callback


def wait_until_tools_ready(vapp, vsphere, callback=vgr_callback):
    """Blocking function to ensure that a VSphere has VMware Tools ready.

    :param pyvcloud.vcd.vapp.VApp vapp:
    :param vsphere_guest_run.vsphere VSphere vsphere:
    :param function callback: a function to print out messages received from
        vsphere-guest-run functions. Function signature should be like this:
        def callback(message, exception=None), where parameter 'message'
        is a string.
    """
    vsphere.connect()
    moid = vapp.get_vm_moid(vapp.name)
    vm = vsphere.get_vm_by_moid(moid)
    vsphere.wait_until_tools_ready(vm, sleep=5, callback=callback)


def get_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()
