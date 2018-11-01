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

from system_test.framework.environment import Environment
import yaml


def __merge_inner(old_data, new_data):
    for key, value in old_data.items():
        if isinstance(value, dict):
            # get node or create one
            node = new_data.setdefault(key, {})
            __merge_inner(value, node)
        else:
            new_data[key] = value

    return new_data


def merge_with_environment_config(new_config, output_file_name=None):
    """."""
    if Environment.get_config() is not None:
        current_config = dict(Environment.get_config())
        # get rid of test specific configurations
        del current_config['test']
        merged_config = __merge_inner(current_config, new_config)
    else:
        merged_config = new_config

    merged_yaml_config = yaml.safe_dump(
        merged_config, default_flow_style=False) + '\n'

    if output_file_name is not None:
        with open(output_file_name, 'w') as f:
            f.write()

    return merged_yaml_config.strip() + '\n'
