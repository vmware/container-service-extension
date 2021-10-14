# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import collections
from pathlib import Path
import re

from vcd_cli.vcd import vcd
import yaml

import container_service_extension.logging.logger as logger
from container_service_extension.rde.constants import RuntimeRDEVersion
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0
import container_service_extension.rde.models.rde_2_0_0 as rde_2_0_0
from container_service_extension.rde.utils import get_runtime_rde_version_by_vcd_api_version  # noqa: E501
import container_service_extension.system_test_framework.environment as env


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
            format_command_info(
                'vcd', cmd, result.exit_code, result.output
            )

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
    if runner_username == 'sys_admin':
        # sys admin can see all the clusters
        assert len(re.findall('testcluster', output)) == 3

    if runner_username == 'org_admin':
        # org admin can see all the clusters belonging to the org
        assert len(re.findall('testcluster', output)) == 3

    if runner_username == 'vapp_author':
        # vapp author can only see clusters created by him
        assert len(re.findall('testcluster', output)) == 1


def _update_cluster_apply_spec_for_2_0(apply_spec, properties):
    # setting default values for ovdc network, org name and ovdc name
    apply_spec_rde: rde_2_0_0.NativeEntity = rde_2_0_0.NativeEntity.from_dict(apply_spec)  # noqa: E501
    apply_spec_rde.spec.settings.ovdc_network = env.TEST_NETWORK
    apply_spec_rde.metadata.org_name = env.TEST_ORG
    apply_spec_rde.metadata.virtual_data_center_name = env.TEST_VDC
    apply_spec_rde.metadata.site = env.VCD_SITE

    # set values sent in properties parameter
    for key, value in properties.items():
        if key == 'worker_count':
            apply_spec_rde.spec.topology.workers.count = value
        elif key == 'nfs_count':
            apply_spec_rde.spec.topology.nfs.count = value
        elif key == 'rollback':
            apply_spec_rde.spec.settings.rollback_on_failure = value
        elif key == 'sizing_class':
            apply_spec_rde.spec.topology.control_plane.sizing_class = value
            apply_spec_rde.spec.topology.workers.sizing_class = value
            apply_spec_rde.spec.topology.nfs.sizing_class = value
        elif key == 'cpu':
            apply_spec_rde.spec.topology.control_plane.cpu = value
            apply_spec_rde.spec.topology.workers.cpu = value
        elif key == 'memory':
            apply_spec_rde.spec.topology.control_plane.memory = value
            apply_spec_rde.spec.topology.workers.memory = value
        elif key == 'storage_profile':
            apply_spec_rde.spec.topology.control_plane.storage_profile = value
            apply_spec_rde.spec.topology.workers.storage_profile = value
            apply_spec_rde.spec.topology.nfs.storage_profile = value
        elif key == 'template_name' and value:
            apply_spec_rde.spec.distribution.template_name = value
        elif key == 'template_revision' and value:
            apply_spec_rde.spec.distribution.template_revision = value
        elif key == 'cluster_name':
            apply_spec_rde.metadata.name = value
        elif key == 'network' and value:
            apply_spec_rde.spec.settings.ovdc_network = value
    modified_spec = apply_spec_rde.to_dict()
    del modified_spec['status']
    return modified_spec


def _update_cluster_apply_spec_for_1_0(apply_spec, properties):
    # setting default values for ovdc network, org name and ovdc name
    apply_spec_rde: rde_1_0_0.NativeEntity = \
        rde_1_0_0.NativeEntity.from_dict(apply_spec)
    apply_spec_rde.spec.settings.network = env.TEST_NETWORK
    apply_spec_rde.metadata.org_name = env.TEST_ORG
    apply_spec_rde.metadata.ovdc_name = env.TEST_VDC

    # set values sent in properties parameter
    for key, value in properties.items():
        if key == 'worker_count':
            apply_spec_rde.spec.workers.count = value
        elif key == 'nfs_count':
            apply_spec_rde.spec.nfs.count = value
        elif key == 'rollback':
            apply_spec_rde.spec.settings.rollback_on_failure = value
        elif key == 'sizing_class':
            apply_spec_rde.spec.control_plane.sizing_class = value
            apply_spec_rde.spec.workers.sizing_class = value
            apply_spec_rde.spec.nfs.sizing_class = value
        elif key == 'storage_profile':
            apply_spec_rde.spec.control_plane.storage_profile = value
            apply_spec_rde.spec.workers.storage_profile = value
            apply_spec_rde.spec.nfs.storage_profile = value
        elif key == 'template_name':
            apply_spec_rde.spec.k8_distribution.template_name = value
        elif key == 'template_revision':
            apply_spec_rde.spec.k8_distribution.template_revision = value
        elif key == 'cluster_name':
            apply_spec_rde.metadata.cluster_name = value
        elif key == 'network' and value:
            apply_spec_rde.spec.settings.network = value

    modified_spec = apply_spec_rde.to_dict()
    del modified_spec['status']
    return modified_spec


def modify_cluster_apply_spec(apply_spec_file_path, properties):
    modified_spec = None
    with open(env.APPLY_SPEC_PATH, 'r') as f:
        # replace worker count
        content = f.read()
        sample_apply_spec = yaml.safe_load(content)
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


def get_worker_count_from_1_0_0_entity_dict(cluster_dict):
    native_entity: rde_1_0_0.NativeEntity = \
        rde_1_0_0.NativeEntity.from_dict(cluster_dict)
    return len(native_entity.status.nodes.workers)


def get_worker_count_from_2_0_0_entity_dict(cluster_dict):
    native_entity: rde_2_0_0.NativeEntity = \
        rde_2_0_0.NativeEntity.from_dict(cluster_dict)
    return len(native_entity.status.nodes.workers)


def generate_validate_node_count_func(cluster_name, expected_nodes, rde_version, logger=logger.NULL_LOGGER):  # noqa: E501
    """Generate validator function to verify number of nodes in the cluster.

    :param expected_nodes: Expected number of nodes in the cluster
    :return validator: function(output, test_user)
    """
    def validator(output, test_runner_username):
        cmd_list = [
            CMD_BINDER(cmd=f"cse cluster info {cluster_name}",   # noqa
                       exit_code=0,
                       validate_output_func=None,
                       test_user=test_runner_username)
        ]
        cmd_results = execute_commands(cmd_list, logger=logger)

        cluster_info_dict = yaml.safe_load(cmd_results[0].output)

        if rde_version == RuntimeRDEVersion.RDE_1_X.value:
            return get_worker_count_from_1_0_0_entity_dict(cluster_info_dict) == expected_nodes  # noqa: E501
        elif rde_version == RuntimeRDEVersion.RDE_2_X.value:
            return get_worker_count_from_2_0_0_entity_dict(cluster_info_dict) == expected_nodes  # noqa: 501
        else:
            raise Exception("Invalid RDE version")

    return validator


def validate_yaml_output():
    """Validate if the output is a valid yaml."""
    def validator(output, test_runner_username):
        # Just try to safe_load the output.
        import yaml
        try:
            yaml.safe_load(output)
        except Exception:
            return False
        return True
    return validator
