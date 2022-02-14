# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import click
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout

from container_service_extension.client.template import Template
import container_service_extension.client.utils as client_utils
from container_service_extension.logging.logger import CLIENT_LOGGER


@click.group(name='template',
             short_help='Manage native kubernetes runtime templates')
@click.pass_context
def template_group(ctx):
    """Manage native kubernetes runtime templates.

Templates that are no longer compliant with CSE template cookbook
specification will be ignored.

\b
Examples
    vcd cse template list
        Display templates that can be used to deploy native clusters.
    """
    pass


@template_group.command('list',
                        short_help='List native kubernetes runtime templates')
@click.pass_context
@click.option(
    '-t',
    '--tkg',
    'is_tkgm',
    is_flag=True,
    help='Show TKG templates in CSE instead of native templates.'
)
def list_templates(ctx, is_tkgm):
    """Display templates that can be used to deploy native/TKG clusters."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        template = Template(client)
        result = template.get_templates(is_tkgm)
        CLIENT_LOGGER.debug(result)
        value_field_to_display_field = {
            'name': 'Name',
            'revision': 'Revision',
            'catalog': 'Catalog',
            'catalog_item': 'Catalog Item',
            'description': 'Description'
        }
        filtered_result = client_utils.filter_columns(result, value_field_to_display_field)  # noqa: E501
        stdout(filtered_result, ctx, sort_headers=False)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e), exc_info=True)


@template_group.command(
    'reload',
    short_help='Reload CSE native and TKG templates in server runtime configuration'  # noqa: E501
)
@click.pass_context
def reload_templates(ctx):
    """Reload CSE native and TKG templates."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            template = Template(client)
            result = template.reload_templates()
            CLIENT_LOGGER.debug(result)
            stdout(result, ctx)
        else:
            msg = "Insufficient permission to perform operation."
            stderr(msg, ctx)
            CLIENT_LOGGER.error(msg)

    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e), exc_info=True)
