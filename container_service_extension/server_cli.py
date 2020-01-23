#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import time

import click
import cryptography
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.utils import metadata_to_dict
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from pyVmomi import vim
import requests
from vcd_cli.utils import stdout
import yaml

from container_service_extension.config_validator import get_validated_config
from container_service_extension.configure_cse import check_cse_installation
from container_service_extension.configure_cse import install_cse
from container_service_extension.configure_cse import install_template
from container_service_extension.encryption_engine import decrypt_file
from container_service_extension.encryption_engine import encrypt_file
from container_service_extension.encryption_engine import get_decrypted_file_contents # noqa: E501
from container_service_extension.exceptions import AmqpConnectionError
import container_service_extension.local_template_manager as ltm
from container_service_extension.remote_template_manager import RemoteTemplateManager # noqa: E501
from container_service_extension.sample_generator import generate_sample_config
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import RemoteTemplateKey
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.service import Service
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.telemetry.telemetry_utils \
    import store_telemetry_settings
from container_service_extension.utils import check_python_version
from container_service_extension.utils import ConsoleMessagePrinter
from container_service_extension.utils import prompt_text
from container_service_extension.utils import str_to_bool
from container_service_extension.vcdbroker import get_all_clusters


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Template display options
DISPLAY_ALL = "all"
DISPLAY_DIFF = "diff"
DISPLAY_LOCAL = "local"
DISPLAY_REMOTE = "remote"

# Prompt messages
PASSWORD_FOR_CONFIG_ENCRYPTION_MSG = "Password for config file encryption"
PASSWORD_FOR_CONFIG_DECRYPTION_MSG = "Password for config file decryption"

# Error messages
AMQP_ERROR_MSG = "Check amqp section of the config file."
CONFIG_DECRYPTION_ERROR_MSG = \
    "Config file decryption failed: invalid decryption password"
VCENTER_LOGIN_ERROR_MSG = "vCenter login failed (check config file for "\
    "vCenter username/password)."


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Container Service Extension for VMware vCloud Director.

\b
    Examples, by default, following commands expect an encrypted CSE
    configuration file. To use a plain-text configuration file instead, specify
    the flag --skip-config-decryption.
\b
        cse version
            Display the software version of the CSE server.
\b
        cse sample
            Generate sample CSE configuration and print it to the console.
\b
        cse sample --pks-config
            Generate sample PKS configuration and print it to the console.
\b
        cse sample --output config.yaml
            Generate sample CSE configuration, and write it to the file
            'config.yaml'.
\b
        cse sample --pks-config --output pks-config.yaml
            Generate sample PKS configuration, and write it to the file
            'pks-config.yaml'
\b
        cse install config.yaml --skip-config-decryption
            Install CSE using configuration specified in 'config.yaml'.
\b
        cse install encrypted-config.yaml
            Install CSE using configuration specified in 'encrypted-config.yaml'.
            The configuration file will be decrypted in memory using a password
            (user will be prompted for the password).
\b
        cse install encrypted-config.yaml --pks-config encrypted-pks-config.yaml
            Install CSE using configuration specified in 'encrypted-config.yaml'
            and 'encrypted-pks-config.yaml'. Both these files will be decrypted
            in memory using the same password (user will be prompted for the
            password).
\b
        cse install config.yaml --force-update --skip-config-decryption
            Install CSE, and if the templates already exist in vCD, create
            them again.
\b
        cse install config.yaml --retain-temp-vapp --ssh-key ~/.ssh/id_rsa.pub
            Install CSE, retain the temporary vApp after the templates have
            been captured. Copy specified SSH key into all template VMs so
            users with the corresponding private key have access (--ssh-key is
            required when --retain-temp-vapp is used).
\b
        cse check config.yaml --skip-config-decryption
            Checks validity of 'config.yaml'.
\b
        cse check config.yaml --pks-config pks-config.yaml --skip-config-decryption
            Checks validity of both config.yaml and 'pks-config.yaml'.
\b
        cse check config.yaml --check-install --skip-config-decryption
            Checks validity of 'config.yaml'.
            Checks that CSE is installed on vCD according to 'config.yaml'
\b
        cse run encrypted-config.yaml
            Run CSE Server using configuration supplied via 'encrypted-config.yaml'.
            Will first validate that CSE was installed according to
            'encrypted-config.yaml'. User will be prompted for the password
            required for decrypting 'encrypted-config.yaml'.
\b
        cse run encrypted-config.yaml --pks-config encrypted-pks-config.yaml
            Run CSE Server using configuration specified in 'encrypted-config.yaml'
            and 'encrypted-pks-config.yaml'. Also validate that CSE has been
            installed according to 'encrypted-config.yaml' and PKS was installed
            according to 'encrypted-pks-config.yaml'. User will be prompted for
            the password required to decrypt both the configuration files.
\b
        cse run encrypted-config.yaml --skip-check
            Run CSE Server using configuration specified in 'encrypted-config.yaml'
            without first validating that CSE was installed according
            to 'encrypted-config.yaml'. User will be prompted for the password
            required to decrypt the configuration file.
\b
        cse run config.yaml --skip-check --skip-config-decryption
            Run CSE Server using configuration specified in plain text 'config.yaml'
            without first validating that CSE was installed according to 'config.yaml'.
\b
        cse encrypt config.yaml --output ~/.configs/encrypted-config.yaml
            Encrypt the plain text configuration file viz. config.yaml and save
            it the encrypted version at the specified location. If --output
            flag is not specified, the encrypted content will be displayed on
            console. User will be prompted to provide a password for encryption.
\b
        cse decrypt config.yaml --output ~./configs/encrypted-config.yaml
            Decrypt the configuration file encrypted-config.yaml and save the
            decrypted content in the file config.yaml. If --output flag is
            not specified the decrypted content will be printed onto console.
            User will be prompted for the password required for decryption.
\b
    Environment Variables
        CSE_CONFIG
            If this environment variable is set, the CSE commands will use the
            file specified in the environment variable as CSE configuration
            file. However if user provides a configuration file along with the
            command, it will override the environment variable. If neither the
            environment variable is set nor user provides a configuration file,
            CSE will try to read configuration from the file 'config.yaml' in
            the current directory.
\b
        CSE_CONFIG_PASSWORD
            If this environment variable is set, the commands will use the
            value provided in this variable to encrypt/decrypt CSE
            configuration file. If this variable is not set, then user will be
            prompted for password to encrypt/decrypt the CSE configuration files.
    """  # noqa: E501
    if ctx.invoked_subcommand is None:
        console_message_printer = ConsoleMessagePrinter()
        console_message_printer.general_no_color(ctx.get_help())
        return


@cli.group(short_help='Manage native Kubernetes provider templates')
@click.pass_context
def template(ctx):
    """Manage native Kubernetes provider templates.

\b
    Examples, by default, following commands expect an encrypted CSE
    configuration file. To use a plain-text configuration file instead, specify
    the flag --skip-config-decryption.
\b
        cse template list encrypted-config.yaml
            Display all templates, including that are currently in the local
            catalog, and the ones that are defined in remote template repository.
            'encrypted-config.yaml' will be decrypted with the password received
            from user via a console prompt.
\b
        cse template list config.yaml --skip-config-decryption
            Display all templates, including that are currently in the local
            catalog, and the ones that are defined in remote template repository.
\b
        cse template list config.yaml --display local --skip-config-decryption
            Display templates that are currently in the local catalog.
\b
        cse template list config.yaml --display remote --skip-config-decryption
            Display templates that are defined in the remote template repository.
\b
        cse template list config.yaml --display diff --skip-config-decryption
            Display only templates that are defined in remote template repository
            but not present in the local catalog.
\b
        cse template install config.yaml --skip-config-decryption
            Install all templates defined in remote template repository that are
            missing from the local catalog.
\b
        cse template install encrypted-config.yaml
            Install all templates defined in remote template repository that are
            missing from the local catalog. 'encrypted-config.yaml' will be
            decrypted with the password received from user via a console prompt.
\b
        cse template install [template name] [template revision] encrypted-config.yaml
            Install a particular template at a given revision defined in remote
            template repository that is missing from the local catalog.
            'encrypted-config.yaml' will be decrypted with the password received
            from user via a console prompt.
\b
        cse template install config.yaml --force --skip-config-decryption
            Install all templates defined in remote template repository. Templates
            already present in the local catalog that match with one in the remote
            repository will be recreated from scratch.
    """  # noqa: E501
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


@cli.command('sample', short_help='Generate sample CSE/PKS configuration')
@click.pass_context
@click.option(
    '-o',
    '--output',
    'output',
    required=False,
    default=None,
    metavar='OUTPUT_FILE_NAME',
    help="Filepath to write configuration file to")
@click.option(
    '-p',
    '--pks-config',
    is_flag=True,
    help='Generate only sample PKS config')
def sample(ctx, output, pks_config):
    """Display sample CSE config file contents."""
    console_message_printer = ConsoleMessagePrinter()
    try:
        # Not passing the console_message_printer, because we want to suppress
        # the python version check messages from being printed onto console,
        # and pollute the sample.
        check_python_version()
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    console_message_printer.general_no_color(
        generate_sample_config(output=output,
                               generate_pks_config=pks_config))


@cli.command(short_help="Checks that CSE/PKS configuration file is valid (Can "
                        "also check that CSE/PKS is installed according to "
                        "the configuration file(s))")
@click.pass_context
@click.argument('config', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '--pks-config',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_NAME',
    required=False,
    help='Filepath of the PKS configuration file')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE/PKS configuration file')
@click.option(
    '-i',
    '--check-install',
    'check_install',
    is_flag=True,
    help='Checks that CSE/PKS is installed on vCD according '
         'to the configuration file')
def check(ctx, config, pks_config, skip_config_decryption, check_install):
    """Validate CSE config file."""
    console_message_printer = ConsoleMessagePrinter()
    try:
        check_python_version(ConsoleMessagePrinter())
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if skip_config_decryption:
        password = None
    else:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    config_dict = None
    try:
        config_dict = get_validated_config(
            config, pks_config_file_name=pks_config,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            msg_update_callback=console_message_printer)

        # Telemetry data construction
        cse_params = {
            PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(pks_config),
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption),
            PayloadKey.WAS_INSTALLATION_CHECKED: bool(check_install)
        }
        # Record telemetry data
        record_user_action_details(
            cse_operation=CseOperation.CONFIG_CHECK,
            cse_params=cse_params,
            telemetry_settings=config_dict['service']['telemetry'])
    except AmqpConnectionError:
        console_message_printer.error(AMQP_ERROR_MSG)
        raise
    except requests.exceptions.ConnectionError as err:
        console_message_printer.error(f"Cannot connect to {err.request.url}.")
        sys.exit(1)
    except cryptography.fernet.InvalidToken:
        console_message_printer.error(CONFIG_DECRYPTION_ERROR_MSG)
        sys.exit(1)
    except vim.fault.InvalidLogin:
        console_message_printer.error(VCENTER_LOGIN_ERROR_MSG)
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if config_dict:
        if check_install:
            try:
                check_cse_installation(config_dict, msg_update_callback=ConsoleMessagePrinter())  # noqa: E501
            except Exception as err:
                console_message_printer.error(f"Error : {err}")
                console_message_printer.error("CSE installation is invalid.")
                # Telemetry - Record failed install action
                record_user_action(
                    cse_operation=CseOperation.CONFIG_CHECK,
                    telemetry_settings=config_dict['service']['telemetry'],
                    status=OperationStatus.FAILED, message=str(err))
                sys.exit(1)
        # Telemetry - Record successful install action
        record_user_action(cse_operation=CseOperation.CONFIG_CHECK,
                           telemetry_settings=config_dict['service']['telemetry'])  # noqa: E501


@cli.command(short_help='Decrypt the given file')
@click.pass_context
@click.argument('input_file', metavar='INPUT_FILE',
                type=click.Path(exists=True))
@click.option(
    '-o',
    '--output',
    'output_file',
    required=False,
    default=None,
    metavar='OUTPUT_FILE',
    help='Filepath to write decrypted file to')
def decrypt(ctx, input_file, output_file):
    """Decrypt CSE configuration file."""
    console_message_printer = ConsoleMessagePrinter()
    try:
        check_python_version(console_message_printer)
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG, hide_input=True, color='green')
        decrypt_file(input_file, password, output_file)
    except cryptography.fernet.InvalidToken:
        console_message_printer.error("Decryption failed: Invalid password")
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)
    console_message_printer.general("\nDecryption successful")


@cli.command(short_help='Encrypt the given file')
@click.pass_context
@click.argument('input_file', metavar='INPUT_FILE',
                type=click.Path(exists=True))
@click.option(
    '-o',
    '--output',
    'output_file',
    required=False,
    default=None,
    metavar='OUTPUT_FILE',
    help='Filepath to write encrypted file to')
def encrypt(ctx, input_file, output_file):
    """Encrypt CSE configuration file."""
    console_message_printer = ConsoleMessagePrinter()
    try:
        check_python_version(console_message_printer)
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_ENCRYPTION_MSG, hide_input=True, color='green')
        encrypt_file(input_file, password, output_file)
    except cryptography.fernet.InvalidToken:
        console_message_printer.error("Encryption failed: Invalid password")
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)
    console_message_printer.general("\nEncryption successful")


@cli.command(short_help='Install CSE on vCD')
@click.pass_context
@click.argument('config', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '--pks-config',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_NAME',
    required=False,
    help='Filepath of PKS config file')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE/PKS config file')
@click.option(
    '-t',
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
def install(ctx, config, pks_config, skip_config_decryption,
            skip_template_creation, force_update,
            retain_temp_vapp, ssh_key_file):
    """Install CSE on vCloud Director."""
    console_message_printer = ConsoleMessagePrinter()

    try:
        check_python_version(console_message_printer)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if skip_config_decryption:
        password = None
    else:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    if retain_temp_vapp and not ssh_key_file:
        console_message_printer.error(
            "Must provide ssh-key file (using --ssh-key OR -k) if "
            "--retain-temp-vapp is provided, or else temporary vm will be "
            "inaccessible")
        sys.exit(1)

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()

    try:
        install_cse(config_file_name=config,
                    pks_config_file_name=pks_config,
                    skip_template_creation=skip_template_creation,
                    force_update=force_update, ssh_key=ssh_key,
                    retain_temp_vapp=retain_temp_vapp,
                    skip_config_decryption=skip_config_decryption,
                    decryption_password=password,
                    msg_update_callback=ConsoleMessagePrinter())
    except AmqpConnectionError:
        console_message_printer.error(AMQP_ERROR_MSG)
        raise
    except requests.exceptions.ConnectionError as err:
        console_message_printer.error(f"Cannot connect to {err.request.url}.")
        sys.exit(1)
    except vim.fault.InvalidLogin:
        console_message_printer.error(VCENTER_LOGIN_ERROR_MSG)
        sys.exit(1)
    except cryptography.fernet.InvalidToken:
        console_message_printer.error(CONFIG_DECRYPTION_ERROR_MSG)
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)


@cli.command(short_help='Run CSE service')
@click.pass_context
@click.argument('config', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '--pks-config',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_NAME',
    required=False,
    help='Filepath of PKS config file')
@click.option(
    '--skip-check',
    is_flag=True,
    help='Skip CSE installation checks')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE/PKS config file')
def run(ctx, config, pks_config, skip_check, skip_config_decryption):
    """Run CSE service."""
    console_message_printer = ConsoleMessagePrinter()

    try:
        check_python_version(console_message_printer)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if skip_config_decryption:
        password = None
    else:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    try:
        cse_run_complete = False
        error_message = None
        service = Service(config, pks_config_file=pks_config,
                          should_check_config=not skip_check,
                          skip_config_decryption=skip_config_decryption,
                          decryption_password=password)
        service.run(msg_update_callback=console_message_printer)
        cse_run_complete = True

        # Record telemetry on user action and details of operation.
        cse_params = {
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption),
            PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(pks_config),
            PayloadKey.WAS_INSTALLATION_CHECK_SKIPPED: bool(skip_check)
        }
        record_user_action_details(cse_operation=CseOperation.SERVICE_RUN,
                                   cse_params=cse_params)
        record_user_action(cse_operation=CseOperation.SERVICE_RUN)
    except AmqpConnectionError:
        error_message = AMQP_ERROR_MSG
        console_message_printer.error(AMQP_ERROR_MSG)
        raise
    except requests.exceptions.ConnectionError as err:
        error_message = f"Cannot connect to {err.request.url}."
        console_message_printer.error(error_message)
        sys.exit(1)
    except vim.fault.InvalidLogin:
        error_message = VCENTER_LOGIN_ERROR_MSG
        console_message_printer.error(VCENTER_LOGIN_ERROR_MSG)
        sys.exit(1)
    except cryptography.fernet.InvalidToken:
        error_message = CONFIG_DECRYPTION_ERROR_MSG
        console_message_printer.error(CONFIG_DECRYPTION_ERROR_MSG)
        sys.exit(1)
    except Exception as err:
        error_message = str(err)
        console_message_printer.error(error_message)
        console_message_printer.error(
            "CSE Server failure. Please check the logs.")
        sys.exit(1)
    finally:
        if not cse_run_complete:
            with open(config) as config_file:
                config_dict = yaml.safe_load(config_file) or {}
            store_telemetry_settings(config_dict)
            record_user_action(cse_operation=CseOperation.SERVICE_RUN,
                               status=OperationStatus.FAILED,
                               telemetry_settings=config_dict['service']['telemetry'],  # noqa: E501
                               message=error_message)


@cli.command('convert-cluster', short_help='Converts pre CSE 2.5.2 clusters to CSE 2.5.2+ cluster format') # noqa: E501
@click.pass_context
@click.argument('cluster_name', metavar='CLUSTER_NAME', default=None)
@click.argument('config_file_name', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '--admin-password',
    default=None,
    metavar='ADMIN_PASSWORD',
    help="New root password to set on cluster vms. If left empty password will be auto-generated") # noqa: E501
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    metavar='ORG_NAME',
    help="Only convert clusters from a specific org")
@click.option(
    '-v',
    '--vdc',
    'vdc_name',
    default=None,
    metavar='VDC_NAME',
    help='Only convert clusters from a specific org VDC')
@click.option(
    '-g',
    '--skip-wait-for-gc',
    'skip_wait_for_gc',
    is_flag=True,
    help='Skip waiting for guest customization to finish on vms')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE config file')
def convert_cluster(ctx, config_file_name, skip_config_decryption,
                    cluster_name, admin_password,
                    org_name, vdc_name, skip_wait_for_gc):
    console_message_printer = ConsoleMessagePrinter()

    try:
        check_python_version(console_message_printer)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if skip_config_decryption:
        decryption_password = None
    else:
        decryption_password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    client = None
    try:
        config = get_validated_config(
            config_file_name, skip_config_decryption=skip_config_decryption,
            decryption_password=decryption_password,
            msg_update_callback=console_message_printer)

        # Record telemetry details
        cse_params = {
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption),
            PayloadKey.WAS_GC_WAIT_SKIPPED: bool(skip_wait_for_gc),
            PayloadKey.WAS_OVDC_SPECIFIED: bool(vdc_name),
            PayloadKey.WAS_ORG_SPECIFIED: bool(org_name),
            PayloadKey.WAS_NEW_ADMIN_PASSWORD_PROVIDED: bool(admin_password)

        }
        record_user_action_details(cse_operation=CseOperation.CLUSTER_CONVERT,
                                   cse_params=cse_params,
                                   telemetry_settings=config['service']['telemetry'])  # noqa: E501

        log_filename = None
        log_wire = str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = 'cluster_convert_wire.log'

        client = Client(config['vcd']['host'],
                        api_version=config['vcd']['api_version'],
                        verify_ssl_certs=config['vcd']['verify'],
                        log_file=log_filename,
                        log_requests=log_wire,
                        log_headers=log_wire,
                        log_bodies=log_wire)
        credentials = BasicLoginCredentials(config['vcd']['username'],
                                            SYSTEM_ORG_NAME,
                                            config['vcd']['password'])
        client.set_credentials(credentials)
        msg = f"Connected to vCD as system administrator: " \
              f"{config['vcd']['host']}:{config['vcd']['port']}"
        console_message_printer.general(msg)

        cluster_records = get_all_clusters(client=client,
                                           cluster_name=cluster_name,
                                           org_name=org_name,
                                           ovdc_name=vdc_name)

        if len(cluster_records) == 0:
            console_message_printer.info(f"No clusters were found.")
            return

        vms = []
        for cluster in cluster_records:
            console_message_printer.info(
                f"Processing cluster '{cluster['name']}'.")
            vapp_href = cluster['vapp_href']
            vapp = VApp(client, href=vapp_href)

            # this step removes the old 'cse.template' metadata and adds
            # cse.template.name and cse.template.revision metadata
            # using hard-coded values taken from github history
            console_message_printer.info("Processing metadata of cluster.")
            metadata_dict = metadata_to_dict(vapp.get_metadata())
            old_template_name = metadata_dict.get(ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME) # noqa: E501
            new_template_name = None
            cse_version = metadata_dict.get(ClusterMetadataKey.CSE_VERSION)
            if old_template_name:
                console_message_printer.info(
                    "Determining k8s version on cluster.")
                if 'photon' in old_template_name:
                    new_template_name = 'photon-v2'
                    if cse_version in ('1.0.0'):
                        new_template_name += '_k8s-1.8_weave-2.0.5'
                    elif cse_version in ('1.1.0', '1.2.0', '1.2.1', '1.2.2', '1.2.3', '1.2.4'): # noqa: E501
                        new_template_name += '_k8s-1.9_weave-2.3.0'
                    elif cse_version in ('1.2.5', '1.2.6', '1.2.7',): # noqa: E501
                        new_template_name += '_k8s-1.10_weave-2.3.0'
                    elif cse_version in ('2.0.0'):
                        new_template_name += '_k8s-1.12_weave-2.3.0'
                elif 'ubuntu' in old_template_name:
                    new_template_name = 'ubuntu-16.04'
                    if cse_version in ('1.0.0'):
                        new_template_name += '_k8s-1.9_weave-2.1.3'
                    elif cse_version in ('1.1.0', '1.2.0', '1.2.1', '1.2.2', '1.2.3', '1.2.4', '1.2.5', '1.2.6', '1.2.7'): # noqa: E501
                        new_template_name += '_k8s-1.10_weave-2.3.0'
                    elif cse_version in ('2.0.0'):
                        new_template_name += '_k8s-1.13_weave-2.3.0'

            if new_template_name:
                console_message_printer.info("Updating metadata of cluster.")
                task = vapp.remove_metadata(ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME) # noqa: E501
                client.get_task_monitor().wait_for_success(task)
                new_metadata_to_add = {
                    ClusterMetadataKey.TEMPLATE_NAME: new_template_name,
                    ClusterMetadataKey.TEMPLATE_REVISION: 0
                }
                task = vapp.set_multiple_metadata(new_metadata_to_add)
                client.get_task_monitor().wait_for_success(task)

            # this step uses hard-coded data from the newly updated
            # cse.template.name and cse.template.revision metadata fields as
            # well as github history to add [cse.os, cse.docker.version,
            # cse.kubernetes, cse.kubernetes.version, cse.cni, cse.cni.version]
            # to the clusters
            vapp.reload()
            metadata_dict = metadata_to_dict(vapp.get_metadata())
            template_name = metadata_dict.get(ClusterMetadataKey.TEMPLATE_NAME)
            template_revision = str(metadata_dict.get(ClusterMetadataKey.TEMPLATE_REVISION, '0')) # noqa: E501

            if template_name:
                k8s_version, docker_version = ltm.get_k8s_and_docker_versions(template_name, template_revision=template_revision, cse_version=cse_version) # noqa: E501
                tokens = template_name.split('_')
                new_metadata = {
                    ClusterMetadataKey.OS: tokens[0],
                    ClusterMetadataKey.DOCKER_VERSION: docker_version,
                    ClusterMetadataKey.KUBERNETES: 'upstream',
                    ClusterMetadataKey.KUBERNETES_VERSION: k8s_version,
                    ClusterMetadataKey.CNI: tokens[2].split('-')[0],
                    ClusterMetadataKey.CNI_VERSION: tokens[2].split('-')[1],
                }
                task = vapp.set_multiple_metadata(new_metadata)
                client.get_task_monitor().wait_for_success(task)

            console_message_printer.general(
                "Finished processing metadata of cluster.")

            reset_admin_pw = False
            vm_resources = vapp.get_all_vms()
            for vm_resource in vm_resources:
                try:
                    vapp.get_admin_password(vm_resource.get('name'))
                except EntityNotFoundException:
                    reset_admin_pw = True
                    break

            if reset_admin_pw:
                try:
                    console_message_printer.info(
                        f"Undeploying the vApp '{cluster['name']}'")
                    task = vapp.undeploy()
                    client.get_task_monitor().wait_for_success(task)
                    console_message_printer.general(
                        "Successfully undeployed the vApp.")
                except Exception as err:
                    console_message_printer.error(str(err))

                for vm_resource in vm_resources:
                    console_message_printer.info(
                        f"Processing vm '{vm_resource.get('name')}'.")
                    vm = VM(client, href=vm_resource.get('href'))
                    vms.append(vm)

                    console_message_printer.info("Updating vm admin password")
                    task = vm.update_guest_customization_section(
                        enabled=True,
                        admin_password_enabled=True,
                        admin_password_auto=not admin_password,
                        admin_password=admin_password,
                    )
                    client.get_task_monitor().wait_for_success(task)
                    console_message_printer.general("Successfully updated vm")

                    console_message_printer.info("Deploying vm.")
                    task = vm.power_on_and_force_recustomization()
                    client.get_task_monitor().wait_for_success(task)
                    console_message_printer.general("Successfully deployed vm")

                console_message_printer.info("Deploying cluster")
                task = vapp.deploy(power_on=True)
                client.get_task_monitor().wait_for_success(task)
                console_message_printer.general("Successfully deployed cluster") # noqa: E501

            console_message_printer.general(
                f"Successfully processed cluster '{cluster['name']}'")

        if skip_wait_for_gc:
            # Record telemetry data on successful completion
            record_user_action(cse_operation=CseOperation.CLUSTER_CONVERT, telemetry_settings=config['service']['telemetry'])  # noqa: E501
            return

        while True:
            to_remove = []
            for vm in vms:
                status = vm.get_guest_customization_status()
                if status != 'GC_PENDING':
                    to_remove.append(vm)
            for vm in to_remove:
                vms.remove(vm)
            console_message_printer.info(
                f"Waiting on guest customization to finish on {len(vms)} vms.")
            if not len(vms) == 0:
                time.sleep(5)
            else:
                break
        # # Record telemetry data on successful completion
        record_user_action(cse_operation=CseOperation.CLUSTER_CONVERT, telemetry_settings=config['service']['telemetry'])  # noqa: E501
    except cryptography.fernet.InvalidToken:
        console_message_printer.error(CONFIG_DECRYPTION_ERROR_MSG)
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        # Record telemetry data on failed cluster convert
        record_user_action(cse_operation=CseOperation.CLUSTER_CONVERT,
                           status=OperationStatus.FAILED,
                           telemetry_settings=config['service']['telemetry'])
        sys.exit(1)
    finally:
        if client:
            client.logout()


@template.command(
    'list',
    short_help='List Kubernetes templates')
@click.pass_context
@click.argument('config_file_name', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE config file')
@click.option(
    '-d',
    '--display',
    'display_option',
    type=click.Choice(
        [DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_LOCAL, DISPLAY_REMOTE]),
    default=DISPLAY_ALL,
    help='Choose templates to display.')
def list_template(ctx, config_file_name, skip_config_decryption,
                  display_option):
    """List CSE k8s templates."""
    console_message_printer = ConsoleMessagePrinter()

    try:
        # Not passing the console_message_printer, because we want to suppress
        # the python version check messages from being printed onto console.
        check_python_version()
        requests.packages.urllib3.disable_warnings()
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if skip_config_decryption:
        password = None
    else:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    try:
        # We don't want to validate config file, because server startup or
        # installation is not being performed. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        if skip_config_decryption:
            with open(config_file_name) as config_file:
                config_dict = yaml.safe_load(config_file) or {}
        else:
            console_message_printer.info(f"Decrypting '{config_file_name}'")
            config_dict = yaml.safe_load(
                get_decrypted_file_contents(config_file_name, password)) or {}

        # Store telemetry instance id, url and collector id in config
        store_telemetry_settings(config_dict)

        # Record telemetry details
        cse_params = {PayloadKey.DISPLAY_OPTION: display_option}
        record_user_action_details(cse_operation=CseOperation.TEMPLATE_LIST,
                                   cse_params=cse_params,
                                   telemetry_settings=config_dict['service']['telemetry'])  # noqa: E501

        local_templates = []
        if display_option in (DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_LOCAL):
            client = None
            try:
                # To suppress the warning message that pyvcloud prints if
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
                    ltm.get_all_k8s_local_template_definition(
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
                    template['deprecated'] = \
                        str_to_bool(definition[LocalTemplateKey.DEPRECATED])
                    template['cpu'] = definition[LocalTemplateKey.CPU]
                    template['memory'] = definition[LocalTemplateKey.MEMORY]
                    template['description'] = \
                        definition[LocalTemplateKey.DESCRIPTION]
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
                    str_to_bool(definition[RemoteTemplateKey.DEPRECATED])
                template['cpu'] = definition[RemoteTemplateKey.CPU]
                template['memory'] = definition[RemoteTemplateKey.MEMORY]
                template['description'] = \
                    definition[RemoteTemplateKey.DESCRIPTION]
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
        record_user_action(cse_operation=CseOperation.TEMPLATE_LIST,
                           telemetry_settings=config_dict['service']['telemetry'])  # noqa: E501
    except cryptography.fernet.InvalidToken:
        console_message_printer.error(CONFIG_DECRYPTION_ERROR_MSG)
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        record_user_action(cse_operation=CseOperation.TEMPLATE_LIST,
                           status=OperationStatus.FAILED,
                           message=str(err),
                           telemetry_settings=config_dict['service']['telemetry'])  # noqa: E501
        sys.exit(1)


@template.command('install', short_help='Create Kubernetes templates')
@click.pass_context
@click.argument('template_name', metavar='TEMPLATE_NAME', default='*')
@click.argument('template_revision', metavar='TEMPLATE_REVISION', default='*')
@click.argument('config_file_name', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE config file')
@click.option(
    '-f',
    '--force',
    'force_create',
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
def install_cse_template(ctx, template_name, template_revision,
                         config_file_name, skip_config_decryption,
                         force_create, retain_temp_vapp,
                         ssh_key_file):
    """Create CSE k8s templates."""
    console_message_printer = ConsoleMessagePrinter()

    try:
        check_python_version(ConsoleMessagePrinter())
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)

    if retain_temp_vapp and not ssh_key_file:
        console_message_printer.error(
            "Must provide ssh-key file (using --ssh-key OR -k) if "
            "--retain-temp-vapp is provided, or else temporary vm will be "
            "inaccessible")
        sys.exit(1)

    if skip_config_decryption:
        password = None
    else:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()

    try:
        install_template(
            template_name=template_name,
            template_revision=template_revision,
            config_file_name=config_file_name,
            force_create=force_create,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=ssh_key,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            msg_update_callback=console_message_printer)
    except AmqpConnectionError:
        console_message_printer.error(AMQP_ERROR_MSG)
        raise
    except requests.exceptions.ConnectionError as err:
        console_message_printer.error(f"Cannot connect to {err.request.url}.")
        sys.exit(1)
    except vim.fault.InvalidLogin:
        console_message_printer.error(VCENTER_LOGIN_ERROR_MSG)
        sys.exit(1)
    except cryptography.fernet.InvalidToken:
        console_message_printer.error(CONFIG_DECRYPTION_ERROR_MSG)
        sys.exit(1)
    except Exception as err:
        console_message_printer.error(str(err))
        sys.exit(1)


if __name__ == '__main__':
    cli()
