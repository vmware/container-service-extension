# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import hashlib
import os
import pathlib
import platform
import stat
import sys
import threading
from typing import Optional
import urllib

import click
import pkg_resources
import requests
import semantic_version

from container_service_extension.logger import NULL_LOGGER
from container_service_extension.server_constants import MQTT_MIN_API_VERSION
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import PaginationKey
from container_service_extension.thread_local_data import get_thread_request_id
from container_service_extension.thread_local_data import set_thread_request_id


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


class ConsoleMessagePrinter:
    """Callback object to print color coded message on console."""

    def general_no_color(self, msg):
        click.secho(msg)

    def general(self, msg):
        click.secho(msg, fg='green')

    def info(self, msg):
        click.secho(msg, fg='yellow')

    def error(self, msg):
        click.secho(msg, fg='red')


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


def get_cse_info():
    return {
        'product': 'CSE',
        'description': 'Container Service Extension for VMware vCloud Director', # noqa: E501
        'version': pkg_resources.require('container-service-extension')[0].version,  # noqa: E501
        'python': platform.python_version()
    }


def get_installed_cse_version():
    """."""
    cse_version_raw = get_cse_info()['version']
    # Cleanup version string. Strip dev version string segment.
    # e.g. convert '2.6.0.0b2.dev5' to '2.6.0'
    tokens = cse_version_raw.split('.')[:3]
    cse_version = semantic_version.Version('.'.join(tokens))
    return cse_version


def prompt_text(text, color='black', hide_input=False):
    click_text = click.style(str(text), fg=color)
    return click.prompt(click_text, hide_input=hide_input, type=click.STRING)


def get_server_runtime_config():
    import container_service_extension.service as cse_service
    return cse_service.Service().get_service_config()


def get_server_api_version():
    """Get the API version with which CSE server is running.

    :return: api version
    """
    config = get_server_runtime_config()
    return config['vcd']['api_version']


def get_default_storage_profile():
    config = get_server_runtime_config()
    return config['broker']['storage_profile']


def get_default_k8_distribution():
    config = get_server_runtime_config()
    import container_service_extension.def_.models as def_models
    return def_models.Distribution(template_name=config['broker']['default_template_name'],  # noqa: E501
                                   template_revision=config['broker']['default_template_revision'])  # noqa: E501


def get_pks_cache():
    from container_service_extension.service import Service
    return Service().get_pks_cache()


def is_pks_enabled():
    from container_service_extension.service import Service
    return Service().is_pks_enabled()


def is_tkg_plus_enabled(config: dict = None):
    if not config:
        try:
            config = get_server_runtime_config()
        except Exception:
            return False
    service_section = config.get('service', {})
    tkg_plus_enabled = service_section.get('enable_tkg_plus', False)
    if isinstance(tkg_plus_enabled, bool):
        return tkg_plus_enabled
    elif isinstance(tkg_plus_enabled, str):
        return str_to_bool(tkg_plus_enabled)
    return False


def is_tkg_m_enabled(config: dict = None):
    if not config:
        try:
            config = get_server_runtime_config()
        except Exception:
            return False
    service_section = config.get('service', {})
    tkgm_enabled = service_section.get('enable_tkgm', False)
    if isinstance(tkgm_enabled, bool):
        return tkgm_enabled
    elif isinstance(tkgm_enabled, str):
        return str_to_bool(tkgm_enabled)
    return False


def is_environment_variable_enabled(env_name):
    return str_to_bool(os.getenv(env_name))


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

    :param str s: input string

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


def transfer_request_id_wrapper(func):
    cur_thread_req_id = get_thread_request_id()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        set_thread_request_id(cur_thread_req_id)
        func(*args, **kwargs)
        set_thread_request_id(None)  # Reset request id
    return wrapper


def run_async(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        req_id_wrapper = transfer_request_id_wrapper(func)
        t = threading.Thread(name=generate_thread_name(func.__name__),
                             target=req_id_wrapper, args=args, kwargs=kwargs,
                             daemon=True)
        t.start()
        return t
    return wrapper


def generate_thread_name(function_name):
    parent_thread_id = threading.current_thread().ident
    return function_name + ':' + str(parent_thread_id)


def should_use_mqtt_protocol(config):
    """Return true if should use the mqtt protocol; false otherwise.

    The MQTT protocol should be used if the config file contains an "mqtt" key
        and the api version is greater than or equal to the minimum mqtt
        api version.

    :param dict config: config yaml file as a dictionary

    :return: whether to use the mqtt protocol
    :rtype: bool
    """
    return config.get('mqtt') is not None and \
        config.get('vcd') is not None and \
        config['vcd'].get('api_version') is not None and \
        float(config['vcd']['api_version']) >= MQTT_MIN_API_VERSION


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
    filter_string = ""
    if filters:
        filter_expressions = []
        for (key, value) in filters.items():
            if key and value:
                filter_exp = f"{key}=={urllib.parse.quote(escape_query_filter_expression_value(value))}"  # noqa: E501
                filter_expressions.append(filter_exp)
        filter_string = ";".join(filter_expressions)
    return filter_string


def construct_paginated_response(values, result_total,
                                 page_number=CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                 page_size=CSE_PAGINATION_DEFAULT_PAGE_SIZE,  # noqa: E501
                                 page_count=None,
                                 next_page_uri=None,
                                 prev_page_uri=None):
    if not page_count:
        extra_page = 1 if bool(result_total % page_size) else 0
        page_count = result_total // page_size + extra_page
    resp = {
        PaginationKey.RESULT_TOTAL: result_total,
        PaginationKey.PAGE_COUNT: page_count,
        PaginationKey.PAGE_NUMBER: page_number,
        PaginationKey.PAGE_SIZE: page_size,
        PaginationKey.NEXT_PAGE_URI: next_page_uri,
        PaginationKey.PREV_PAGE_URI: prev_page_uri,
        PaginationKey.VALUES: values
    }

    # Conditionally deleting instead of conditionally adding the entry
    # maintains the order for the response
    if not prev_page_uri:
        del resp[PaginationKey.PREV_PAGE_URI]
    if not next_page_uri:
        del resp[PaginationKey.NEXT_PAGE_URI]
    return resp


def create_links_and_construct_paginated_result(base_uri, values, result_total,
                                                page_number=CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                                page_size=CSE_PAGINATION_DEFAULT_PAGE_SIZE,  # noqa: E501
                                                query_params=None):
    if query_params is None:
        query_params = {}
    next_page_uri: Optional[str] = None
    if page_number * page_size < result_total:
        # TODO find a way to get the initial url part
        # ideally the request details should be passed down to each of the
        # handler functions as request context
        next_page_uri = f"{base_uri}?page={page_number+1}&pageSize={page_size}"
        for q in query_params.keys():
            next_page_uri += f"&{q}={query_params[q]}"

    prev_page_uri: Optional[str] = None
    if page_number > 1:
        prev_page_uri = f"{base_uri}?page={page_number-1}&pageSize={page_size}"

    # add the rest of the query parameters
    for q in query_params.keys():
        if next_page_uri:
            next_page_uri += f"&{q}={query_params[q]}"
        if prev_page_uri:
            prev_page_uri += f"&{q}={query_params[q]}"

    return construct_paginated_response(values=values,
                                        result_total=result_total,
                                        page_number=page_number,
                                        page_size=page_size,
                                        next_page_uri=next_page_uri,
                                        prev_page_uri=prev_page_uri)


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
