#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import sys

import click
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import NotAcceptableException
from pyvcloud.vcd.exceptions import VcdException
from pyVmomi import vim
import requests
from vcd_cli.utils import stdout

from container_service_extension.configure_cse import check_cse_installation
from container_service_extension.configure_cse import generate_sample_config
from container_service_extension.configure_cse import get_validated_config
from container_service_extension.configure_cse import install_cse
from container_service_extension.exceptions import AmqpConnectionError
from container_service_extension.service import Service
from container_service_extension.utils import check_python_version


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Container Service Extension for VMware vCloud Director.

\b
    Examples
        cse version
            Display CSE version.
\b
        cse sample
            Generate sample CSE config as dict
            and print it to the console.
\b
        cse sample --output config.yaml
            Generate sample CSE config in the provided file name
            'config.yaml'.
\b
        cse sample --pks-output pks.yaml
            Generate sample PKS config in a file named 'pks.yaml'.
\b
        cse sample --output config.yaml --pks-output pks.yaml
            Generate sample CSE and PKS config in the respective file
            named provided as param.
\b
        cse install
            Install CSE using data from 'config.yaml'.
\b
        cse install -c myconfig.yaml --template photon-v2
            Install CSE using data from 'myconfig.yaml' but only create
            template 'photon-v2'.
\b
        cse install --update
            Install CSE, and if the templates already exist in vCD, create
            them again.
\b
        cse install --no-capture --ssh-key ~/.ssh/id_rsa.pub
            Install CSE, but don't capture temporary vApps to a template.
            Instead, leave them running for debugging purposes. Copy specified
            SSH key into all template VMs so users with the cooresponding
            private key have access (--ssh-key is required when --no-capture
            is used).
\b
        cse check
            Checks that 'config.yaml' is valid.
\b
        cse check -c myconfig.yaml --check-install
            Checks that 'myconfig.yaml' is valid. Also checks that CSE is
            installed on vCD according to 'myconfig.yaml' (Checks that all
            templates specified in 'myconfig.yaml' exist.)
\b
        cse check --check-install --template photon-v2
            Checks that 'config.yaml' is valid. Also checks that CSE is
            installed on vCD according to 'config.yaml' (Checks that
            template 'photon-v2' exists.)
\b
        cse run
            Run CSE Server using data from 'config.yaml', but first validate
            that CSE was installed according to 'config.yaml'.
\b
        cse run --config myconfig.yaml --skip-check
            Run CSE Server using data from 'myconfig.yaml' without first
            validating that CSE was installed according to 'myconfig.yaml'.
\b
    Environment Variables
        CSE_CONFIG
            If this environment variable is set, the commands will use the file
            indicated in the variable as the config file. The file indicated
            with the '--config' option will have preference over the
            environment variable. If both are omitted, it defaults to file
            'config.yaml' in the current directory.
    """
    if ctx.invoked_subcommand is None:
        click.secho(ctx.get_help())
        return


@cli.command(short_help='Display CSE version')
@click.pass_context
def version(ctx):
    """Display CSE version."""
    ver_obj = Service.version()
    ver_str = '%s, %s, version %s' % (ver_obj['product'],
                                      ver_obj['description'],
                                      ver_obj['version'])
    stdout(ver_obj, ctx, ver_str)


@cli.command('sample', short_help='Generate sample CSE config')
@click.pass_context
@click.option(
    '-o',
    '--output',
    'output',
    required=False,
    default=None,
    metavar='OUTPUT_FILE_NAME',
    help="Filepath to write CSE config file to.")
@click.option(
    '-p',
    '--pks-output',
    'pks_output',
    required=False,
    default=None,
    metavar='OUTPUT_FILE_NAME',
    help="Filepath to write PKS config file to.")
def sample(ctx, output, pks_output):
    """Display sample CSE config file contents."""
    try:
        check_python_version()
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(0)

    click.secho(generate_sample_config(output=output,
                                       pks_output=pks_output))


@cli.command(short_help="Checks that CSE config file is valid (Can also check "
                        "that CSE is installed according to config file)")
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config',
    type=click.Path(exists=True),
    metavar='CONFIG_FILE_NAME',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Config file to use')
@click.option(
    '-i',
    '--check-install',
    'check_install',
    is_flag=True,
    required=False,
    default=False,
    help='Checks that CSE is installed on vCD according to the config file')
@click.option(
    '-t',
    '--template',
    'template',
    required=False,
    default='*',
    metavar='TEMPLATE_NAME',
    help="If '--check-install' flag is used, validate specified k8s template. "
         "Default value of '*' means that all k8s templates in config file"
         " will be validated")
def check(ctx, config, check_install, template):
    """Validate CSE config file."""
    try:
        check_python_version()
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(0)

    config_dict = None
    try:
        config_dict = get_validated_config(config)
    except (NotAcceptableException, VcdException, ValueError,
            KeyError, TypeError) as err:
        click.secho(str(err), fg='red')
    except AmqpConnectionError as err:
        click.secho(str(err), fg='red')
        click.secho("check config file amqp section.", fg='red')
    except requests.exceptions.ConnectionError:
        click.secho("Cannot connect to vCD host (check config file vCD host).",
                    fg='red')
    except vim.fault.InvalidLogin:
        click.secho("vCenter login failed (check config file vCenter "
                    "username/password).", fg='red')

    if not check_install or config_dict is None:
        return

    try:
        check_cse_installation(config_dict, check_template=template)
    except EntityNotFoundException:
        click.secho("CSE installation is invalid", fg='red')


@cli.command(short_help='Install CSE on vCD')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config',
    type=click.Path(exists=True),
    metavar='CONFIG_FILE_NAME',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Config file to use')
@click.option(
    '-t',
    '--template',
    'template',
    required=False,
    default='*',
    metavar='TEMPLATE_NAME',
    help="Create only the specified k8s template. Default value of '*' "
         "means that all templates in config file will be created.")
@click.option(
    '-u',
    '--update',
    is_flag=True,
    default=False,
    required=False,
    help='Recreate CSE native k8s templates on vCD if they already exist')
@click.option(
    '-n',
    '--no-capture',
    is_flag=True,
    required=False,
    default=False,
    help='Do not capture the temporary vApp as a catalog template. --ssh-key '
         'option is required if this flag is used')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='SSH public key to connect to the guest OS on the VM.'
)
def install(ctx, config, template, update, no_capture, ssh_key_file):
    """Install CSE on vCloud Director."""
    try:
        check_python_version()
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(0)

    if no_capture and ssh_key_file is None:
        click.echo('Must provide ssh-key file (using --ssh-key OR -k) if '
                   '--no-capture is True, or else temporary vm will '
                   'be inaccessible')
        return

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()
    try:
        install_cse(ctx, config_file_name=config, template_name=template,
                    update=update, no_capture=no_capture, ssh_key=ssh_key)
    except (EntityNotFoundException, NotAcceptableException, VcdException,
            ValueError, KeyError, TypeError) as err:
        click.secho(str(err), fg='red')
    except AmqpConnectionError as err:
        click.secho(str(err), fg='red')
        click.secho("check config file amqp section.", fg='red')
    except requests.exceptions.ConnectionError:
        click.secho("Cannot connect to vCD host (check config file vCD host).",
                    fg='red')
    except vim.fault.InvalidLogin:
        click.secho("vCenter login failed (check config file vCenter "
                    "username/password).", fg='red')


@cli.command(short_help='Run CSE service')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config',
    type=click.Path(exists=True),
    metavar='CONFIG_FILE_NAME',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Config file to use')
@click.option(
    '-s',
    '--skip-check',
    is_flag=True,
    default=False,
    required=False,
    help='Skip CSE installation checks')
def run(ctx, config, skip_check):
    """Run CSE service."""
    try:
        check_python_version()
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(0)

    try:
        service = Service(config, should_check_config=not skip_check)
        service.run()
    except (NotAcceptableException, VcdException, ValueError, KeyError,
            TypeError) as err:
        click.secho(str(err), fg='red')
    except AmqpConnectionError as err:
        click.secho(str(err), fg='red')
        click.secho("check config file amqp section.", fg='red')
    except requests.exceptions.ConnectionError:
        click.secho("Cannot connect to vCD host (check config file vCD host).",
                    fg='red')
    except vim.fault.InvalidLogin:
        click.secho("vCenter login failed (check config file vCenter "
                    "username/password).", fg='red')
    except Exception as err:
        click.secho(str(err), fg='red')
        click.secho("CSE Server failure. Please check the logs.", fg='red')


if __name__ == '__main__':
    cli()
