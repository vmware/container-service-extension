# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Basic utility methods to perform data transformation and file operations."""

import hashlib
import os
import pathlib
import platform
import stat
import sys
from typing import List
import urllib

import click
import pkg_resources
import requests

from container_service_extension.logging.logger import NULL_LOGGER


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


class NullPrinter:
    """Callback object which does nothing."""

    def general_no_color(self, msg):
        pass

    def general(self, msg):
        pass

    def info(self, msg):
        pass

    def error(self, msg):
        pass


class ConsoleMessagePrinter(NullPrinter):
    """Callback object to print color coded message on console."""

    def general_no_color(self, msg):
        click.secho(msg)

    def general(self, msg):
        click.secho(msg, fg='green')

    def info(self, msg):
        click.secho(msg, fg='yellow')

    def error(self, msg):
        click.secho(msg, fg='red')


def get_cse_info():
    return {
        'product': 'CSE',
        'description': 'Container Service Extension for VMware vCloud Director',  # noqa: E501
        'version': pkg_resources.require('container-service-extension')[0].version,  # noqa: E501
        'python': platform.python_version()
    }


def prompt_text(text, color='black', hide_input=False):
    click_text = click.style(str(text), fg=color)
    return click.prompt(click_text, hide_input=hide_input, type=str)


def is_environment_variable_enabled(env_var_name):
    """Check if the environment variable is set.

    :param str env_var_name: Name of the environment variable
    :rtype: bool
    """
    return str_to_bool(os.getenv(env_var_name))


def get_duplicate_items_in_list(items):
    """Find duplicate entries in a list.

    :param list items: list of items with possible duplicates.

    :return: the items that occur more than once in input list. Each duplicated
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
                               excluded_keys=None,
                               msg_update_callback=NullPrinter()):
    """Compare a dictionary with a reference dictionary.

    The method ensures that  all keys and value types are the same in the
    dictionaries.

    :param dict dikt: the dictionary to check for validity
    :param dict ref_dict: the dictionary to check against
    :param str location: where this check is taking place, so error messages
        can be more descriptive.
    :param list excluded_keys: list of str, representing the list of key which
        if missing won't raise an exception.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    :raises KeyError: if @dikt has missing or invalid keys
    :raises TypeError: if the value of a property in @dikt does not match with
        the value of the same property in @ref_dict
    """
    if excluded_keys is None:
        excluded_keys = []
    ref_keys = set(ref_dict.keys())
    keys = set(dikt.keys())

    missing_keys = ref_keys - keys - set(excluded_keys)

    if missing_keys:
        msg_update_callback.error(
            f"Missing keys in {location}: {missing_keys}")
    bad_value = False
    for k in ref_keys:
        if k not in keys:
            continue
        value_type = type(ref_dict[k])
        if not isinstance(dikt[k], value_type):
            msg_update_callback.error(
                f"{location} key '{k}': value type should be "
                f"'{_type_to_string[value_type]}'")
            bad_value = True

    if missing_keys:
        raise KeyError(f"Missing and/or invalid key in {location}")
    if bad_value:
        raise TypeError(f"Incorrect type for property value(s) in {location}")


def check_python_version(msg_update_callback=NullPrinter()):
    """Ensure that user's Python version >= 3.7.3.

    If the check fails, will exit the python interpreter with error status.

    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.
    """
    try:
        msg_update_callback.general_no_color(
            "Required Python version: >= 3.7.3\n"
            f"Installed Python version: {sys.version}")
        if sys.version_info < (3, 7, 3):
            raise Exception("Python version should be 3.7.3 or greater")
    except Exception as err:
        msg_update_callback.error(str(err))
        sys.exit(1)


def str_to_bool(s):
    """Convert string boolean values to bool.

    The conversion is case insensitive.

    :param s: input string

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


def check_file_permissions(filename, msg_update_callback=NullPrinter()):
    """Ensure that the file has correct permissions.

    Unix based system:
        Owner - r/w permission
        Other - No access
    Windows:
        No check

    :param str filename: path to file.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises Exception: if file has 'x' permissions for Owner or 'rwx'
        permissions for 'Others' or 'Group'.
    """
    if os.name == 'nt':
        return
    err_msgs = []
    file_mode = os.stat(filename).st_mode
    if file_mode & stat.S_IXUSR:
        msg = f"Remove execute permission of the Owner for the file {filename}"
        msg_update_callback.error(msg)
        err_msgs.append(msg)
    if file_mode & stat.S_IROTH or file_mode & stat.S_IWOTH \
            or file_mode & stat.S_IXOTH:
        msg = f"Remove read, write and execute permissions of Others for " \
              f"the file {filename}"
        msg_update_callback.error(msg)
        err_msgs.append(msg)
    if file_mode & stat.S_IRGRP or file_mode & stat.S_IWGRP \
            or file_mode & stat.S_IXGRP:
        msg = f"Remove read, write and execute permissions of Group for the " \
              f"file {filename}"
        msg_update_callback.error(msg)
        err_msgs.append(msg)

    if err_msgs:
        raise IOError(err_msgs)


def download_file(url, filepath, sha256=None, force_overwrite=False,
                  logger=NULL_LOGGER, msg_update_callback=NullPrinter()):
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
    :param logging.Logger logger: logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :raises HTTPError: if the response has an error status code
    """
    path = pathlib.Path(filepath)
    if not force_overwrite and path.is_file() and \
            (sha256 is None or get_sha256(filepath) == sha256):
        msg = f"Skipping download to '{filepath}' (file already exists)"
        logger.info(msg)
        msg_update_callback.general(msg)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    msg = f"Downloading file from '{url}' to '{filepath}'..."
    logger.info(msg)
    msg_update_callback.info(msg)
    response = requests.get(url, stream=True,
                            headers={'Cache-Control': 'no-cache'})
    response.raise_for_status()
    with path.open(mode='wb') as f:
        for chunk in response.iter_content(chunk_size=SIZE_1MB):
            f.write(chunk)
    msg = "Download complete"
    logger.info(msg)
    msg_update_callback.general(msg)


def read_data_file(filepath, logger=NULL_LOGGER,
                   msg_update_callback=NullPrinter()):
    """Retrieve file content from local disk as a string.

    :param str filepath: absolute filepath of the file, whose content we want
        to read.
    :param logging.Logger logger: logger to log with.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :return: the contents of the file.

    :rtype: str

    :raises FileNotFoundError: if requested data file cannot be
        found.
    """
    path = pathlib.Path(filepath)
    try:
        contents = path.read_text()
    except FileNotFoundError as err:
        msg_update_callback.error(f"{err}")
        logger.error(f"{err}", exc_info=True)
        raise

    msg = f"Found data file: {path}"
    msg_update_callback.general(msg)
    logger.debug(msg)

    return contents


def flatten_dictionary(input_dict, parent_key='', separator='.'):
    """Flatten a given dictionary with nested dictionaries if any.

    Example: { 'a' : {'b':'c', 'd': {'e' : 'f'}}, 'g' : 'h'} will be flattened
    to {'a.b': 'c', 'a.d.e': 'f', 'g': 'h'}

    This will flatten only the values of dict type.

    :param dict input_dict:
    :param str parent_key: parent key that gets prefixed while forming flattened key  # noqa: E501
    :param str separator: use the separator to form flattened key
    :return: flattened dictionary
    :rtype: dict
    """
    flattened_dict = {}
    for k in input_dict.keys():
        val = input_dict.get(k)
        key_prefix = f"{parent_key}{k}"
        if isinstance(val, dict):
            flattened_dict.update(flatten_dictionary(val, f"{key_prefix}{separator}"))  # noqa: E501
        else:
            flattened_dict.update({key_prefix: val})
    return flattened_dict


def escape_query_filter_expression_value(value):
    value_str = str(value)
    value_str = value_str.replace('(', "\\(")
    value_str = value_str.replace(')', "\\)")
    value_str = value_str.replace(';', "\\;")
    value_str = value_str.replace(',', "\\,")
    return value_str


def construct_filter_string(filters: dict):
    """Construct &-ed filter string from the dict.

    :param dict filters: dictionary containing key and values for the filters
    """
    filter_string = ""
    if filters:
        filter_expressions = []
        for (key, value) in filters.items():
            if key and value:
                filter_exp = f"{key}=={urllib.parse.quote(escape_query_filter_expression_value(value))}"  # noqa: E501
                filter_expressions.append(filter_exp)
        filter_string = ";".join(filter_expressions)
    return filter_string


def extract_id_from_href(href):
    """Extract id from an href.

    'https://vmware.com/api/admin/user/123456' will return 123456

    :param str href: an href

    :return: id
    """
    if not href:
        return None
    if '/' in href:
        return href.split('/')[-1]
    return href


# ToDo: Device a better way to find the max api version
# without converting the strings to float.
# e.g. 5.20 will be smaller than 5.8 if compared as float, which is wrong
def get_max_api_version(api_versions: List[str]) -> str:
    return str(max(float(x) for x in api_versions))
