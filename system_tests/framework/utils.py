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

import yaml


def write_dict_to_file_as_yaml(input_dict, output_file_name):
    """Write a dictionary as yaml to a file.

    :param dict input_dict: the dictionary that needs to be written to file.
    :param str output_file_name: name of the output file.
    """
    config_yaml = yaml.safe_dump(input_dict, default_flow_style=False)
    with open(output_file_name, 'w') as output_file:
        output_file.write(config_yaml)
