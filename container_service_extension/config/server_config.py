# container-service-extension
# Copyright (c) 2022 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import threading
from typing import Dict, List, Tuple, Union


"""
Server Config object allows for thread safe access to the inner dictionary.

The inner dictionary must follow the following constraints.
* Each value should be of basic type, dict or list. The dictionary can be a
    nested dictionary.
* To access any node in the nested dictionary, dot-notation joined key should
    be used.

E.g.
config = {
    key1 : {
        key11: value11,
        key12: [
            value12a,
            value12b
        ]
    },
    key2: value2,
    key3: [
        {
            key31: {
                key31a: value31a
            }
        }
    ]
}

To access value12b, use key : "key1.key12.[1]"
To access value2, use key : "key2"
To access value31a, use key: "key3.[0].key31.key31a"

It is possible to access intermediate dictionary/list nodes but is
discouraged.
"""


def _is_index(key: str, full_key: str = "") -> Tuple[bool, int, str]:
    """Determine  whether a key fragment is an index or not.

    Convert keys of format "[n]" to int(n).

    :param str key:
    :param str full_key:

    :return: True

    :rtype: Tuple[bool, int, str]
    """
    err_msg = ""
    if key.startswith("[") and key.endswith("]"):
        try:
            return True, int(key[1: len(key) - 1]), err_msg
        except TypeError:
            if full_key:
                err_msg = f"Invalid key fragment '{key}' of key " \
                          f"'{full_key}'. Expected integer index."
            else:
                err_msg = f"Invalid key '{key}'. Expected integer index."

    if not err_msg:
        if full_key:
            err_msg = f"Invalid key fragment '{key}' of key '{full_key}'. " \
                      "Expected index in [n] format."
        else:
            err_msg = f"Invalid key '{key}'. Expected index in [n] format."
    return False, -1, err_msg


def _get_element(root: Union[List, Dict], key: str, full_key: str = "") -> Union[bool, Dict, float, int, List, str]:  # noqa: E501
    """Get child element from a node in config dict.

    Input node can be dict or list, parse the key and
    retrieve the element accordingly.

    :param Union[Dict, List] root:
    :param str key:
    :param str full_key:

    :rtype: Union[bool, Dict, float, int, List, str]

    :return: The element from the source node if present
    """
    if isinstance(root, list):
        is_index, index, err_msg = _is_index(key, full_key)
        if not err_msg:
            if 0 <= index < len(root):
                return root[index]
            else:
                if full_key:
                    err_msg = f"Out of bound index '{index}' in key " \
                              f"fragment '{key}' of key '{full_key}'."
                else:
                    err_msg = f"Out of bound index '{index}' in key '{key}'."
        raise KeyError(err_msg)
    elif isinstance(root, dict):
        if key in root:
            return root[key]
        if full_key:
            err_msg = f"Key fragment '{key}' of key '{full_key}' not found."
        else:
            err_msg = f"Key '{key}' not found"
        raise KeyError(err_msg)
    if full_key:
        err_msg = f"For key fragment '{key}' of key '{full_key}'. " \
                  f"Expected dictionary/list, received '{type(root)}'."
    else:
        err_msg = f"For key '{key}'.Expected dictionary/list, " \
                  f"received '{type(root)}'."
    raise TypeError(err_msg)


def _split_key(full_key: str) -> (str, str):
    """Return key to the parent element and fragment key to the leaf node."""
    tokens = full_key.split(".")
    return ".".join(tokens[0:-1]), tokens[-1]


def _navigate_to_parent(root: Dict, full_key: str) -> Dict:
    """Given a key, return the parent element of the element corresponding to the key."""  # noqa: E501
    parent_key, _ = _split_key(full_key)
    if parent_key:
        tokens = parent_key.split(".")
    else:
        tokens = []

    for i in range(0, len(tokens)):
        root = _get_element(root, key=tokens[i], full_key=full_key)

    return root


class ServerConfig:
    def __init__(self, config: dict):
        self._lock = threading.Lock()
        self._config = config

    def get_value_at(self, key: str) -> Union[bool, Dict, float, int, List, str]:  # noqa: E501
        """."""
        with self._lock:
            parent_element = _navigate_to_parent(self._config, key)
            parent_key, final_key = _split_key(key)
            val = _get_element(parent_element, final_key)
        return val

    def set_value_at(self, key: str, value: object) -> str:
        """."""
        old_value = None
        with self._lock:
            parent_element = _navigate_to_parent(self._config, key)
            parent_key, final_key_fragment = _split_key(key)
            is_index, index, err_msg = _is_index(final_key_fragment, key)

            if is_index:
                if isinstance(parent_element, list):
                    if 0 <= index < len(parent_element):
                        old_value = parent_element[index]
                        parent_element[index] = value
                    else:
                        raise KeyError(
                            f"Out of bound index '{index}' in key fragment "
                            f"'{final_key_fragment}' of key '{key}'."
                        )
                else:
                    raise ValueError(
                        f"Expected list but found '{type(parent_element)}' "
                        f"for key fragment '{final_key_fragment}' in key "
                        f"'{key}'"
                    )
            else:
                if isinstance(parent_element, dict):
                    if final_key_fragment in parent_element:
                        old_value = parent_element[final_key_fragment]
                    parent_element[final_key_fragment] = value
                else:
                    raise ValueError(
                        "Expected dictionary but found "
                        f"'{type(parent_element)}' for key "
                        f"fragment '{final_key_fragment}' in key '{key}'"
                    )

        return old_value
