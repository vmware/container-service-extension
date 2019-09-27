# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pathlib import Path
import re

from vcd_cli.vcd import vcd
import yaml

import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


def dict_to_yaml_file(dikt, filepath):
    """Write a dictionary to a yaml file.

    :param dict dikt: the dictionary to write to a yaml file.
    :param str filepath: the output file path.
    """
    with Path(filepath).open('w') as f:
        f.write(yaml.safe_dump(dikt, default_flow_style=False))


def yaml_to_dict(filepath):
    """Get a dictionary from a yaml file.

    :param str filepath: the file path to the yaml file.

    :return: dictionary representation of the yaml file.

    :rtype: dict
    """
    with Path(filepath).open('r') as f:
        return yaml.safe_load(f)


def get_temp_vapp_name(template_name):
    """.

    This temp vapp name logic is borrowed from cse_install method
    """
    return template_name + '_temp'


def format_command_info(cmd_root, cmd, exit_code, output):
    return f"\nCommand: [{cmd_root} {cmd}]\nExit Code: [{exit_code}]" \
           f"\nOutput Start===\n{output}===Output End"


def execute_commands(cmd_list):
    cmd_results = []
    for action in cmd_list:
        cmd = action.cmd
        print(f"Running command [vcd {cmd}]")
        expected_exit_code = action.exit_code
        result = env.CLI_RUNNER.invoke(vcd, cmd.split(), input='y',
                                       catch_exceptions=False)
        assert result.exit_code == expected_exit_code, \
            testutils.format_command_info(
                'vcd', cmd, result.exit_code, result.output)

        if action.validate_output_func is not None:
            action.validate_output_func(result.output, action.test_user)

        cmd_results.append(result)

    return cmd_results


def list_cluster_output_validator(output, runner_username):
    """Test cse cluster list command output.

    Validate cse cluster list command based on persona.

    :param output: list of results from execution of cse commands
    :param runner_username: persona used to run the command
    """
    if runner_username == 'sys_admin':
        # sys admin can see all the clusters
        assert len(re.findall('testcluster', output)) == 3

    if runner_username == 'org_admin':
        # org admin can see all the clusters belonging to the org
        assert len(re.findall('testcluster', output)) == 3

    if runner_username == 'vapp_author':
        # vapp author can only see clusters created by him
        assert len(re.findall('testcluster', output)) == 1
