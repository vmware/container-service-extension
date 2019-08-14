#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import sys

import click
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import NotAcceptableException
from pyvcloud.vcd.exceptions import VcdException
from pyVmomi import vim
import requests
from vcd_cli.utils import stdout
import yaml

from container_service_extension.config_validator import get_validated_config
from container_service_extension.configure_cse import check_cse_installation
from container_service_extension.configure_cse import install_cse
from container_service_extension.exceptions import AmqpConnectionError
from container_service_extension.local_template_manager import \
    get_all_k8s_local_template_definition
from container_service_extension.remote_template_manager import \
    RemoteTemplateManager
from container_service_extension.sample_generator import generate_sample_config
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import RemoteTemplateKey
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.service import Service
from container_service_extension.utils import check_python_version
from container_service_extension.utils import ConsoleMessagePrinter


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
DISPLAY_ALL = "all"
DISPLAY_DIFF = "diff"
DISPLAY_LOCAL = "local"
DISPLAY_REMOTE = "remote"


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


@cli.group(short_help='Manage native Kubernetes provider templates')
@click.pass_context
def template(ctx):
    """Manage native Kubernetes provider templates.

\b
Examples
    cse template list -c config.yaml
        Display all templates, including that are currently in the local
        catalog, and the ones that are defined in remote template cookbook.
\b
    cse template list --display local -c config.yaml
        Display templates that are currently in the local catalog.
\b
    cse template list --display remote -c config.yaml
        Display templates that are defined in the remote template cookbook.
\b
    cse template list --display diff -c config.yaml
        Display only templates that are defined in remote template cookbook but
        not present in the local catalog.
\b
    cse template install -c config.yaml
        Install all templates defined in remote template cookbook that are
        missing from the local catalog.
\b
    cse template install [template name] [template revision] -c config.yaml
        Install a particular template at a given revision defined in remote
        template cookbook that is missing from the local catalog.
\b
    cse template install -c config.yaml --force
        Install all templates defined in remote template cookbook. Tempaltes
        already in the local catalog that match one in the remote catalog will
        be recreated from scratch.
\b
    cse template delete -c config.yaml
        Delete all templates from local catalog.
\b
    cse template delete [template name] [template revision] -c config.yaml
        Delete a particular template at a given revision from local catalog.
    """
    pass


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
    help="Filepath to write CSE config file to")
@click.option(
    '-p',
    '--pks-output',
    'pks_output',
    required=False,
    default=None,
    metavar='OUTPUT_FILE_NAME',
    help="Filepath to write PKS config file to")
def sample(ctx, output, pks_output):
    """Display sample CSE config file contents."""
    try:
        check_python_version()
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(1)

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
    help='Filepath of CSE config file')
@click.option(
    '-i',
    '--check-install',
    'check_install',
    is_flag=True,
    help='Checks that CSE is installed on vCD according to the config file')
def check(ctx, config, check_install):
    """Validate CSE config file."""
    try:
        check_python_version(ConsoleMessagePrinter())
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(1)

    config_dict = None
    try:
        config_dict = get_validated_config(
            config, msg_update_callback=ConsoleMessagePrinter())
    except (NotAcceptableException, VcdException, ValueError,
            KeyError, TypeError) as err:
        click.secho(str(err), fg='red')
    except AmqpConnectionError as err:
        click.secho(str(err), fg='red')
        click.secho("check config file amqp section.", fg='red')
    except requests.exceptions.ConnectionError as err:
        click.secho(f"Cannot connect to {err.request.url}.", fg='red')
    except vim.fault.InvalidLogin:
        click.secho("vCenter login failed (check config file vCenter "
                    "username/password).", fg='red')

    if check_install and config_dict:
        try:
            check_cse_installation(
                config_dict, msg_update_callback=ConsoleMessagePrinter())
        except Exception as err:
            click.secho(f"Error : {err}")
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
    help='Filepath of CSE config file')
@click.option(
    '-s',
    '--skip-template-creation',
    'skip_template_creation',
    is_flag=True,
    help='Skips creating CSE k8s template during installation')
@click.option(
    '-f',
    '--force-update',
    is_flag=True,
    help='Recreate CSE k8s templates on vCD even if they already exist')
@click.option(
    '-d',
    '--retain-temp-vapp',
    'retain_temp_vapp',
    is_flag=True,
    help='Retain the temporary vApp after the template has been captured'
         ' --ssh-key option is required if this flag is used')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='Filepath of SSH public key to add to vApp template')
def install(ctx, config, skip_template_creation, force_update,
            retain_temp_vapp, ssh_key_file):
    """Install CSE on vCloud Director."""
    try:
        check_python_version(ConsoleMessagePrinter())
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(1)

    if retain_temp_vapp and not ssh_key_file:
        click.echo('Must provide ssh-key file (using --ssh-key OR -k) if '
                   '--no-capture is True, or else temporary vm will '
                   'be inaccessible')
        return

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()
    try:
        install_cse(ctx, config_file_name=config,
                    skip_template_creation=skip_template_creation,
                    force_update=force_update, ssh_key=ssh_key,
                    retain_temp_vapp=retain_temp_vapp,
                    msg_update_callback=ConsoleMessagePrinter())
    except (EntityNotFoundException, NotAcceptableException, VcdException,
            ValueError, KeyError, TypeError) as err:
        click.secho(str(err), fg='red')
    except AmqpConnectionError as err:
        click.secho(str(err), fg='red')
        click.secho("check config file amqp section.", fg='red')
    except requests.exceptions.ConnectionError as err:
        click.secho(f"Cannot connect to {err.request.url}.", fg='red')
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
    help='Filepath of CSE config file')
@click.option(
    '-s',
    '--skip-check',
    is_flag=True,
    help='Skip CSE installation checks')
def run(ctx, config, skip_check):
    """Run CSE service."""
    try:
        check_python_version(ConsoleMessagePrinter())
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(1)

    try:
        service = Service(config, should_check_config=not skip_check)
        service.run(msg_update_callback=ConsoleMessagePrinter())
    except (NotAcceptableException, VcdException, ValueError, KeyError,
            TypeError) as err:
        click.secho(str(err), fg='red')
    except AmqpConnectionError as err:
        click.secho(str(err), fg='red')
        click.secho("check config file amqp section.", fg='red')
    except requests.exceptions.ConnectionError as err:
        click.secho(f"Cannot connect to {err.request.url}.", fg='red')
    except vim.fault.InvalidLogin:
        click.secho("vCenter login failed (check config file vCenter "
                    "username/password).", fg='red')
    except Exception as err:
        click.secho(str(err), fg='red')
        click.secho("CSE Server failure. Please check the logs.", fg='red')


@template.command(
    'list',
    short_help='List Kubernetes templates')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config_file_name',
    type=click.Path(exists=True),
    metavar='CONFIG_FILE_NAME',
    envvar='CSE_CONFIG',
    default='config.yaml',
    help='Filepath of CSE config file')
@click.option(
    '-d',
    '--display',
    'display_option',
    type=click.Choice(
        [DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_LOCAL, DISPLAY_REMOTE]),
    default=DISPLAY_ALL,
    help='Choose templates to display.')
def list_template(ctx, config_file_name, display_option):
    """List CSE k8s templates."""
    try:
        try:
            check_python_version()
        except Exception as err:
            click.secho(str(err), fg='red')
            sys.exit(1)

        # We don't want to validate config file, because server startup or
        # installation is not being perfomred. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        with open(config_file_name) as config_file:
            config_dict = yaml.safe_load(config_file) or {}

        local_templates = []
        if display_option in (DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_LOCAL):
            client = None
            try:
                # To supress the warning message that pyvcloud prints if
                # ssl_cert verification is skipped.
                if not config_dict['vcd']['verify']:
                    requests.packages.urllib3.disable_warnings()

                client = Client(config_dict['vcd']['host'],
                                api_version=config_dict['vcd']['api_version'],
                                verify_ssl_certs=config_dict['vcd']['verify'])
                credentials = BasicLoginCredentials(
                    config_dict['vcd']['username'],
                    SYSTEM_ORG_NAME,
                    config_dict['vcd']['password'])
                client.set_credentials(credentials)

                org_name = config_dict['broker']['org']
                catalog_name = config_dict['broker']['catalog']
                local_template_definitions = \
                    get_all_k8s_local_template_definition(
                        client=client,
                        catalog_name=catalog_name,
                        org_name=org_name)

                default_template_name = \
                    config_dict['broker']['default_template_name']
                default_template_revision = \
                    str(config_dict['broker']['default_template_revision'])
                for definition in local_template_definitions:
                    template = {}
                    template['name'] = definition[LocalTemplateKey.NAME]
                    template['revision'] = \
                        definition[LocalTemplateKey.REVISION]
                    template['compute_policy'] = \
                        definition[LocalTemplateKey.COMPUTE_POLICY]
                    template['local'] = True
                    template['remote'] = False
                    if str(definition[LocalTemplateKey.REVISION]) == default_template_revision and definition[LocalTemplateKey.NAME] == default_template_name: # noqa: E501
                        template['default'] = True
                    else:
                        template['default'] = False
                    template['deprecated'] = definition[LocalTemplateKey.DEPRECATED] # noqa: E501
                    template['cpu'] = definition[LocalTemplateKey.CPU]
                    template['memory'] = definition[LocalTemplateKey.MEMORY]
                    template['description'] = definition[LocalTemplateKey.DESCRIPTION] # noqa: E501
                    template['admin_password'] = definition[LocalTemplateKey.ADMIN_PASSWORD] # noqa: E501
                    local_templates.append(template)
            finally:
                if client:
                    client.logout()

        remote_templates = []
        if display_option in (DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_REMOTE):
            rtm = RemoteTemplateManager(
                remote_template_cookbook_url=config_dict['broker']['remote_template_cookbook_url'], # noqa: E501
                msg_update_callback=ConsoleMessagePrinter())
            remote_template_cookbook = rtm.get_remote_template_cookbook()
            remote_template_definitions = remote_template_cookbook['templates']
            for definition in remote_template_definitions:
                template = {}
                template['name'] = definition[RemoteTemplateKey.NAME]
                template['revision'] = definition[RemoteTemplateKey.REVISION]
                template['compute_policy'] = \
                    definition[RemoteTemplateKey.COMPUTE_POLICY]
                template['local'] = False
                template['remote'] = True
                template['default'] = False
                template['deprecated'] = \
                    definition[RemoteTemplateKey.DEPRECATED]
                template['cpu'] = definition[RemoteTemplateKey.CPU]
                template['memory'] = definition[RemoteTemplateKey.MEMORY]
                template['description'] = \
                    definition[RemoteTemplateKey.DESCRIPTION]
                template['admin_password'] = \
                    definition[RemoteTemplateKey.ADMIN_PASSWORD]
                remote_templates.append(template)

        result = []
        if display_option is DISPLAY_ALL:
            result = remote_templates
            # If local copy of template exists, update the remote definition
            # with relevant values, else add the local definition to the result
            # list.
            for local_template in local_templates:
                found = False
                for remote_template in remote_templates:
                    if str(local_template[LocalTemplateKey.REVISION]) == str(remote_template[RemoteTemplateKey.REVISION]) and local_template[LocalTemplateKey.NAME] == remote_template[RemoteTemplateKey.NAME]: # noqa: E501
                        remote_template['compute_policy'] = \
                            local_template['compute_policy']
                        remote_template['local'] = local_template['local']
                        remote_template['default'] = local_template['default']
                        found = True
                        break
                if not found:
                    result.append(local_template)
        elif display_option in DISPLAY_DIFF:
            for remote_template in remote_templates:
                found = False
                for local_template in local_templates:
                    if str(local_template[LocalTemplateKey.REVISION]) == str(remote_template[RemoteTemplateKey.REVISION]) and local_template[LocalTemplateKey.NAME] == remote_template[RemoteTemplateKey.NAME]: # noqa: E501
                        found = True
                        break
                if not found:
                    result.append(remote_template)
        elif display_option in DISPLAY_LOCAL:
            result = local_templates
        elif display_option in DISPLAY_REMOTE:
            result = remote_templates

        stdout(result, ctx, sort_headers=False)
    except Exception as err:
        click.secho(str(err), fg='red')


if __name__ == '__main__':
    cli()
