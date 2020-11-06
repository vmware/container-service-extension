# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import click
from vcd_cli.utils import stdout
from vcd_cli.vcd import vcd

from container_service_extension.client import pks
from container_service_extension.client.cluster_command_group import cluster_group  # noqa: E501
import container_service_extension.client.command_filter as cmd_filter
from container_service_extension.client.node_command_group import node_group
from container_service_extension.client.ovdc_command_group import ovdc_group
from container_service_extension.client.system_command_group import system_group  # noqa: E501
from container_service_extension.client.template_command_group import template_group  # noqa: E501
from container_service_extension.logger import CLIENT_LOGGER
import container_service_extension.utils as utils


@vcd.group(short_help='Manage Kubernetes clusters',
           cls=cmd_filter.GroupCommandFilter)
@click.pass_context
def cse(ctx):
    """Manage Kubernetes clusters (Native, vSphere with Tanzu and Ent-PKS).

    Once logged-in, few cmd groups may remain hidden based on factors like
    a) the API version with which CSE server is running
    b) whether CSE server is running or not.

    If CSE server is not running, "Cluster" command group can be used to
    manage "vSphere with Tanzu" clusters only.

    Note that re-login is required for CLI to effectively process any changes
     in the above mentioned external factors.
    """


@cse.command(short_help='Display CSE version')
@click.pass_context
def version(ctx):
    """Display version of CSE plug-in."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    cse_info = utils.get_cse_info()
    ver_str = '%s, %s, version %s' % (cse_info['product'],
                                      cse_info['description'],
                                      cse_info['version'])
    stdout(cse_info, ctx, ver_str)
    CLIENT_LOGGER.debug(ver_str)


# cluster commands
cse.add_command(cluster_group)

# node commands
cse.add_command(node_group)

# template commands
cse.add_command(template_group)

# system commands
cse.add_command(system_group)

# ovdc commands
cse.add_command(ovdc_group)

# Add-on CLI support for PKS container provider
cse.add_command(pks.pks_group)
