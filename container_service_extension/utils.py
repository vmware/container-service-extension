# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import hashlib
import os
import pathlib
import stat
import sys
import threading

import click
import requests


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


class ConsoleMessagePrinter():
    """Callback object to print color coded message on console."""

    def general_no_color(self, msg):
        click.secho(msg)

    def general(self, msg):
        click.secho(msg, fg='green')

    def info(self, msg):
        click.secho(msg, fg='yellow')

    def error(self, msg):
        click.secho(msg, fg='red')


def prompt_text(text, color='black', hide_input=False):
    click_text = click.style(str(text), fg=color)
    return click.prompt(click_text, hide_input=hide_input, type=str)


def get_server_runtime_config():
    from container_service_extension.service import Service
    return Service().get_service_config()


def get_pks_cache():
    from container_service_extension.service import Service
    return Service().get_pks_cache()


def is_pks_enabled():
    from container_service_extension.service import Service
    return Service().is_pks_enabled()


def get_duplicate_items_in_list(items):
    """Find duplicate entries in a list.

    :param list items: list of items with possible duplicates.

    :return: the items that occur more than once in niput list. Each duplicated
        item will be mentioned only once in the returned list.

    :rtype: list
    """
    seen = set()
    duplicates = set()
    if items:
        for item in items:
            if item in seen:
                duplicates.add(item)
            else:
                seen.add(item)
    return list(duplicates)


def check_keys_and_value_types(dikt, ref_dict, location='dictionary',
                               excluded_keys=[], msg_update_callback=None):
    """Compare a dictionary with a reference dictionary.

    The method ensures that  all keys and value types are the same in the
    dictionaries.

    :param dict dikt: the dictionary to check for validity
    :param dict ref_dict: the dictionary to check against
    :param str location: where this check is taking place, so error messages
        can be more descriptive.
    :param list excluded_keys: list of str, representing the list of key which
        if missing won't raise an exception.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback
        object that writes messages onto console.

    :raises KeyError: if @dikt has missing or invalid keys
    :raises TypeError: if the value of a property in @dikt does not match with
        the value of the same property in @ref_dict
    """
    ref_keys = set(ref_dict.keys())
    keys = set(dikt.keys())

    missing_keys = ref_keys - keys - set(excluded_keys)

    if missing_keys and msg_update_callback:
        msg_update_callback.error(
            f"Missing keys in {location}: {missing_keys}")
    bad_value = False
    for k in ref_keys:
        if k not in keys:
            continue
        value_type = type(ref_dict[k])
        if not isinstance(dikt[k], value_type):
            if msg_update_callback:
                msg_update_callback.error(
                    f"{location} key '{k}': value type should be "
                    f"'{_type_to_string[value_type]}'")
            bad_value = True

    if missing_keys:
        raise KeyError(f"Missing and/or invalid key in {location}")
    if bad_value:
        raise TypeError(f"Incorrect type for property value(s) in {location}")


def check_python_version(msg_update_callback=None):
    """Ensure that user's Python version >= 3.7.3.

    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :raises Exception: if user's Python version < 3.7.3
    """
    if msg_update_callback:
        msg_update_callback.general_no_color(
            "Required Python version: >= 3.7.3\n"
            f"Installed Python version: {sys.version}")
    if sys.version_info < (3, 7, 3):
        raise Exception("Python version should be 3.7.3 or greater")


def str_to_bool(s):
    """Convert string boolean values to bool.

    The conversion is case insensitive.

    :param val: input string

    :return: True if val is 'true' otherwise False
    """
    return str(s).lower() == 'true'


def get_sha256(filepath):
    """Get sha256 hash of file as a string.

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


def check_file_permissions(filename, msg_update_callback=None):
    """Ensure that the file has correct permissions.

    Unix based system:
        Owner - r/w permission
        Other - No access
    Windows:
        No check

    :param str filename: path to file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback
        object that writes messages onto console.

    :raises Exception: if file has 'x' permissions for Owner or 'rwx'
        permissions for 'Others' or 'Group'.
    """
    if os.name == 'nt':
        return
    err_msgs = []
    file_mode = os.stat(filename).st_mode
    if file_mode & stat.S_IXUSR:
        msg = f"Remove execute permission of the Owner for the file {filename}"
        if msg_update_callback:
            msg_update_callback.error(msg)
        err_msgs.append(msg)
    if file_mode & stat.S_IROTH or file_mode & stat.S_IWOTH \
            or file_mode & stat.S_IXOTH:
        msg = f"Remove read, write and execute permissions of Others for " \
              f"the file {filename}"
        if msg_update_callback:
            msg_update_callback.error(msg)
        err_msgs.append(msg)
    if file_mode & stat.S_IRGRP or file_mode & stat.S_IWGRP \
            or file_mode & stat.S_IXGRP:
        msg = f"Remove read, write and execute permissions of Group for the " \
              f"file {filename}"
        if msg_update_callback:
            msg_update_callback.error(msg)
        err_msgs.append(msg)

    if err_msgs:
        raise IOError(err_msgs)


def download_file(url, filepath, sha256=None, force_overwrite=False,
                  logger=None, msg_update_callback=None):
    """Download a file from a url to local filepath.

    Will not overwrite files unless @sha256 is given.
    Recursively creates specified directories in @filepath.

    :param str url: source url.
    :param str filepath: destination filepath.
    :param str sha256: without this argument, if a file already exists at
        @filepath, download will be skipped. If @sha256 matches the file's
        sha256, download will be skipped.
    :param bool force_overwrite: if True, will download the file even if it
        already exists or its SHA hasn't changed.
    :param logging.Logger logger: optional logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback
        object that writes messages onto console.

    :raises HTTPError: if the response has an error status code
    """
    path = pathlib.Path(filepath)
    if not force_overwrite and path.is_file() and \
            (sha256 is None or get_sha256(filepath) == sha256):
        msg = f"Skipping download to '{filepath}' (file already exists)"
        if logger:
            logger.info(msg)
        if msg_update_callback:
            msg_update_callback.general(msg)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    msg = f"Downloading file from '{url}' to '{filepath}'..."
    if logger:
        logger.info(msg)
    if msg_update_callback:
        msg_update_callback.info(msg)
    response = requests.get(url, stream=True,
                            headers={'Cache-Control': 'no-cache'})
    response.raise_for_status()
    with path.open(mode='wb') as f:
        for chunk in response.iter_content(chunk_size=SIZE_1MB):
            f.write(chunk)
    msg = f"Download complete"
    if logger:
        logger.info(msg)
    if msg_update_callback:
        msg_update_callback.general(msg)


def read_data_file(filepath, logger=None, msg_update_callback=None):
    """Retrieve file content from local disk as a string.

    :param str filepath: absolute filepath of the file, whose content we want
        to read.
    :param logging.Logger logger: optional logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback
        object that writes messages onto console.

    :return: the contents of the file.

    :rtype: str

    :raises FileNotFoundError: if requested data file cannot be
        found.
    """
    path = pathlib.Path(filepath)
    contents = ''
    try:
        contents = path.read_text()
    except FileNotFoundError as err:
        if msg_update_callback:
            msg_update_callback.error(f"{err}")
        if logger:
            logger.error(f"{err}", exc_info=True)
        raise

    msg = f"Found data file: {path}"
    if msg_update_callback:
        msg_update_callback.general(msg)
    if logger:
        logger.debug(msg)

    return contents


def run_async(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs,
                             daemon=True)
        t.start()
        return t

    return wrapper
