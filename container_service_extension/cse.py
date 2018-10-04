#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import traceback

import click
from vcd_cli.utils import stdout

from container_service_extension.config import check_cse
from container_service_extension.config import generate_sample_config
from container_service_extension.config import install_cse
from container_service_extension.service import Service

LOGGER = logging.getLogger('cse.cli')

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Container Service Extension for VMware vCloud Director.

\b
    Manages CSE.
\b
    Examples
        cse sample
            Generate sample config.
\b
        cse sample > config.yaml
            Save sample config.
\b
        cse check
            Validate CSE installation/configuration.
\b
        cse install --config config.yaml
            Install CSE.
\b
        cse install --config config.yaml --template photon-v2
            Install CSE. It only creates the template specified.
\b
        cse install --config config.yaml --no-capture --ssh-key  \\
                    ~/.etc/id_rsa.pub
            Install CSE. The temporary vApp specified in the config file \\
            will be created, but the vApp will not be captured as a template \\
            in the catalog. --ssh-key option is required if --no-capture \\
            is used
\b
        cse install --config config.yaml --template photon-v2 --update \\
                    --amqp skip --ext skip
            Update the specified template.
\b
        cse version
            Display version.
\b
    Environment Variables
        CSE_CONFIG
            If this environment variable is set, the commands will use the file
            indicated in the variable as the config file. The file indicated
            with the \'--config\' option will have preference over the
            environment variable. If both are omitted, it defaults to file
            \'config.yaml\' in the current directory.
    """
    if ctx.invoked_subcommand is None:
        click.secho(ctx.get_help())
        return


@cli.command(short_help='show version')
@click.pass_context
def version(ctx):
    """Show CSE version."""
    ver_obj = Service.version()
    ver_str = '%s, %s, version %s' % (ver_obj['product'],
                                      ver_obj['description'],
                                      ver_obj['version'])
    stdout(ver_obj, ctx, ver_str)


@cli.command('sample', short_help='generate sample configuration')
@click.pass_context
def sample(ctx):
    """Generate sample CSE configuration."""
    click.secho(generate_sample_config())


@cli.command(short_help='check that CSE is installed according to config file')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config',
    type=click.Path(exists=True),
    metavar='<config-file>',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Config file to use.')
@click.option(
    '-t',
    '--template',
    'template',
    required=False,
    default='*',
    metavar='<template>',
    help='Validate this template')
def check(ctx, config, template):
    """Validate CSE Installation"""
    try:
        check_cse(config, template)
        click.echo('The installation is valid.')
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        click.echo(f"{e}\nCSE installation is invalid, check config file.")


@cli.command(short_help='install CSE on vCD')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config',
    type=click.Path(exists=True),
    metavar='<config-file>',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Config file to use.')
@click.option(
    '-t',
    '--template',
    'template',
    required=False,
    default='*',
    metavar='<template>',
    help='Install this template')
@click.option(
    '-u',
    '--update',
    is_flag=True,
    default=False,
    required=False,
    help='Update template')
@click.option(
    '-n',
    '--no-capture',
    is_flag=True,
    required=False,
    default=False,
    help='Do not capture the temporary vApp as a catalog template. --ssh-key '
         'option is required if this is enabled')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='SSH public key to connect to the guest OS on the VM'
)
@click.option(
    '-a',
    '--amqp',
    'amqp_install',
    default='prompt',
    type=click.Choice(['prompt', 'skip', 'config']),
    help='AMQP configuration')
@click.option(
    '-e',
    '--ext',
    'ext_install',
    default='prompt',
    type=click.Choice(['prompt', 'skip', 'config']),
    help='API Extension configuration')
def install(ctx, config, template, update, no_capture, ssh_key_file,
            amqp_install, ext_install):
    """Install CSE on vCloud Director."""
    if no_capture and ssh_key_file is None:
        click.echo('Must provide ssh-key file (using --ssh-key OR -k) if '
                   '--no-capture is True, or else temporary vm will '
                   'be inaccessible')
    else:
        ssh_key = None
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()
        install_cse(ctx, config, template, update, no_capture, ssh_key,
                    amqp_install, ext_install)


@cli.command(short_help='run service')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config',
    type=click.Path(exists=True),
    metavar='<config-file>',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Config file to use.')
@click.option(
    '-s',
    '--skip-check',
    is_flag=True,
    default=False,
    required=False,
    help='Skip check')
def run(ctx, config, skip_check):
    """Run CSE service."""
    service = Service(config, should_check_cse=not skip_check)
    service.run()


if __name__ == '__main__':
    cli()
