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


@click.group(name='template_group', short_help='Manage native kubernetes runtime templates')
@click.pass_context
def template_group(ctx):
    """Manage native kubernetes runtime templates.

\b
Examples
    vcd cse template list
        Display templates that can be used to deploy native clusters.
    """
    pass


@template_group.command('list',
                        short_help='List native kubernetes runtime templates')
@click.pass_context
def list_templates(ctx):
    """Display templates that can be used to deploy native clusters."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        template = Template(client)
        result = template.get_templates()
        CLIENT_LOGGER.debug(result)
        value_field_to_display_field = {
            'name': 'Name',
            'revision': 'Revision',
            'is_default': 'Default',
            'catalog': 'Catalog',
            'catalog_item': 'Catalog Item',
            'description': 'Description'
        }
        filtered_result = client_utils.filter_columns(result, value_field_to_display_field)  # noqa: E501
        stdout(filtered_result, ctx, sort_headers=False)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
