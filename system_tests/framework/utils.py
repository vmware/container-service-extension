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


def write_config_dict_to_file(config_dict, output_file_name):
    """Write a config dict as yaml to a file.

    :param dict config_dict: the dictionary that needs to be written to a file.
    :param str output_file_name: name of the output file.

    :return: True if the data is written successfully to the file, else False.

    :rtype: bool
    """
    config_yaml = yaml.safe_dump(
        config_dict, default_flow_style=False) + '\n'

    output_file = None
    try:
        output_file = open(output_file_name, 'w')
        output_file.write(config_yaml)
        return True
    except Exception:
        return False
    finally:
        if output_file is not None:
            output_file.close()
