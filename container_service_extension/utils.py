# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import hashlib
import sys

import click


# chunk size in bytes for file reading
BUF_SIZE = 65536

_type_to_string = {
    str: 'string',
    int: 'number',
    bool: 'true/false',
    dict: 'mapping',
    list: 'sequence',
}


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


def check_keys_and_value_types(dikt, ref_dict, location='dictionary',
                               excluded_keys=[]):
    """Compare a dictionary with a reference dictionary.

    The method ensures that  all keys and value types are the same in the
    dictionaries.

    :param dict dikt: the dictionary to check for validity
    :param dict ref_dict: the dictionary to check against
    :param str location: where this check is taking place, so error messages
        can be more descriptive.
    :param list excluded_keys: list of str, representing the list of key which
        if missing won't raise an exception.

    :raises KeyError: if @dikt has missing or invalid keys
    :raises TypeError: if the value of a property in @dikt does not match with
        the value of the same property in @ref_dict
    """
    ref_keys = set(ref_dict.keys())
    keys = set(dikt.keys())

    missing_keys = ref_keys - keys - set(excluded_keys)

    if missing_keys:
        click.secho(f"Missing keys in {location}: {missing_keys}", fg='red')
    bad_value = False
    for k in ref_keys:
        if k not in keys:
            continue
        value_type = type(ref_dict[k])
        if not isinstance(dikt[k], value_type):
            click.secho(f"{location} key '{k}': value type should be "
                        f"'{_type_to_string[value_type]}'", fg='red')
            bad_value = True

    if missing_keys:
        raise KeyError(f"Missing and/or invalid key in {location}")
    if bad_value:
        raise TypeError(f"Incorrect type for property value(s) in {location}")


def check_python_version():
    """Ensure that user's Python version >= 3.6.

    :raises Exception: if user's Python version < 3.6.
    """
    click.echo("Required Python version: >= 3.7.3\n"
               f"Installed Python version: {sys.version}")
    if sys.version_info < (3, 7, 3):
        raise Exception("Python version should be 3.7.3 or greater")

def str2bool(val):
    """Convert string boolean values to bool.

    The conversion is case insensitive.

    :param val: input string

    :return: True if val is 'true' otherwise False
    """
    if val:
        return str(val).lower() == 'true'
    return False