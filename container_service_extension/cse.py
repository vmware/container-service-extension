#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from container_service_extension.config import check_config
from container_service_extension.config import generate_sample_config
from container_service_extension.config import install_cse
from container_service_extension.config import uninstall_cse
from container_service_extension.service import Service
import logging
import pkg_resources
import platform
import sys
from vcd_cli.utils import stdout


LOGGER = logging.getLogger(__name__)


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS,
             invoke_without_command=True)
@click.pass_context
@click.option('-j',
              '--json',
              'json_output',
              is_flag=True,
              default=False,
              help='Results as JSON object')
def cli(ctx, json_output):
    """Container Service Extension for VMware vCloud Director."""
    if ctx.invoked_subcommand is None:
        click.secho(ctx.get_help())
        return


@cli.command(short_help='show version')
@click.pass_context
def version(ctx):
    """Show CSE version"""
    ver = pkg_resources.require('container-service-extension')[0].version
    ver_obj = {'product': 'cse',
               'description': 'Container Service Extension for VMware vCloud Director',
               'version': ver,
               'python': platform.python_version()}
    ver_str = '%s, %s, version %s' % (ver_obj['product'],
                              ver_obj['description'],
                              ver_obj['version'])
    stdout(ver_obj, ctx, ver_str)
    # click.secho(ver)


@cli.command('sample-config', short_help='generate sample configuration')
@click.pass_context
def sample_config(ctx):
    """Generate sample CSE configuration"""
    click.secho(generate_sample_config())


@cli.command(short_help='check configuration')
@click.pass_context
@click.argument('file_name',
                type=click.Path(exists=True),
                metavar='<config-file>',
                required=True,
                default='config.yml')
def check(ctx, file_name):
    """Validate CSE configuration"""
    check_config(file_name)
    click.secho('The configuration is valid.')


@cli.command(short_help='install CSE on vCD')
@click.pass_context
@click.argument('file_name',
                type=click.Path(exists=True),
                metavar='<config-file>',
                required=True,
                default='config.yml')
def install(ctx, file_name):
    """Install CSE on vCloud Director"""
    install_cse(ctx, file_name)


@cli.command(short_help='uninstall CSE from vCD')
@click.pass_context
@click.argument('file_name',
                type=click.Path(exists=True),
                metavar='<config-file>',
                required=True,
                default='config.yml')
def uninstall(ctx, file_name):
    """Uninstall CSE from vCloud Director"""
    uninstall_cse(ctx, file_name)


@cli.command(short_help='run service')
@click.pass_context
@click.argument('file_name',
                type=click.Path(exists=True),
                metavar='<config-file>',
                required=True,
                default='config.yml')
@click.option('-s',
              '--skip-check',
              is_flag=True,
              default=False,
              required=False,
              help='Skip check')
def run(ctx, file_name, skip_check):
    """Run CSE service"""
    service = Service(file_name, check_config=not skip_check)
    service.run()


if __name__ == '__main__':
    cli()
