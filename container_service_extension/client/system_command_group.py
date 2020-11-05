# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import os

import click
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout
from vcd_cli.vcd import vcd
import yaml

from container_service_extension.client import pks
from container_service_extension.client.cluster import Cluster
import container_service_extension.client.command_filter as cmd_filter
import container_service_extension.client.constants as cli_constants
from container_service_extension.client.de_cluster_native import DEClusterNative  # noqa: E501
from container_service_extension.client.ovdc import Ovdc
import container_service_extension.client.sample_generator as client_sample_generator  # noqa: E501
from container_service_extension.client.system import System
from container_service_extension.client.template import Template
import container_service_extension.client.utils as client_utils
from container_service_extension.exceptions import CseResponseError
from container_service_extension.exceptions import CseServerNotRunningError
from container_service_extension.logger import CLIENT_LOGGER
from container_service_extension.minor_error_codes import MinorErrorCode
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import LocalTemplateKey
import container_service_extension.shared_constants as shared_constants
import container_service_extension.utils as utils


@cse.group(name='system', short_help='Manage CSE service (system daemon)')
@click.pass_context
def system_group(ctx):
    """Manage CSE server remotely.

\b
Examples
    vcd cse system info
        Display detailed information of the CSE server.
\b
    vcd cse system enable --yes
        Enable CSE server without prompting.
\b
    vcd cse system stop --yes
        Stop CSE server without prompting.
\b
    vcd cse system disable --yes
        Disable CSE server without prompting.
    """
    pass


@system_group.command('info', short_help='Display info of CSE server')
@click.pass_context
def system_info(ctx):
    """Display CSE server info."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.get_info()
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@system_group.command('stop', short_help='Gracefully stop CSE server')
@click.pass_context
@click.confirmation_option(prompt='Are you sure you want to stop the server?')
def stop_service(ctx):
    """Stop CSE server."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.update_service_status(action=shared_constants.ServerAction.STOP) # noqa: E501
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@system_group.command('enable', short_help='Enable CSE server')
@click.pass_context
def enable_service(ctx):
    """Enable CSE server."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.update_service_status(action=shared_constants.ServerAction.ENABLE) # noqa: E501
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@system_group.command('disable', short_help='Disable CSE server')
@click.pass_context
def disable_service(ctx):
    """Disable CSE server."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.update_service_status(action=shared_constants.ServerAction.DISABLE) # noqa: E501
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
