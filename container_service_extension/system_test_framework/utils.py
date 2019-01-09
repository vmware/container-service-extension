# VMware vCloud Director Python SDK
# Copyright (c) 2018 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

import yaml
from vcd_cli.utils import to_dict


def dict_to_yaml_file(dikt, filepath):
    """Write a dictionary to a yaml file.

    :param dict dikt: the dictionary to write to a yaml file.
    :param str filepath: the output file path.
    """
    with Path(filepath).open('w') as f:
        f.write(yaml.safe_dump(dikt, default_flow_style=False))


def yaml_to_dict(filepath):
    """Gets a dictionary from a yaml file.

    :param str filepath: the file path to the yaml file.

    :return: dictionary representation of the yaml file.

    :rtype: dict
    """
    with Path(filepath).open('r') as f:
        return yaml.safe_load(f)


def diff_amqp_settings(amqp_service, amqp_config):
    """Gets a list of settings that differ between vCD and config file amqp.
    Returns an empty list if settings are the same.

    :param pyvcloud.vcd.amqp.AmqpService amqp_service:
    :param dict amqp_config: amqp section of config file.

    :return: list containing the keys that differ.

    :rtype: List[str]
    """
    cur_settings = to_dict(amqp_service.get_settings())
    amqp = {
        'AmqpExchange': amqp_config['exchange'],
        'AmqpHost': amqp_config['host'],
        'AmqpPort': str(amqp_config['port']),
        'AmqpPrefix': amqp_config['prefix'],
        'AmqpSslAcceptAll': str(amqp_config['ssl_accept_all']).lower(),
        'AmqpUseSSL': str(amqp_config['ssl']).lower(),
        'AmqpUsername': amqp_config['username'],
        'AmqpVHost': amqp_config['vhost']
    }
    return [k for k, v in cur_settings.items() if amqp[k] != v]
