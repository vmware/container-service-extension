# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import collections
from pathlib import Path
import re

from vcd_cli.vcd import vcd
import yaml
from yaml.parser import ParserError

import container_service_extension.logging.logger as logger
from container_service_extension.rde.constants import RuntimeRDEVersion
from container_service_extension.rde.utils import get_runtime_rde_version_by_vcd_api_version  # noqa: E501
import container_service_extension.system_test_framework.environment as env
import container_service_extension.system_test_framework.utils as testutils


CMD_BINDER = collections.namedtuple('UserCmdBinder',
                                    'cmd exit_code validate_output_func'
                                    ' test_user')


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


def execute_commands(cmd_list, logger=logger.NULL_LOGGER):
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

        logger.debug(f"Executed command: {cmd}")
        logger.debug(f"Output: {result.output}")
        logger.debug(f"Exit code: {result.exit_code}")

        cmd_results.append(result)

    return cmd_results


def list_cluster_output_validator(output, runner_username):
    """Test cse cluster list command output.

    Validate cse cluster list command based on persona.

    :param output: list of results from execution of cse commands
    :param runner_username: persona used to run the command
    """
    if runner_username == env.SYS_ADMIN_NAME:
        # sys admin can see all the clusters
        assert len(re.findall('testcluster', output)) == 3

    if runner_username == env.CLUSTER_ADMIN_NAME:
        # org admin can see all the clusters belonging to the org
        assert len(re.findall('testcluster', output)) == 3

    if runner_username == env.CLUSTER_AUTHOR_NAME:
        # vapp author can only see clusters created by him
        assert len(re.findall('testcluster', output)) == 1


def _update_cluster_apply_spec_for_1_0(apply_spec, properties):
    modified_spec = apply_spec.copy()
    modified_spec['spec']['settings']['network'] = env.TEST_NETWORK
    modified_spec['metadata']['org_name'] = env.TEST_ORG
    modified_spec['metadata']['ovdc_name'] = env.TEST_VDC

    for key, value in properties.items():
        if key == 'worker_count':
            modified_spec['spec']['workers']['count'] = value
        elif key == 'nfs_count':
            modified_spec['spec']['nfs']['count'] = value
        elif key == 'rollback':
            modified_spec['spec']['settings']['rollback_on_failure'] = value
        elif key == 'sizing_class':
            modified_spec['spec']['control_plane']['sizing_class'] = value
            modified_spec['spec']['workers']['sizing_class'] = value
            modified_spec['spec']['nfs']['sizing_class'] = value
        elif key == 'storage_profile':
            modified_spec['spec']['control_plane']['storage_profile'] = value
            modified_spec['spec']['workers']['storage_profile'] = value
            modified_spec['spec']['nfs']['storage_profile'] = value
        elif key == 'template_name':
            modified_spec['spec']['k8_distribution']['template_name'] = value
        elif key == 'template_revision':
            modified_spec['spec']['k8_distribution']['template_revision'] \
                = value
        elif key == 'cluster_name':
            modified_spec['metadata']['cluster_name'] = value
        elif key == 'network':
            modified_spec['spec']['settings']['network'] = value
    return modified_spec


def _update_cluster_apply_spec_for_2_0(apply_spec, properties):
    modified_spec = apply_spec.copy()
    modified_spec['spec']['settings']['ovdcNetwork'] = env.TEST_NETWORK
    modified_spec['metadata']['orgName'] = env.TEST_ORG
    modified_spec['metadata']['virtualDataCenterName'] = env.TEST_VDC

    for key, value in properties.items():
        if key == 'worker_count':
            modified_spec['spec']['topology']['workers']['count'] = value
        elif key == 'nfs_count':
            modified_spec['spec']['topology']['nfs']['count'] = value
        elif key == 'rollback':
            modified_spec['spec']['settings']['rollbackOnFailure'] = value
        elif key == 'sizing_class':
            modified_spec['spec']['topology']['controlPlane']['sizingClass'] = value  # noqa: E501
            modified_spec['spec']['topology']['workers']['sizingClass'] = value
            modified_spec['spec']['topology']['nfs']['sizingClass'] = value
        elif key == 'storage_profile':
            modified_spec['spec']['topology']['controlPlane']['storageProfile'] = value  # noqa: E501
            modified_spec['spec']['topology']['workers']['storageProfile'] = value  # noqa: E501
            modified_spec['spec']['topology']['nfs']['storageProfile'] = value
        elif key == 'template_name' and value:
            modified_spec['spec']['distribution']['templateName'] = value
        elif key == 'template_revision' and value:
            modified_spec['spec']['distribution']['templateRevision'] = value
        elif key == 'cluster_name':
            modified_spec['metadata']['name'] = value
        elif key == 'network' and value:
            modified_spec['spec']['settings']['ovdcNetwork'] = value
    return modified_spec


def modify_cluster_apply_spec(apply_spec_file_path, properties):
    modified_spec = None
    with open(env.APPLY_SPEC_PATH, 'r') as f:
        # replace worker count
        content = f.read()
        sample_apply_spec = yaml.load(content)
        rde_version = get_runtime_rde_version_by_vcd_api_version(
            env.VCD_API_VERSION_TO_USE)
        if rde_version == RuntimeRDEVersion.RDE_1_X.value:
            modified_spec = _update_cluster_apply_spec_for_1_0(
                sample_apply_spec, properties)
        elif rde_version == RuntimeRDEVersion.RDE_2_X.value:
            modified_spec = _update_cluster_apply_spec_for_2_0(
                sample_apply_spec, properties)
        else:
            raise Exception("Invalid RDE version")
    # write modified spec to the apply spec file
    with open(apply_spec_file_path, 'w') as f:
        f.write(yaml.dump(modified_spec))


def construct_apply_param(test_case_parameters):
    """Construct parameter for generating cluster apply spec.

    :param tuple test_case_parameters: Indicates a parameterized test case.
        Note that the order of the parameters is important.
    """
    return {
        'worker_count': test_case_parameters[0],
        'nfs_count': test_case_parameters[1],
        'rollback': test_case_parameters[2],
        'template_name': test_case_parameters[3],
        'template_revision': test_case_parameters[4],
        'network': test_case_parameters[5],
        'sizing_class': test_case_parameters[6],
        'storage_profile': test_case_parameters[7],
        'cluster_name': test_case_parameters[8]
    }


def validate_yaml_output():
    def validator(output, test_runner_username):
        try:
            yaml.load(output)
            return True
        except ParserError:
            return False
    return validator


def get_worker_count_from_1_0_0_entity_dict(cluster_dict):
    return len(cluster_dict['status']['nodes']['workers'])


def get_worker_count_from_2_0_0_entity_dict(cluster_dict):
    return len(cluster_dict['status']['nodes']['workers'])


def generate_validate_node_count_func(expected_nodes, rde_version, logger=logger.NULL_LOGGER):  # noqa: E501
    """Generate validator function to verify number of nodes in the cluster.

    :param expected_nodes: Expected number of nodes in the cluster

    :return validator: function(output, test_user)
    """
    def validator(output, test_runner_username):
        cmd_list = [
            CMD_BINDER(cmd=f"cse cluster info {env.USERNAME_TO_CLUSTER_NAME[test_runner_username]}",   # noqa
                       exit_code=0,
                       validate_output_func=None,
                       test_user=test_runner_username)
        ]
        cmd_results = execute_commands(cmd_list, logger=logger)

        cluster_info_dict = yaml.load(cmd_results[0].output)

        if rde_version == RuntimeRDEVersion.RDE_1_X.value:
            return get_worker_count_from_1_0_0_entity_dict(cluster_info_dict) == expected_nodes  # noqa: E501
        elif rde_version == RuntimeRDEVersion.RDE_2_X.value:
            return get_worker_count_from_2_0_0_entity_dict(cluster_info_dict) == expected_nodes  # noqa: 501
        else:
            raise Exception("Invalid RDE version")

    return validator
