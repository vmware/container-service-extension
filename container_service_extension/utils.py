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
import stat
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
LOGGER = logging.getLogger('cse.utils')
CSE_SCRIPTS_DIR = 'container_service_extension_scripts'

# used for registering CSE to vCD
CSE_EXT_NAME = 'cse'
CSE_EXT_NAMESPACE = 'cse'

# chunk size in bytes for file reading
BUF_SIZE = 65536

# chunk size for downloading files
SIZE_1MB = 1024 * 1024

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


def wait_until_tools_ready(vapp, vsphere, callback=vgr_callback()):
    """Blocking function to ensure that a VSphere has VMware Tools ready.

    :param pyvcloud.vcd.vapp.VApp vapp:
    :param vsphere_guest_run.vsphere.VSphere vsphere:
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
