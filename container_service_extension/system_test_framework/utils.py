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

import pathlib

import yaml
from vcd_cli.utils import to_dict

# from container_service_extension.system_test_framework.environment import SCRIPTS_DIR, ACTIVE_PHOTON_CUST_SCRIPT, ACTIVE_UBUNTU_CUST_SCRIPT, 
import container_service_extension.system_test_framework.environment as env

def write_dict_to_file_as_yaml(input_dict, output_file_name):
    """Write a dictionary as yaml to a file.

    :param dict input_dict: the dictionary that needs to be written to file.
    :param str output_file_name: name of the output file.
    """
    config_yaml = yaml.safe_dump(input_dict, default_flow_style=False)
    with open(output_file_name, 'w') as output_file:
        output_file.write(config_yaml)


def prepare_customization_scripts():
    """Copies real customization scripts to the active customization scripts.
    Copy 'CUST-PHOTON.sh' to 'cust-photon-v2.sh'
    Copy 'CUST-UBUNTU.sh' to 'cust-ubuntu-16.04.sh'

    :raises FileNotFoundError: if script files cannot be found.
    """

    scripts_filepaths = {
        f"{env.SCRIPTS_DIR}/{env.STATIC_PHOTON_CUST_SCRIPT}":
            f"{env.SCRIPTS_DIR}/{env.STATIC_PHOTON_CUST_SCRIPT}",
        f"{env.SCRIPTS_DIR}/{env.STATIC_UBUNTU_CUST_SCRIPT}":
            f"{env.SCRIPTS_DIR}/{env.STATIC_UBUNTU_CUST_SCRIPT}",
    }

    for src, dst in scripts_filepaths:
        pathlib.Path(dst).write_text(pathlib.Path(src).read_text())


def restore_customizaton_scripts():
    """Blanks out 'cust-photon-v2.sh' and 'cust-ubuntu-16.04.sh'.

    :raises FileNotFoundError: if script files cannot be found.
    """

    scripts_paths = [
        pathlib.Path(f"{env.SCRIPTS_DIR}/{env.ACTIVE_PHOTON_CUST_SCRIPT}"),
        pathlib.Path(f"{env.SCRIPTS_DIR}/{env.ACTIVE_UBUNTU_CUST_SCRIPT}")
    ]

    for path in scripts_paths:
        path.write_text('')
