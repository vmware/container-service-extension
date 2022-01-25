# container-service-extension
# Copyright (c) 2022 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from typing import Dict, List, Tuple

import container_service_extension.common.utils.core_utils as utils


def sanitize_typing(
    user_input: List[Tuple[str, str]],
    known_extra_options: Dict
):
    """Convert list of key-value pair to correctly typed dictionary."""
    sanitized_user_input = {}
    # sanitize user input to correct type
    for k, v in user_input:
        if k in known_extra_options:
            if known_extra_options[k]["type"] == bool:
                sanitized_user_input[k] = utils.str_to_bool(v)
            else:
                sanitized_user_input[k] = known_extra_options[k]["type"](v)
        else:
            sanitized_user_input[k] = v
    return sanitized_user_input


def prompt_for_missing_required_extra_options(
    user_input: Dict,
    known_extra_options: Dict,
    required_options: List[str]

):
    """Augment input dictionary with user input.

    Note : required_options should be a subset of keys of
    known_extra_option dictionary

    If any item in required option is missing in user_input dictionary,
    Prompt user to input a value for the same, use the information
    present in known_extra_options to get prompt text, input typing,
    etc.

    """
    # Prompt user for missing required options
    for k in required_options:
        if k in user_input:
            continue
        val = utils.prompt_text(
            text=known_extra_options[k]["prompt"],
            color='green',
            hide_input=known_extra_options[k]["hidden_field"],
            type=known_extra_options[k]["type"]
        )
        user_input[k] = val
    return user_input


def construct_config_from_extra_options(
    user_input: Dict,
    known_extra_options: Dict
):
    """Construct a config dictionary from user provided key-value pairs.

    Input like "a.b.c : val" is converted to
    {
        'a' : {
            'b': {
                'c': val
            }
        }
    }

    :rtype: Dict

    return: config dictionary constructed from user provided input
    """
    condensed_config_dict = {}
    for k, v in user_input.items():
        if k in known_extra_options:
            condensed_config_dict[known_extra_options[k]['config_key']] = v
        else:
            condensed_config_dict[k] = v

    config = {}
    # Expand dot-notation keys into nested dictionary
    for key, value in condensed_config_dict.items():
        tokens = key.split(".")
        current_dict = config
        for i in range(len(tokens)):
            if i == len(tokens) - 1:
                current_dict[tokens[i]] = value
            else:
                if tokens[i] not in current_dict:
                    current_dict[tokens[i]] = {}
                if not isinstance(current_dict[tokens[i]], dict):
                    raise Exception(
                        "Expecting dictionary in config node "
                        f"'{'.'.join(tokens[0:i+1])}' "
                        f"but found 'f{type(current_dict[tokens[i]])}'"
                    )
                current_dict = current_dict[tokens[i]]

    return config


def merge_dict_recursive(dict1: Dict, dict2: Dict, prefix_key=""):
    """Update dictionary 1 with data from dictionary 2 (recursively).

    If key 'k' is in dict2 but not in dict1, simply add it to dict1.

    If key 'k' is present in both dict1 and dict2.
    If dict1's value is not a dictionary, replace it with the value
    from dict2.
    If both dict1's and dict2's value are dictionaries, merge them recursively
    If value of dict1 is a dictionary but dict2 is not, raise error.

    :return: merged dictionary
    :rtype: dict
    """
    for k, v2 in dict2.items():
        if k in dict1:
            v1 = dict1[k]
            if not isinstance(v1, dict):
                dict1[k] = v2
            else:
                if isinstance(v2, dict):
                    dict1[k] = merge_dict_recursive(v1, v2, f"{prefix_key}.{k}")  # noqa: E501
                else:
                    raise Exception(f"Cannot merge dictionary `{v1}` and a non dictionary `{v2}` for key `{prefix_key}.{k}`")  # noqa: E501
        else:
            dict1[k] = v2
    return dict1
