#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from copy import deepcopy
import os
from pathlib import Path
import sys
import time

import click
import cryptography
import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import BadRequestException
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import VcdException
import requests
from vcd_cli.utils import stdout
import yaml

from container_service_extension.common.constants.config_constants import KNOWN_EXTRA_OPTIONS  # noqa: E501
import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.config_utils as config_utils
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.installer.config_validator as config_validator  # noqa: E501
import container_service_extension.installer.configure_cse as configure_cse
from container_service_extension.installer.cse_service_role_mgr import create_cse_service_role  # noqa : E501
import container_service_extension.installer.sample_generator as sample_generator  # noqa: E501
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
from container_service_extension.installer.templates.remote_template_manager import RemoteTemplateManager  # noqa: E501
import container_service_extension.installer.templates.tkgm_template_manager as ttm  # noqa: E501
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import OperationStatus
from container_service_extension.lib.telemetry.constants import PayloadKey
from container_service_extension.lib.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.lib.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.lib.telemetry.telemetry_utils \
    import update_with_telemetry_settings
from container_service_extension.logging.logger import INSTALL_LOGGER
from container_service_extension.logging.logger import INSTALL_WIRELOG_FILEPATH
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.logging.logger import SERVER_CLI_LOGGER
from container_service_extension.logging.logger import SERVER_CLI_WIRELOG_FILEPATH  # noqa: E501
from container_service_extension.logging.logger import SERVER_CLOUDAPI_WIRE_LOGGER  # noqa: E501
from container_service_extension.logging.logger import SERVER_DEBUG_WIRELOG_FILEPATH  # noqa: E501
from container_service_extension.logging.logger import SERVER_LOGGER
from container_service_extension.security.encryption_engine import decrypt_file
from container_service_extension.security.encryption_engine import encrypt_file
from container_service_extension.security.encryption_engine import get_decrypted_file_contents  # noqa: E501
import container_service_extension.server.service as cse_service

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Template display options
DISPLAY_NATIVE = "native"
DISPLAY_DIFF = "diff"
DISPLAY_LOCAL = "local"
DISPLAY_REMOTE = "remote"
DISPLAY_TKGM = "tkg"

# Prompt messages
PASSWORD_FOR_CONFIG_ENCRYPTION_MSG = "Password for config file encryption"
PASSWORD_FOR_CONFIG_DECRYPTION_MSG = "Password for config file decryption"
USERNAME_FOR_SYSTEM_ADMINISTRATOR = "Username for System Administrator"
PASSWORD_FOR_SYSTEM_ADMINISTRATOR = "Password for "


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
        cse install --config config.yaml --skip-config-decryption
            Install CSE using configuration specified in 'config.yaml'.
\b
        cse install -c encrypted-config.yaml
            Install CSE using configuration specified in 'encrypted-config.yaml'.
            The configuration file will be decrypted in memory using a password
            (user will be prompted for the password).
\b
        cse install -c encrypted-config.yaml --pks-config encrypted-pks-config.yaml
            Install CSE using configuration specified in 'encrypted-config.yaml'
            and 'encrypted-pks-config.yaml'. Both these files will be decrypted
            in memory using the same password (user will be prompted for the
            password).
\b
        cse install -c config.yaml --force-update --skip-config-decryption
            Install CSE, and if the templates already exist in vCD, create
            them again.
\b
        cse upgrade --config config.yaml --skip-config-decryption
            Upgrade CSE using configuration specified in 'config.yaml'.
\b
        cse upgrade -c encrypted-config.yaml
            Upgrade CSE using configuration specified in
            'encrypted-config.yaml'. The configuration file will be decrypted
            in memory using a password (user will be prompted for the password).
\b
        cse pks-configure --skip-config-decryption pks_config.yaml
            Configure CSE for PKS using pks_config.yaml. Skip decryption of
            the config information.
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
        cse run -c encrypted-config.yaml
            Run CSE Server using configuration supplied via 'encrypted-config.yaml'.
            Will first validate that CSE was installed according to
            'encrypted-config.yaml'. User will be prompted for the password
            required for decrypting 'encrypted-config.yaml'.
\b
        cse run -c encrypted-config.yaml --pks-config encrypted-pks-config.yaml
            Run CSE Server using configuration specified in 'encrypted-config.yaml'
            and 'encrypted-pks-config.yaml'. Also validate that CSE has been
            installed according to 'encrypted-config.yaml' and PKS was installed
            according to 'encrypted-pks-config.yaml'. User will be prompted for
            the password required to decrypt both the configuration files.
\b
        cse run -c encrypted-config.yaml --skip-check
            Run CSE Server using configuration specified in 'encrypted-config.yaml'
            without first validating that CSE was installed according
            to 'encrypted-config.yaml'. User will be prompted for the password
            required to decrypt the configuration file.
\b
        cse run -c config.yaml --skip-check --skip-config-decryption
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
        cse template install my_template 1 -c my_config.yaml
            Installs my_template at revision 1 specified in the remote template
            repository URL specified in my_config.yaml
\b
        cse template install * * -c my_config.yaml
            Installs all templates specified in the remote template
            repository URL specified in my_config.yaml
\b
        cse template import -F my_tkg_ova -c my_config.yaml
            Imports TKG ova into VCD catalog specified in config file
\b
        cse template import -F my_tkg_ova -x vcd_host HOST -x username USERNAME -x vcd_verify Yes -x org_name MY_ORG -x catalog_name MY_CATALOG
            Imports TKG ova into VCD catalog specified by the extra options.

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
        console_message_printer = utils.ConsoleMessagePrinter()
        console_message_printer.general_no_color(ctx.get_help())
        return


@cli.group(short_help='Manage native Kubernetes runtime templates')
@click.pass_context
def template(ctx):
    """Manage native Kubernetes runtime templates.

\b
    Examples, by default, following commands expect an encrypted CSE
    configuration file. To use a plain-text configuration file instead, specify
    the flag --skip-config-decryption.
\b
        cse template list -c encrypted-config.yaml
            Display all templates, including the ones that are currently in the local
            catalog, and the ones that are defined in remote template repository.
            'encrypted-config.yaml' will be decrypted with the password received
            from user via a console prompt.
\b
        cse template list -c config.yaml --skip-config-decryption
            Display all templates, including the ones that are currently in the local
            catalog, and the ones that are defined in remote template repository.
\b
        cse template list -c config.yaml --display local --skip-config-decryption
            Display templates that are currently in the local catalog.
\b
        cse template list -c config.yaml --display remote --skip-config-decryption
            Display templates that are defined in the remote template repository.
\b
        cse template list -c config.yaml --display diff --skip-config-decryption
            Display only templates that are defined in remote template repository
            but not present in the local catalog.
\b
        cse template install -c config.yaml --skip-config-decryption
            Install all templates defined in remote template repository that are
            missing from the local catalog.
\b
        cse template install -c encrypted-config.yaml
            Install all templates defined in remote template repository that are
            missing from the local catalog. 'encrypted-config.yaml' will be
            decrypted with the password received from user via a console prompt.
\b
        cse template install [template name] [template revision] -c encrypted-config.yaml
            Install a particular template at a given revision defined in remote
            template repository that is missing from the local catalog.
            'encrypted-config.yaml' will be decrypted with the password received
            from user via a console prompt.
\b
        cse template install -c config.yaml --force --skip-config-decryption
            Install all templates defined in remote template repository. Templates
            already present in the local catalog that match with one in the remote
            repository will be recreated from scratch.
\b
        cse template import -F my_tkg_ova -c my_config.yaml
            Imports TKG ova into VCD catalog specified in config file
\b
        cse template import -F my_tkg_ova -x vcd_host HOST -x username USERNAME -x vcd_verify Yes -x org_name MY_ORG -x catalog_name MY_CATALOG
            Imports TKG ova into VCD catalog specified by the extra options.
    """  # noqa: E501
    pass


@cli.command(short_help='Display CSE version')
@click.pass_context
def version(ctx):
    """Display CSE version."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    cse_info = utils.get_cse_info()
    ver_str = '%s, %s, version %s' % (cse_info['product'],
                                      cse_info['description'],
                                      cse_info['version'])
    stdout(cse_info, ctx, ver_str)


@cli.command(short_help='Create CSE service role for CSE install/upgrade/run')
@click.pass_context
@click.argument('vcd_host', metavar='VCD_HOST')
@click.option(
    '-s',
    '--skip-verify-ssl-certs',
    is_flag=True,
    help='Skip verifying SSL certificates of VCD Host')
def create_service_role(ctx, vcd_host, skip_verify_ssl_certs):
    """Create CSE service Role."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    requests.packages.urllib3.disable_warnings()

    # The console_message_printer is not being passed to the python version
    # check, because we want to suppress the version check messages from being
    # printed onto console.
    utils.check_python_version()

    # Prompt user for administrator username/password
    admin_username = utils.prompt_text(USERNAME_FOR_SYSTEM_ADMINISTRATOR,
                                       color='green', hide_input=False)
    admin_password = utils.prompt_text(PASSWORD_FOR_SYSTEM_ADMINISTRATOR + str(admin_username),  # noqa: E501
                                       color='green', hide_input=True)

    msg = f"Connecting to vCD: {vcd_host}"
    console_message_printer.general_no_color(msg)
    SERVER_CLI_LOGGER.info(msg)

    client = None
    try:
        client = vcd_client.Client(vcd_host, verify_ssl_certs=not skip_verify_ssl_certs)  # noqa: E501
        credentials = vcd_client.BasicLoginCredentials(
            admin_username,
            shared_constants.SYSTEM_ORG_NAME,
            admin_password)
        client.set_credentials(credentials)

        msg = f"Connected to vCD as system administrator: {admin_username}"
        console_message_printer.general_no_color(msg)
        SERVER_CLI_LOGGER.info(msg)
        msg = "Creating CSE Service Role..."
        console_message_printer.general_no_color(msg)
        SERVER_CLI_LOGGER.info(msg)

        try:
            create_cse_service_role(
                client,
                msg_update_callback=console_message_printer,
                logger_debug=SERVER_CLI_LOGGER)
        except EntityNotFoundException as err:
            msg = "CSE Internal Error, Please contact support"
            console_message_printer.error(msg)
            SERVER_CLI_LOGGER.error(msg)
            console_message_printer.error(str(err))
            SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        except BadRequestException as err:
            msg = "CSE Service Role already Exists"
            console_message_printer.error(msg)
            console_message_printer.error(str(err))
            SERVER_CLI_LOGGER.error(msg)
            SERVER_CLI_LOGGER.error(str(err), exc_info=True)
    except requests.exceptions.ConnectionError as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
    except VcdException as err:
        msg = f"Incorrect SystemOrg Username: {admin_username} and/or Password"
        console_message_printer.error(msg)
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(msg)
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
    except Exception as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
    finally:
        if client is not None:
            client.logout()


@cli.command(short_help='Generate sample CSE/PKS configuration')
@click.pass_context
@click.option(
    '-o',
    '--output',
    'output_file_name',
    required=False,
    default=None,
    metavar='OUTPUT_FILE_NAME',
    help="Filepath to write configuration file to")
@click.option(
    '-p',
    '--pks-config',
    'generate_pks_config',
    is_flag=True,
    help='Generate only sample PKS config')
@click.option(
    '-l',
    '--legacy-mode',
    'legacy_mode',
    required=False,
    is_flag=True,
    help="Generate sample config for legacy type")
@click.option(
    '-x',
    '--extra-option',
    'extra_options',
    metavar='EXTRA_OPTION',
    nargs=2,
    type=(str, str),
    multiple=True,
    help='Allows avoiding prompts if --config is omitted'
)
def sample(
    ctx,
    output_file_name,
    generate_pks_config,
    legacy_mode,
    extra_options
):
    """Display sample CSE config file contents."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    # The console_message_printer is not being passed to the python version
    # check, because we want to suppress the version check messages from being
    # printed onto console, and pollute the sample config.
    utils.check_python_version()

    try:
        sample_config = sample_generator.generate_sample_cse_config(
            legacy_mode=legacy_mode
        )

        sanitized_user_input = config_utils.sanitize_typing(
            user_input=extra_options,
            known_extra_options=KNOWN_EXTRA_OPTIONS
        )
        user_input_config = config_utils.construct_config_from_extra_options(
            user_input=sanitized_user_input,
            known_extra_options=KNOWN_EXTRA_OPTIONS
        )
        sample_config = config_utils.merge_dict_recursive(
            sample_config,
            user_input_config
        )

        sample_config_text = sample_generator.generate_sample_config_text(
            sample_config=sample_config,
            output_file_name=output_file_name,
            generate_pks_config=generate_pks_config,
            legacy_mode=legacy_mode
        )
    except Exception as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        sys.exit(1)

    console_message_printer.general_no_color(sample_config_text)
    SERVER_CLI_LOGGER.debug(sample_config_text)


@cli.command(short_help="Checks that CSE/PKS config file is valid. Can "
                        "also check that CSE/PKS is installed according to "
                        "the config file(s)")
@click.pass_context
@click.argument('config_file_path', metavar='CONFIG_FILE_NAME',
                envvar='CSE_CONFIG',
                default='config.yaml',
                type=click.Path(exists=True))
@click.option(
    '-p',
    '--pks-config-file',
    'pks_config_file_path',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_PATH',
    required=False,
    help='Filepath to PKS config file')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE/PKS config file')
@click.option(
    '-i',
    '--check-install',
    'check_install',
    is_flag=True,
    help='Checks that CSE/PKS is installed on vCD according '
         'to the config file')
def check(ctx, config_file_path, pks_config_file_path, skip_config_decryption,
          check_install):
    """Validate CSE config file."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    config_dict = None
    try:
        config_dict = config_validator.get_validated_config(
            config_file_name=config_file_path,
            pks_config_file_name=pks_config_file_path,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=SERVER_CLI_WIRELOG_FILEPATH,
            logger_debug=SERVER_CLI_LOGGER,
            msg_update_callback=console_message_printer)

        if check_install:
            try:
                configure_cse.check_cse_installation(
                    config_dict, msg_update_callback=console_message_printer)
            except Exception as err:
                msg = f"Error : {err}\nCSE installation is invalid"
                SERVER_CLI_LOGGER.error(msg)
                console_message_printer.error(msg)
                raise

        # Record telemetry data on successful completion
        record_user_action(
            cse_operation=CseOperation.CONFIG_CHECK,
            telemetry_settings=config_dict['service']['telemetry'])
        # Telemetry data construction
        cse_params = {
            PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(pks_config_file_path),  # noqa: E501
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption),
            PayloadKey.WAS_INSTALLATION_CHECKED: bool(check_install)
        }
        # Record telemetry data
        record_user_action_details(
            cse_operation=CseOperation.CONFIG_CHECK,
            cse_params=cse_params,
            telemetry_settings=config_dict['service']['telemetry'])
    except Exception as err:
        # Record telemetry data on failed operation
        if config_dict:
            record_user_action(
                cse_operation=CseOperation.CONFIG_CHECK,
                status=OperationStatus.FAILED,
                telemetry_settings=config_dict['service']['telemetry'])
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        sys.exit(1)
    finally:
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


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
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    try:
        try:
            password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
                PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
                hide_input=True,
                color='green')
            decrypt_file(input_file, password, output_file)
            msg = "Decryption successful."
            console_message_printer.general(msg)
            SERVER_CLI_LOGGER.debug(msg)
        except cryptography.fernet.InvalidToken:
            raise Exception("Decryption failed: Invalid password")
    except Exception as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        sys.exit(1)


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
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    try:
        try:
            password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
                PASSWORD_FOR_CONFIG_ENCRYPTION_MSG,
                hide_input=True,
                color='green')
            encrypt_file(input_file, password, output_file)
            msg = "Encryption successful."
            console_message_printer.general(msg)
            SERVER_CLI_LOGGER.debug(msg)
        except cryptography.fernet.InvalidToken:
            raise Exception("Encryption failed: Invalid password")
    except Exception as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        sys.exit(1)


@cli.command(short_help='Install CSE extension 3.1.0 on vCD')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config_file_path',
    default='config.yaml',
    metavar='CONFIG_FILE_PATH',
    type=click.Path(exists=True),
    envvar='CSE_CONFIG',
    required=True,
    help="(Required) Filepath to CSE config file")
@click.option(
    '-p',
    '--pks-config-file',
    'pks_config_file_path',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_PATH',
    required=False,
    help='Filepath to PKS config file')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE/PKS config file')
def install(ctx, config_file_path, pks_config_file_path,
            skip_config_decryption):
    """Install CSE on Cloud Director.

\b
    - legacy_mode is config property that is used to configure CSE with
      desired version of VCD.
    - Set legacy_mode=true if CSE 3.1 is configured with VCD whose maximum
      supported api_version < 35.
    - Set legacy_mode=false if CSE 3.1 is configured with VCD whose maximum
      supported api_version >= 35.
    - Note: legacy_mode=true is a valid condition for CSE 3.1 configured with
      VCD whose maximum supported api_version >= 35. However, it is strongly
      recommended to set the property to false to leverage the new
      functionality.
    - When legacy_mode=true, supported template information are based on
      remote-template-cookbook version "1.0.0".
    - When legacy_mode=false, supported template information are based on
      remote-template-cookbook version "2.0.0".
    """
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True
        )

    try:
        config = config_validator.get_validated_config(
            config_file_name=config_file_path,
            pks_config_file_name=pks_config_file_path,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=INSTALL_WIRELOG_FILEPATH,
            logger_debug=INSTALL_LOGGER,
            msg_update_callback=console_message_printer
        )

        configure_cse.install_cse(
            config_file_name=config_file_path,
            config=config,
            pks_config_file_name=pks_config_file_path,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer
        )
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


@cli.command(short_help='Configure PKS')
@click.pass_context
@click.argument(
    'pks_config_file_path',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_PATH')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of PKS config file')
def pks_configure(ctx, pks_config_file_path, skip_config_decryption):

    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)
    requests.packages.urllib3.disable_warnings()

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)
    try:
        try:
            utils.check_file_permissions(
                pks_config_file_path,
                msg_update_callback=console_message_printer)
            # TODO: reading pks config to be made common for cse install
            if skip_config_decryption:
                with open(pks_config_file_path) as f:
                    pks_config = yaml.safe_load(f) or {}
            else:
                console_message_printer.info(
                    f"Decrypting '{pks_config_file_path}'")
                pks_config = yaml.safe_load(
                    get_decrypted_file_contents(pks_config_file_path,
                                                password)) or {}
            configure_cse.configure_nsxt_for_cse(
                nsxt_servers=pks_config['nsxt_servers'],
                log_wire=True,
                msg_update_callback=console_message_printer
            )
        except requests.exceptions.SSLError as err:
            raise Exception(f"SSL verification failed: {str(err)}")
        except requests.exceptions.ConnectionError as err:
            raise Exception(f"Cannot connect to {err.request.url}.")
        except cryptography.fernet.InvalidToken:
            raise Exception(server_constants.CONFIG_DECRYPTION_ERROR_MSG)
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        console_message_printer.error(str(err))
        sys.exit(1)


@cli.command(short_help='Run CSE service')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config_file_path',
    default='config.yaml',
    metavar='CONFIG_FILE_PATH',
    type=click.Path(exists=True),
    envvar='CSE_CONFIG',
    required=True,
    help="(Required) Filepath to CSE config file")
@click.option(
    '-p',
    '--pks-config-file',
    'pks_config_file_path',
    type=click.Path(exists=True),
    metavar='PKS_CONFIG_FILE_PATH',
    required=False,
    help='Filepath to PKS config file')
@click.option(
    '--skip-check',
    is_flag=True,
    help='Skip CSE installation checks')
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE/PKS config file')
def run(ctx, config_file_path, pks_config_file_path, skip_check,
        skip_config_decryption):
    """Run CSE service.

    legacy_mode is config property that is used to configure CSE with
    desired version of VCD.
    Set legacy_mode=true if CSE 3.1 is configured with VCD whose maximum
    supported api_version < 35.
    Set legacy_mode=false if CSE 3.1 is configured with VCD whose maximum
    supported api_version >= 35.
    Note: legacy_mode=true is a valid condition for CSE 3.1 configured with
    VCD whose maximum supported api_version >= 35. However, it is strongly
    recommended to set the property to false to leverage the new functionality.

    """
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)
    cse_version = utils.get_cse_version()
    console_message_printer.general_no_color(f"CSE version: {cse_version}")

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    config = None
    cse_run_complete = False
    try:
        config = config_validator.get_validated_config(
            config_file_name=config_file_path,
            pks_config_file_name=pks_config_file_path,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=SERVER_DEBUG_WIRELOG_FILEPATH,
            logger_debug=SERVER_LOGGER,
            msg_update_callback=console_message_printer)
        service = cse_service.Service(
            config_file=config_file_path,
            config=config,
            pks_config_file=pks_config_file_path,
            should_check_config=not skip_check,
            skip_config_decryption=skip_config_decryption)
        service.run(msg_update_callback=console_message_printer)
        cse_run_complete = True
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        console_message_printer.error(str(err))
        console_message_printer.error("CSE Server failure. Please check the logs.")  # noqa: E501
        sys.exit(1)
    finally:
        if not cse_run_complete:
            telemetry_settings = config['service']['telemetry'] if config else None  # noqa: E501
            record_user_action(cse_operation=CseOperation.SERVICE_RUN,
                               status=OperationStatus.FAILED,
                               telemetry_settings=telemetry_settings)  # noqa: E501
            # block the process to let telemetry handler to finish posting
            # data to VAC. HACK!!!
            time.sleep(3)


@cli.command('upgrade',
             short_help="Upgrade CSE extension to version 3.1.0 on vCD")
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config_file_path',
    default='config.yaml',
    metavar='CONFIG_FILE_PATH',
    type=click.Path(exists=True),
    envvar='CSE_CONFIG',
    required=True,
    help="Filepath to CSE config file")
@click.option(
    '-s',
    '--skip-config-decryption',
    'skip_config_decryption',
    is_flag=True,
    help='Skip decryption of CSE config file')
def upgrade(ctx, config_file_path, skip_config_decryption):
    """Upgrade existing CSE installation/entities to match CSE 3.1.1.

\b
    - Add CSE, RDE version, Legacy mode info to VCD's extension data for CSE
    - Register defined entities schema of CSE k8s clusters with VCD
    - Create placement compute policies used by CSE
    - Remove old sizing compute policies created by CSE 2.6 and below
    - Currently installed templates that are no longer compliant with
      new CSE template cookbook will not be recognized by CSE 3.1. Admins can
      safely delete them once new templates are installed and the existing
      clusters are upgraded to newer template revisions.
    - Update existing CSE k8s cluster's to match CSE 3.1 k8s clusters.
    - Upgrading legacy clusters would require new template creation supported
      by CSE 3.1.1
    - legacy_mode is config property that is used to configure CSE with
      desired version of VCD.
    - Set legacy_mode=true if CSE 3.1 is configured with VCD whose maximum
      supported api_version < 35.
    - Set legacy_mode=false if CSE 3.1 is configured with VCD whose maximum
      supported api_version >= 35.
    - NOTE: legacy_mode=true is a valid condition for CSE 3.1 configured with
      VCD whose maximum supported api_version >= 35. However, it is strongly
      recommended to set the property to false to leverage
      the new functionality.
    - When legacy_mode=true, supported template information are based on
      remote-template-cookbook version "1.0.0".
    - When legacy_mode=false, supported template information are based on
      remote-template-cookbook version "2.0.0".
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` in the config is set to false,
    # an exception is thrown if
    # 1. If there is an existing TKG+ template
    # 2. If remote template cookbook contains a TKG+ template.
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green',
            hide_input=True
        )

    try:
        config = config_validator.get_validated_config(
            config_file_name=config_file_path,
            pks_config_file_name='',
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=INSTALL_WIRELOG_FILEPATH,
            logger_debug=INSTALL_LOGGER,
            msg_update_callback=console_message_printer
        )

        configure_cse.upgrade_cse(
            config_file_name=config_file_path,
            config=config,
            msg_update_callback=console_message_printer
        )
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


@template.command(
    'list',
    short_help='List native Kubernetes templates')
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config_file_path',
    default='config.yaml',
    metavar='CONFIG_FILE_PATH',
    type=click.Path(exists=True),
    envvar='CSE_CONFIG',
    required=True,
    help="(Required) Filepath to CSE config file")
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
        [DISPLAY_NATIVE, DISPLAY_DIFF, DISPLAY_LOCAL, DISPLAY_REMOTE, DISPLAY_TKGM]  # noqa: E501
    ),
    default=DISPLAY_NATIVE,
    help='Choose templates to display.')
def list_template(ctx, config_file_path, skip_config_decryption,
                  display_option):
    """List CSE k8s templates."""
    # TODO(VCDA-2236) Validate legacy_mode in extension
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    # Not passing the console_message_printer, because we want to suppress
    # the python version check messages from being printed onto console.
    utils.check_python_version()

    config_dict = None
    try:
        # We don't want to validate config file, because server startup or
        # installation is not being performed. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        config_dict = _get_unvalidated_config(
            config_file_path=config_file_path,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer
        )

        # Record telemetry details
        cse_params = {
            PayloadKey.DISPLAY_OPTION: display_option,
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption)
        }
        record_user_action_details(
            cse_operation=CseOperation.TEMPLATE_LIST,
            cse_params=cse_params,
            telemetry_settings=config_dict['service']['telemetry']
        )

        log_wire_file = None
        log_wire = utils.str_to_bool(config_dict.get('service', {}).get('log_wire', False))  # noqa: E501
        if log_wire:
            log_wire_file = SERVER_DEBUG_WIRELOG_FILEPATH

        legacy_mode = None
        if 'service' in config_dict:
            if 'legacy_mode' in config_dict.get('service'):
                legacy_mode = config_dict['service']['legacy_mode']
        if legacy_mode is None:
            msg = "Unable to find `legacy_mode` under " \
                  "`service` section in config file."
            raise Exception(msg)

        tkgm_templates = []
        if display_option == DISPLAY_TKGM and not legacy_mode:
            client = None
            try:
                # Note: This will get us a client with highest supported
                # VCD api version.
                client, _ = _get_clients_from_config(
                    config_dict,
                    log_wire_file=log_wire_file,
                    log_wire=log_wire
                )

                org_name = config_dict['broker']['org']
                catalog_name = config_dict['broker']['catalog']

                tkgm_template_definitions = ttm.read_all_tkgm_template(
                    client=client,
                    org_name=org_name,
                    catalog_name=catalog_name,
                    logger=SERVER_CLI_LOGGER
                )

                for definition in tkgm_template_definitions:
                    tkgm_template = {
                        'name': definition[server_constants.TKGmTemplateKey.NAME],  # noqa: E501
                        'revision': int(definition[server_constants.TKGmTemplateKey.REVISION]),  # noqa: E501
                        'local': 'Yes',
                        'remote': 'No',
                        'cpu': 'n/a',
                        'memory': 'n/a',
                        'description': ''
                    }
                    tkgm_templates.append(tkgm_template)
            finally:
                if client:
                    client.logout()

        local_templates = []
        if display_option in (DISPLAY_NATIVE, DISPLAY_DIFF, DISPLAY_LOCAL):
            client = None
            try:
                # Note: This will get us a client with highest supported
                # VCD api version.
                client, _ = _get_clients_from_config(
                    config_dict,
                    log_wire_file=log_wire_file,
                    log_wire=log_wire
                )

                org_name = config_dict['broker']['org']
                catalog_name = config_dict['broker']['catalog']
                is_tkg_plus_enabled = server_utils.is_tkg_plus_enabled(config_dict)  # noqa: E501

                local_template_definitions = \
                    ltm.get_valid_k8s_local_template_definition(
                        client=client,
                        catalog_name=catalog_name,
                        legacy_mode=legacy_mode,
                        is_tkg_plus_enabled=is_tkg_plus_enabled,
                        org_name=org_name,
                        logger_debug=SERVER_CLI_LOGGER)

                for definition in local_template_definitions:
                    local_template = {
                        'name': definition[server_constants.LocalTemplateKey.NAME],  # noqa: E501
                        'revision': int(definition[server_constants.LocalTemplateKey.REVISION]),  # noqa: E501
                        'local': 'Yes',
                        'remote': 'No',
                        'cpu': definition[server_constants.LocalTemplateKey.CPU],  # noqa: E501
                        'memory': definition[server_constants.LocalTemplateKey.MEMORY],  # noqa: E501
                        'description': definition[server_constants.LocalTemplateKey.DESCRIPTION]  # noqa: E501
                    }
                    if legacy_mode:
                        local_template['compute_policy'] = definition[server_constants.LegacyLocalTemplateKey.COMPUTE_POLICY]  # noqa: E501
                    local_template['deprecated'] = 'Yes' if utils.str_to_bool(definition[server_constants.LocalTemplateKey.DEPRECATED]) else 'No'  # noqa: E501

                    local_templates.append(local_template)
            finally:
                if client:
                    client.logout()

        remote_templates = []
        remote_template_keys = None
        if display_option in (DISPLAY_NATIVE, DISPLAY_DIFF, DISPLAY_REMOTE):
            rtm = RemoteTemplateManager(
                remote_template_cookbook_url=config_dict['broker']['remote_template_cookbook_url'],  # noqa: E501
                legacy_mode=config_dict['service']['legacy_mode'],
                logger=SERVER_CLI_LOGGER)
            remote_template_cookbook = \
                rtm.get_filtered_remote_template_cookbook()
            remote_template_definitions = remote_template_cookbook['templates']
            remote_template_keys = server_utils.get_template_descriptor_keys(
                rtm.cookbook_version)
            for definition in remote_template_definitions:
                remote_template = {
                    'name': definition[remote_template_keys.NAME],
                    'revision': definition[remote_template_keys.REVISION],
                    'local': 'No',
                    'remote': 'Yes',
                    'cpu': definition[remote_template_keys.CPU],
                    'memory': definition[remote_template_keys.MEMORY],
                    'description': definition[remote_template_keys.DESCRIPTION]
                }
                if legacy_mode:
                    remote_template['compute_policy'] = \
                        definition[remote_template_keys.COMPUTE_POLICY]
                remote_template['deprecated'] = 'Yes' if utils.str_to_bool(definition[remote_template_keys.DEPRECATED]) else 'No'  # noqa: E501

                remote_templates.append(remote_template)

        result = []
        if display_option is DISPLAY_NATIVE:
            result = remote_templates
            # If local copy of template exists, update the remote definition
            # with relevant values, else add the local definition to the result
            # list.
            for local_template in local_templates:
                found = False
                for remote_template in remote_templates:
                    if (local_template[server_constants.LocalTemplateKey.NAME], local_template[server_constants.LocalTemplateKey.REVISION]) == (remote_template[remote_template_keys.NAME], remote_template[remote_template_keys.REVISION]):  # noqa: E501
                        if legacy_mode:
                            remote_template['compute_policy'] = \
                                local_template['compute_policy']
                        remote_template['local'] = local_template['local']
                        found = True
                        break
                if not found:
                    result.append(local_template)
        elif display_option in DISPLAY_DIFF:
            for remote_template in remote_templates:
                found = False
                for local_template in local_templates:
                    if (local_template[server_constants.LocalTemplateKey.NAME], local_template[server_constants.LocalTemplateKey.REVISION]) == (remote_template[remote_template_keys.NAME], remote_template[remote_template_keys.REVISION]):  # noqa: E501
                        found = True
                        break
                if not found:
                    result.append(remote_template)
        elif display_option in DISPLAY_LOCAL:
            result = local_templates
        elif display_option in DISPLAY_REMOTE:
            result = remote_templates
        elif display_option in DISPLAY_TKGM:
            result = tkgm_templates

        result = sorted(result, key=lambda t: (t['name'], t['revision']), reverse=True)  # noqa: E501
        stdout(result, ctx, sort_headers=False)
        SERVER_CLI_LOGGER.debug(result)
        record_user_action(
            cse_operation=CseOperation.TEMPLATE_LIST,
            telemetry_settings=config_dict['service']['telemetry']
        )
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
        console_message_printer.error(str(err))
        telemetry_settings = config_dict.get('service', {}).get('telemetry') \
            if config_dict else None
        record_user_action(cse_operation=CseOperation.TEMPLATE_LIST,
                           status=OperationStatus.FAILED,
                           telemetry_settings=telemetry_settings)
        sys.exit(1)
    finally:
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


@template.command('install',
                  short_help="Create native Kubernetes templates listed in "
                             "remote template repository. Use '*' for "
                             "TEMPLATE_NAME and TEMPLATE_REVISION to install "
                             "all listed templates.")
@click.pass_context
@click.argument('template_name', metavar='TEMPLATE_NAME', default='*')
@click.argument('template_revision', metavar='TEMPLATE_REVISION', default='*')
@click.option(
    '-c',
    '--config',
    'config_file_path',
    default='config.yaml',
    metavar='CONFIG_FILE_PATH',
    type=click.Path(exists=True),
    envvar='CSE_CONFIG',
    required=True,
    help="(Required) Filepath to CSE config file")
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
                         config_file_path, skip_config_decryption,
                         force_create, retain_temp_vapp,
                         ssh_key_file):
    """Create Kubernetes templates listed in remote template repository.

    Use '*' for TEMPLATE_NAME and TEMPLATE_REVISION to install
    all listed templates.

    legacy_mode is config property that is used to configure CSE with
    desired version of VCD.

    When legacy_mode=true, supported template information are based on
    remote-template-cookbook version "1.0.0".

    When legacy_mode=false, supported template information are based on
    remote-template-cookbook version "2.0.0", min_cse_version and
    max_cse_version.
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` flag in config is set to false,
    # Throw an error if TKG+ template creation is issued.
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    if retain_temp_vapp and not ssh_key_file:
        msg = "Must provide ssh-key file (using --ssh-key OR -k) if " \
              "--retain-temp-vapp is provided, or else temporary vm will be " \
              "inaccessible"
        SERVER_CLI_LOGGER.error(msg)
        console_message_printer.error(msg)
        sys.exit(1)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()

    try:
        config = config_validator.get_validated_config(
            config_file_name=config_file_path,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=INSTALL_WIRELOG_FILEPATH,
            logger_debug=INSTALL_LOGGER,
            msg_update_callback=console_message_printer
        )

        configure_cse.install_template(
            template_name=template_name,
            template_revision=template_revision,
            config_file_name=config_file_path,
            config=config,
            force_create=force_create,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=ssh_key,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer
        )
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


@template.command(
    'import',
    short_help="Import TKG template from local disk into CSE catalog"
)
@click.pass_context
@click.option(
    '-c',
    '--config',
    'config_file_path',
    metavar='CONFIG_FILE_PATH',
    type=click.Path(exists=True),
    envvar='CSE_CONFIG',
    help="Filepath to CSE config file"
)
@click.option(
    '-s',
    '--skip-config-decryption',
    is_flag=True,
    help='Skip decryption of CSE config file'
)
@click.option(
    '-F',
    '--file',
    'ova_file_path',
    metavar='OVA_FILE_PATH',
    type=click.Path(exists=True),
    required=True,
    help="Filepath to the TKG OVA"
)
@click.option(
    '-f',
    '--force',
    'force_import',
    is_flag=True,
    help='Force import TKGm templates on vCD even if they already exist'
)
@click.option(
    '-x',
    '--extra-option',
    'extra_options',
    metavar='EXTRA_OPTION',
    nargs=2,
    type=(str, str),
    multiple=True,
    help='Allows avoiding prompts if --config is omitted'
)
def import_tkgm_template(
        ctx,
        config_file_path,
        skip_config_decryption,
        ova_file_path,
        force_import,
        extra_options
):
    """Upload TKGm OVA to CSE catalog.

\b
    If --config option is not provided, the command will prompt for required
    information. However the prompts can be avoided by specifying the values
    using -x/--extra-option.
\b
    Essential supported Extra Options:
        catalog_name: String: Name of the catalog where the OVA will be
            imported.
        org_name: String: Name of the Organization where the OVA will be
            imported.
        password: String: Password of CSE service account.
        username: String: Username of CSE service account.
        vcd_host: String: FQDN of VCD host.
\b
    Non-essential supported Extra Options:
        enable_telemetry: Boolean : If True, telemetry data will be
            recorded.
        legacy_mode: Boolean: If True, the command will assume that
            CSE is running in legacy mode.
        log_wire: Boolean: If True, log wire communication to VCD.
        mqtt_verify: Boolean: Verify SSL while connecting to MQTT bus.
        vcd_verify: Boolean: Verify SSL while connecting to VCD.
\b
    Note: Arbitrary key value pair can be provided using -x option but there
    is no guarantee that they will be processed or honored.
    """
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = utils.ConsoleMessagePrinter()
    utils.check_python_version(console_message_printer)

    client = None
    config = {}
    try:
        if config_file_path:
            password = None
            if not skip_config_decryption:
                password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(  # noqa: E501
                    PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
                    color='green',
                    hide_input=True
                )

            config = config_validator.get_validated_config(
                config_file_name=config_file_path,
                skip_config_decryption=skip_config_decryption,
                decryption_password=password,
                log_wire_file=INSTALL_WIRELOG_FILEPATH,
                logger_debug=INSTALL_LOGGER,
                msg_update_callback=console_message_printer
            )
        else:
            required_options = [
                "vcd_host",
                "username",
                "password",
                "org_name",
                "catalog_name"
            ]

            sanitized_extra_options = config_utils.sanitize_typing(
                user_input=extra_options,
                known_extra_options=KNOWN_EXTRA_OPTIONS
            )

            additional_user_input = \
                config_utils.prompt_for_missing_required_extra_options(
                    user_input=sanitized_extra_options,
                    known_extra_options=KNOWN_EXTRA_OPTIONS,
                    required_options=required_options
                )

            sanitized_extra_options.update(additional_user_input)

            # Augment with default value for missing non-essential options
            for k, v in KNOWN_EXTRA_OPTIONS.items():
                if k not in sanitized_extra_options:
                    sanitized_extra_options[k] = v['default_value']

            config = config_utils.construct_config_from_extra_options(
                user_input=sanitized_extra_options,
                known_extra_options=KNOWN_EXTRA_OPTIONS
            )

            # To suppress the warning message that pyvcloud prints if
            # ssl_cert verification is skipped.
            if not config['vcd']['verify']:
                requests.packages.urllib3.disable_warnings()

            log_wire_file = None
            log_wire = utils.str_to_bool(config['service']['log_wire'])
            if log_wire:
                log_wire_file = SERVER_DEBUG_WIRELOG_FILEPATH

            config = config_validator.add_additional_details_to_config(
                config=config,
                vcd_host=config['vcd']['host'],
                vcd_username=config['vcd']['username'],
                vcd_password=config['vcd']['password'],
                verify_ssl=config['vcd']['verify'],
                is_legacy_mode=config['service']['legacy_mode'],
                is_mqtt_exchange=server_utils.should_use_mqtt_protocol(config),
                log_wire=config['service']['log_wire'],
                log_wire_file=log_wire_file
            )

        p = Path(ova_file_path)
        if not p.is_file():
            raise Exception("Provided file location is not a file.")
        ova_file_name = p.name
        os_version_from_ova_name, kubernetes_version_from_ova_name = \
            ttm.parse_tkgm_template_name(ova_file_name)

        if not os_version_from_ova_name or not kubernetes_version_from_ova_name:  # noqa: E501
            msg = "Provided OVA doesn't seem to be a standard TKGm OVA. " \
                  "Do you still want to continue? [y/n]"
            answer = utils.prompt_text(msg, color='green')
            if answer.lower() not in ["yes", "y"]:
                console_message_printer.general(
                    "Aborting import of TKGm OVA."
                )
                return

        log_filename = None
        log_wire = utils.str_to_bool(config['service'].get('log_wire'))
        if log_wire:
            log_filename = INSTALL_WIRELOG_FILEPATH
        client, _ = _get_clients_from_config(
            config,
            log_wire_file=log_filename,
            log_wire=log_wire
        )

        catalog_name = config['broker']['catalog']
        p_no_ext = p.with_suffix('')
        ova_file_name_no_ext = p_no_ext.name
        catalog_item_name = ova_file_name_no_ext
        org_name = config['broker']['org']
        success = ttm.upload_tkgm_template(
            client=client,
            ova_file_path=ova_file_path,
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name,
            org_name=org_name,
            force=force_import,
            logger=INSTALL_LOGGER,
            msg_update_callback=console_message_printer
        )
        if not success:
            return

        property_map = ttm.get_template_property(
            client=client,
            org_name=org_name,
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name
        )
        os_name_from_property_map = property_map.get(server_constants.TKGmProperty.DISTRO_NAME)  # noqa: E501
        os_version_from_property_map = property_map.get(server_constants.TKGmProperty.DISTRO_VERSION)  # noqa: E501
        containerd_version_from_property_map = property_map.get(server_constants.TKGmProperty.CONTAINDERD_VERSION)  # noqa: E501
        kubernetes_version_from_property_map = property_map.get(server_constants.TKGmProperty.KUBERNETES_SEMVER)  # noqa: E501

        cse_version = utils.get_installed_cse_version()
        kind = shared_constants.ClusterEntityKind.TKG_M.value
        kubernetes = "TKGm"

        os_name = os_name_from_property_map
        if not os_name:
            msg = "Please enter the name of the OS in the template"
            os_name = utils.prompt_text(msg, color='green')
        os_version = os_version_from_property_map or os_version_from_ova_name
        if not os_version:
            msg = "Please enter the version of the OS in the template"
            os_version = utils.prompt_text(msg, color='green')
        kubernetes_version = kubernetes_version_from_property_map or kubernetes_version_from_ova_name  # noqa: E501
        if not kubernetes_version:
            msg = "Please enter the version of kubernetes in the template"
            kubernetes_version = utils.prompt_text(msg, color='green')
        containerd_version = containerd_version_from_property_map
        if not containerd_version:
            msg = "Please enter the version of containerd in the template"
            containerd_version = utils.prompt_text(msg, color='green')

        metadata_dict = {
            server_constants.TKGmTemplateKey.CNI: 'antrea',
            # ToDo: Decide on this
            server_constants.TKGmTemplateKey.CNI_VERSION: '0.0.0',
            server_constants.TKGmTemplateKey.CONTAINER_RUNTIME: 'containerd',
            server_constants.TKGmTemplateKey.CONTAINER_RUNTIME_VERSION: containerd_version,  # noqa: E501
            server_constants.TKGmTemplateKey.CSE_VERSION: cse_version,
            server_constants.TKGmTemplateKey.KIND: kind,
            server_constants.TKGmTemplateKey.KUBERNETES: kubernetes,
            server_constants.TKGmTemplateKey.KUBERNETES_VERSION: kubernetes_version,  # noqa: E501
            server_constants.TKGmTemplateKey.NAME: catalog_item_name,
            server_constants.TKGmTemplateKey.OS: os_name,
            server_constants.TKGmTemplateKey.OS_VERSION: os_version,
            server_constants.TKGmTemplateKey.REVISION: '1'
        }
        cse_params = deepcopy(metadata_dict)
        cse_params[PayloadKey.WAS_DECRYPTION_SKIPPED] = skip_config_decryption
        cse_params[PayloadKey.WERE_TEMPLATES_FORCE_UPDATED] = force_import
        record_user_action_details(
            cse_operation=CseOperation.TEMPLATE_IMPORT,
            cse_params=cse_params,
            telemetry_settings=config['service']['telemetry']
        )
        msg = f"Writing metadata onto catalog item {catalog_item_name}."
        INSTALL_LOGGER.info(msg)
        INSTALL_LOGGER.debug(f"{metadata_dict}")
        console_message_printer.info(msg)
        ttm.save_metadata(
            client=client,
            org_name=org_name,
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name,
            data=metadata_dict,
            keys_to_write=metadata_dict.keys()
        )
        msg = "Successfully imported TKGm OVA."
        INSTALL_LOGGER.debug(msg)
        console_message_printer.general(msg)
        # Record telemetry data on template import completion status
        record_user_action(
            cse_operation=CseOperation.TEMPLATE_IMPORT,
            telemetry_settings=config['service']['telemetry']
        )
    except Exception as err:
        # Record telemetry data on template import completion status
        if config:
            record_user_action(
                cse_operation=CseOperation.TEMPLATE_IMPORT,
                status=OperationStatus.FAILED,
                telemetry_settings=config['service']['telemetry'],
            )

        SERVER_CLI_LOGGER.error(str(err), exc_info=True)
        console_message_printer.error(str(err))
    finally:
        if client:
            client.logout()
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


def _get_unvalidated_config(
        config_file_path,
        skip_config_decryption,
        msg_update_callback=utils.NullPrinter()
):
    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or utils.prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    try:
        if skip_config_decryption:
            with open(config_file_path) as config_file:
                config_dict = yaml.safe_load(config_file) or {}
        else:
            msg_update_callback.info(f"Decrypting '{config_file_path}'")
            config_dict = yaml.safe_load(
                get_decrypted_file_contents(
                    config_file_path,
                    password
                )
            ) or {}
        msg_update_callback.general(
            f"Retrieved config from '{config_file_path}'"
        )

        # To suppress the warning message that pyvcloud prints if
        # ssl_cert verification is skipped.
        if config_dict and config_dict.get('vcd') and \
                not config_dict['vcd'].get('verify'):
            requests.packages.urllib3.disable_warnings()

        # Store telemetry instance id, url and collector id in config
        # This step should be done after suppressing the cert validation
        # warnings
        update_with_telemetry_settings(
            config_dict=config_dict,
            vcd_host=config_dict['vcd']['host'],
            vcd_username=config_dict['vcd']['username'],
            vcd_password=config_dict['vcd']['password'],
            verify_ssl=config_dict['vcd']['verify'],
            is_mqtt_exchange=server_utils.should_use_mqtt_protocol(config_dict)
        )

        return config_dict
    except cryptography.fernet.InvalidToken:
        raise Exception(server_constants.CONFIG_DECRYPTION_ERROR_MSG)


def _get_clients_from_config(config, log_wire_file, log_wire):
    client = vcd_client.Client(
        config['vcd']['host'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file=log_wire_file,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    credentials = vcd_client.BasicLoginCredentials(
        config['vcd']['username'],
        shared_constants.SYSTEM_ORG_NAME,
        config['vcd']['password'])
    client.set_credentials(credentials)

    logger_wire = NULL_LOGGER
    if log_wire:
        logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER

    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client,
        logger_debug=SERVER_CLI_LOGGER,
        logger_wire=logger_wire
    )

    return client, cloudapi_client


if __name__ == '__main__':
    cli()
