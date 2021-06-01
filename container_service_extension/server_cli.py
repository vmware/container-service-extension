#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import os
import shutil
import sys
import tempfile
import time
from zipfile import ZipFile

import click
import cryptography
import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import BadRequestException
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import VcdException
import requests
from vcd_cli.utils import stdout
import yaml

from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.config_validator import get_validated_config
import container_service_extension.configure_cse as configure_cse
from container_service_extension.cse_service_role_mgr import create_cse_service_role  # noqa : E501
from container_service_extension.encryption_engine import decrypt_file
from container_service_extension.encryption_engine import encrypt_file
from container_service_extension.encryption_engine import get_decrypted_file_contents  # noqa: E501
import container_service_extension.local_template_manager as ltm
from container_service_extension.logger import INSTALL_LOGGER
from container_service_extension.logger import INSTALL_WIRELOG_FILEPATH
from container_service_extension.logger import NULL_LOGGER
from container_service_extension.logger import SERVER_CLI_LOGGER
from container_service_extension.logger import SERVER_CLI_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_CLOUDAPI_WIRE_LOGGER
from container_service_extension.logger import SERVER_DEBUG_WIRELOG_FILEPATH
from container_service_extension.logger import SERVER_LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.remote_template_manager import RemoteTemplateManager  # noqa: E501
from container_service_extension.sample_generator import generate_sample_config
from container_service_extension.server_constants import CONFIG_DECRYPTION_ERROR_MSG  # noqa: E501
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import RemoteTemplateKey
from container_service_extension.server_constants import SUPPORTED_VCD_API_VERSIONS  # noqa: E501
from container_service_extension.server_constants import SYSTEM_ORG_NAME
import container_service_extension.service as cse_service
from container_service_extension.shared_constants import ClusterEntityKind
from container_service_extension.shared_constants import RequestMethod
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler \
    import record_user_action
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.telemetry.telemetry_utils \
    import store_telemetry_settings
import container_service_extension.utils as utils
from container_service_extension.utils import check_python_version
from container_service_extension.utils import ConsoleMessagePrinter
from container_service_extension.utils import NullPrinter
from container_service_extension.utils import prompt_text
from container_service_extension.utils import str_to_bool


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Template display options
DISPLAY_ALL = "all"
DISPLAY_DIFF = "diff"
DISPLAY_LOCAL = "local"
DISPLAY_REMOTE = "remote"

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
        cse install -c config.yaml --retain-temp-vapp --ssh-key ~/.ssh/id_rsa.pub
            Install CSE, retain the temporary vApp after the templates have
            been captured. Copy specified SSH key into all template VMs so
            users with the corresponding private key have access (--ssh-key is
            required when --retain-temp-vapp is used).
\b
        cse upgrade --config config.yaml --skip-config-decryption
            Upgrade CSE using configuration specified in 'config.yaml'.
\b
        cse upgrade -c encrypted-config.yaml
            Upgrade CSE using configuration specified in
            'encrypted-config.yaml'. The configuration file will be decrypted
            in memory using a password (user will be prompted for the password).
\b
        cse upgrade -c config.yaml --retain-temp-vapp --ssh-key ~/.ssh/id_rsa.pub
            Upgrade CSE, retain the temporary vApp after the templates have
            been captured. Copy specified SSH key into all template VMs so
            users with the corresponding private key have access (--ssh-key is
            required when --retain-temp-vapp is used).
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
        cse template install mytemplate 1 -c myconfig.yaml
            Installs mytemplate at revision 1 specified in the remote template
            repository URL specified in myconfig.yaml
\b
        cse template install * * -c myconfig.yaml
            Installs all templates specified in the remote template
            repository URL specified in myconfig.yaml
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
    """  # noqa: E501
    pass


@cli.group('ui-plugin', short_help='Manage CSE UI plugin')
@click.pass_context
def uiplugin(ctx):
    """Manage vCD UI plugin lifecycle.

\b
    Examples below. By default the following commands expect an encrypted CSE
    configuration file. To use a plain-text configuration file instead, specify
    the flag --skip-config-decryption/-s.
\b
        cse ui-plugin register './container-ui-plugin.zip`
            --config my_config.yaml -s
\b
        cse ui-plugin list --config my_config.yaml -s
\b
        cse ui-plugin deregister
            'urn:vcloud:uiPlugin:6cae8802-35fb-4cc7-b143-9898b65c3adb'
            --config my_config.yaml -s
    """
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
    console_message_printer = ConsoleMessagePrinter()
    requests.packages.urllib3.disable_warnings()

    # The console_message_printer is not being passed to the python version
    # check, because we want to suppress the version check messages from being
    # printed onto console.
    check_python_version()

    # Prompt user for administrator username/password
    admin_username = prompt_text(USERNAME_FOR_SYSTEM_ADMINISTRATOR,
                                 color='green', hide_input=False)
    admin_password = prompt_text(PASSWORD_FOR_SYSTEM_ADMINISTRATOR + str(admin_username),  # noqa: E501
                                 color='green', hide_input=True)

    msg = f"Connecting to vCD: {vcd_host}"
    console_message_printer.general_no_color(msg)
    SERVER_CLI_LOGGER.info(msg)

    client = None
    try:
        client = vcd_client.Client(vcd_host, verify_ssl_certs=not skip_verify_ssl_certs)  # noqa: E501
        credentials = vcd_client.BasicLoginCredentials(
            admin_username,
            SYSTEM_ORG_NAME,
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
            SERVER_CLI_LOGGER.error(str(err))
        except BadRequestException as err:
            msg = "CSE Service Role already Exists"
            console_message_printer.error(msg)
            console_message_printer.error(str(err))
            SERVER_CLI_LOGGER.error(msg)
            SERVER_CLI_LOGGER.error(str(err))
    except requests.exceptions.ConnectionError as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err))
    except VcdException as err:
        msg = f"Incorrect SystemOrg Username: {admin_username} and/or Password"
        console_message_printer.error(msg)
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(msg)
        SERVER_CLI_LOGGER.error(str(err))
    except Exception as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err))
    finally:
        if client is not None:
            client.logout()


@cli.command(short_help='Generate sample CSE/PKS configuration')
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
@click.option(
    '-v',
    '--api-version',
    'api_version',
    required=False,
    default=vcd_client.ApiVersion.VERSION_35.value,
    show_default=True,
    metavar='API_VERSION',
    help=f'vCD API version: {SUPPORTED_VCD_API_VERSIONS}. '
         f'Not needed if only generating PKS config.')
def sample(ctx, output, pks_config, api_version):
    """Display sample CSE config file contents."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    # The console_message_printer is not being passed to the python version
    # check, because we want to suppress the version check messages from being
    # printed onto console, and pollute the sample config.
    check_python_version()

    try:
        api_version = float(api_version)
        sample_config = generate_sample_config(output=output,
                                               generate_pks_config=pks_config,
                                               api_version=api_version)
    except Exception as err:
        console_message_printer.error(str(err))
        SERVER_CLI_LOGGER.error(str(err))
        sys.exit(1)

    console_message_printer.general_no_color(sample_config)
    SERVER_CLI_LOGGER.debug(sample_config)


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
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    config_dict = None
    try:
        config_dict = get_validated_config(
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
        SERVER_CLI_LOGGER.error(str(err))
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
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    try:
        try:
            password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
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
        SERVER_CLI_LOGGER.error(str(err))
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
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    try:
        try:
            password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
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
        SERVER_CLI_LOGGER.error(str(err))
        sys.exit(1)


@cli.command(short_help='Install CSE extension 3.0.0 on vCD')
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
@click.option(
    '-t',
    '--skip-template-creation',
    'skip_template_creation',
    is_flag=True,
    help='Skips creating CSE k8s template during installation')
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
def install(ctx, config_file_path, pks_config_file_path,
            skip_config_decryption, skip_template_creation,
            retain_temp_vapp, ssh_key_file):
    """Install CSE on vCloud Director."""
    # NOTE: For CSE 3.0, if `enable_tkg_plus` in config file is set to false
    # and if `cse install` is invoked without skipping template creation,
    # an Exception will be thrown if TKG+ template is present in the
    # remote_template_cookbook.
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    if retain_temp_vapp and not ssh_key_file:
        msg = "Must provide ssh-key file (using --ssh-key OR -k) if " \
              "--retain-temp-vapp is provided, or else temporary vm will be " \
              "inaccessible"
        console_message_printer.error(msg)
        SERVER_CLI_LOGGER.error(msg)
        sys.exit(1)

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    try:
        config = get_validated_config(
            config_file_name=config_file_path,
            pks_config_file_name=pks_config_file_path,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=INSTALL_WIRELOG_FILEPATH,
            logger_debug=INSTALL_LOGGER,
            msg_update_callback=console_message_printer)

        configure_cse.install_cse(
            config_file_name=config_file_path,
            config=config,
            pks_config_file_name=pks_config_file_path,
            skip_template_creation=skip_template_creation,
            ssh_key=ssh_key,
            retain_temp_vapp=retain_temp_vapp,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer)
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
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
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)
    requests.packages.urllib3.disable_warnings()

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
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
            raise Exception(CONFIG_DECRYPTION_ERROR_MSG)
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
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
    """Run CSE service."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    config = None
    cse_run_complete = False
    try:
        config = get_validated_config(
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
        SERVER_CLI_LOGGER.error(str(err))
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
             short_help="Upgrade CSE extension to version 3.0.0 on vCD")
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
@click.option(
    '-t',
    '--skip-template-creation',
    'skip_template_creation',
    is_flag=True,
    help='Skip creating CSE k8s templates during upgrade')
@click.option(
    '-d',
    '--retain-temp-vapp',
    'retain_temp_vapp',
    is_flag=True,
    help='Retain the temporary vApp after the CSE k8s template has been captured'  # noqa: E501
         ' --ssh-key option is required if this flag is used')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='Filepath of SSH public key to add to CSE k8s template vms')
@click.option(
    '-p',
    '--admin-password',
    'admin_password',
    default=None,
    metavar='ADMIN_PASSWORD',
    help="New root password to set on existing CSE k8s cluster vms. If left "
         "empty, old passwords,if present, will be retained else it will be "
         "auto-generated")
def upgrade(ctx, config_file_path, skip_config_decryption,
            skip_template_creation, retain_temp_vapp,
            ssh_key_file, admin_password):
    """Upgrade existing CSE installation/entities to match CSE 3.0.

\b
    - Add CSE / VCD API version info to VCD's extension data for CSE
    - Register defined entities schema of CSE k8s clusters with VCD
    - Create placement compute policies used by CSE
    - Remove old sizing compute policies created by CSE 2.6 and below
    - Install all templates from template repository linked in config file
    - Update currently installed templates that are no longer defined in
      CSE template repository to adhere to CSE 3.0 template requirements.
    - Update existing CSE k8s cluster's to match CSE 3.0 k8s clusters.
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` in the config is set to false,
    # an exception is thrown if
    # 1. If there is an existing TKG+ template
    # 2. If remote template cookbook contains a TKG+ template.
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    if retain_temp_vapp and not ssh_key_file:
        msg = "Must provide ssh-key file (using --ssh-key OR -k) if " \
              "--retain-temp-vapp is provided, or else temporary vm will be " \
              "inaccessible"
        console_message_printer.error(msg)
        INSTALL_LOGGER.error(msg)
        sys.exit(1)

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    try:
        config = get_validated_config(
            config_file_name=config_file_path,
            pks_config_file_name=None,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=INSTALL_WIRELOG_FILEPATH,
            logger_debug=INSTALL_LOGGER,
            msg_update_callback=console_message_printer)

        configure_cse.upgrade_cse(
            config_file_name=config_file_path,
            config=config,
            skip_template_creation=skip_template_creation,
            ssh_key=ssh_key,
            retain_temp_vapp=retain_temp_vapp,
            admin_password=admin_password,
            msg_update_callback=console_message_printer)

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
        [DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_LOCAL, DISPLAY_REMOTE]),
    default=DISPLAY_ALL,
    help='Choose templates to display.')
def list_template(ctx, config_file_path, skip_config_decryption,
                  display_option):
    """List CSE k8s templates."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    # Not passing the console_message_printer, because we want to suppress
    # the python version check messages from being printed onto console.
    check_python_version()

    config_dict = None
    try:
        # We don't want to validate config file, because server startup or
        # installation is not being performed. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        config_dict = _get_unvalidated_config(
            config_file_path=config_file_path,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer)

        # Record telemetry details
        cse_params = {
            PayloadKey.DISPLAY_OPTION: display_option,
            PayloadKey.WAS_DECRYPTION_SKIPPED: bool(skip_config_decryption)
        }
        record_user_action_details(cse_operation=CseOperation.TEMPLATE_LIST,
                                   cse_params=cse_params,
                                   telemetry_settings=config_dict['service']['telemetry'])  # noqa: E501

        local_templates = []
        if display_option in (DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_LOCAL):
            client = None
            try:
                log_wire_file = None
                log_wire = str_to_bool(config_dict['service'].get('log_wire'))
                if log_wire:
                    log_wire_file = SERVER_DEBUG_WIRELOG_FILEPATH

                client, _ = _get_clients_from_config(
                    config_dict,
                    log_wire_file=log_wire_file,
                    log_wire=log_wire)

                org_name = config_dict['broker']['org']
                catalog_name = config_dict['broker']['catalog']
                is_tkg_plus_enabled = utils.is_tkg_plus_enabled(config_dict)
                is_tkgm_enabled = utils.is_tkgm_enabled(config_dict)

                local_template_definitions = \
                    ltm.get_all_k8s_local_template_definition(
                        client=client,
                        catalog_name=catalog_name,
                        org_name=org_name,
                        logger_debug=SERVER_CLI_LOGGER)

                default_template_name = \
                    config_dict['broker']['default_template_name']
                default_template_revision = \
                    str(config_dict['broker']['default_template_revision'])
                api_version = float(client.get_api_version())
                for definition in local_template_definitions:
                    if api_version >= float(vcd_client.ApiVersion.VERSION_35.value):
                        if definition[LocalTemplateKey.KIND] == ClusterEntityKind.TKG_PLUS.value and \
                                not is_tkg_plus_enabled:  # noqa: E501
                            # TKG+ is not enabled on CSE config. Skip the template
                            # and log the relevant information.
                            msg = "Skipping loading template data for " \
                                  f"'{definition[LocalTemplateKey.NAME]}' as " \
                                  "TKG+ is not enabled"
                            SERVER_CLI_LOGGER.debug(msg)
                            continue
                        if definition[LocalTemplateKey.KIND] == ClusterEntityKind.TKG_M.value and \
                                not is_tkgm_enabled:  # noqa: E501
                            # TKGm is not enabled on CSE config. Skip the template
                            # and log the relevant information.
                            msg = "Skipping loading template data for " \
                                  f"'{definition[LocalTemplateKey.NAME]}' as " \
                                  "TKGm is not enabled"
                            SERVER_CLI_LOGGER.debug(msg)
                            continue
                    local_template = {
                        'name': definition[LocalTemplateKey.NAME],
                        # Any metadata read from vCD is string due to how
                        # pyvcloud is coded, so we need to cast it back to int.
                        'revision': int(definition[LocalTemplateKey.REVISION]),
                        'compute_policy': definition[LocalTemplateKey.COMPUTE_POLICY],  # noqa: E501
                        'local': 'Yes',
                        'remote': 'No',
                        'cpu': definition[LocalTemplateKey.CPU],
                        'memory': definition[LocalTemplateKey.MEMORY],
                        'description': definition[LocalTemplateKey.DESCRIPTION]
                    }
                    if (definition[LocalTemplateKey.NAME], str(definition[LocalTemplateKey.REVISION])) == (default_template_name, default_template_revision):  # noqa: E501
                        local_template['default'] = 'Yes'
                    else:
                        local_template['default'] = 'No'
                    local_template['deprecated'] = 'Yes' if str_to_bool(definition[LocalTemplateKey.DEPRECATED]) else 'No'  # noqa: E501

                    local_templates.append(local_template)
            finally:
                if client:
                    client.logout()

        remote_templates = []
        if display_option in (DISPLAY_ALL, DISPLAY_DIFF, DISPLAY_REMOTE):
            rtm = RemoteTemplateManager(
                remote_template_cookbook_url=config_dict['broker']['remote_template_cookbook_url'],  # noqa: E501
                logger=SERVER_CLI_LOGGER,
                msg_update_callback=console_message_printer)
            remote_template_cookbook = rtm.get_remote_template_cookbook()
            remote_template_definitions = remote_template_cookbook['templates']
            for definition in remote_template_definitions:
                remote_template = {
                    'name': definition[RemoteTemplateKey.NAME],
                    'revision': definition[RemoteTemplateKey.REVISION],
                    'compute_policy': definition[RemoteTemplateKey.COMPUTE_POLICY],  # noqa: E501
                    'local': 'No',
                    'remote': 'Yes',
                    'cpu': definition[RemoteTemplateKey.CPU],
                    'memory': definition[RemoteTemplateKey.MEMORY],
                    'description': definition[RemoteTemplateKey.DESCRIPTION]
                }
                if display_option is DISPLAY_ALL:
                    remote_template['default'] = 'No'
                remote_template['deprecated'] = 'Yes' if str_to_bool(definition[RemoteTemplateKey.DEPRECATED]) else 'No'  # noqa: E501

                remote_templates.append(remote_template)

        result = []
        if display_option is DISPLAY_ALL:
            result = remote_templates
            # If local copy of template exists, update the remote definition
            # with relevant values, else add the local definition to the result
            # list.
            for local_template in local_templates:
                found = False
                for remote_template in remote_templates:
                    if (local_template[LocalTemplateKey.NAME], local_template[LocalTemplateKey.REVISION]) == (remote_template[RemoteTemplateKey.NAME], remote_template[RemoteTemplateKey.REVISION]):  # noqa: E501
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
                    if (local_template[LocalTemplateKey.NAME], local_template[LocalTemplateKey.REVISION]) == (remote_template[RemoteTemplateKey.NAME], remote_template[RemoteTemplateKey.REVISION]):  # noqa: E501
                        found = True
                        break
                if not found:
                    result.append(remote_template)
        elif display_option in DISPLAY_LOCAL:
            result = local_templates
        elif display_option in DISPLAY_REMOTE:
            result = remote_templates

        result = sorted(result, key=lambda t: (t['name'], t['revision']), reverse=True)  # noqa: E501
        stdout(result, ctx, sort_headers=False)
        SERVER_CLI_LOGGER.debug(result)
        record_user_action(cse_operation=CseOperation.TEMPLATE_LIST,
                           telemetry_settings=config_dict['service']['telemetry'])  # noqa: E501
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
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` flag in config is set to false,
    # Throw an error if TKG+ template creation is issued.
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    if retain_temp_vapp and not ssh_key_file:
        msg = "Must provide ssh-key file (using --ssh-key OR -k) if " \
              "--retain-temp-vapp is provided, or else temporary vm will be " \
              "inaccessible"
        SERVER_CLI_LOGGER.error(msg)
        console_message_printer.error(msg)
        sys.exit(1)

    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    ssh_key = None
    if ssh_key_file is not None:
        ssh_key = ssh_key_file.read()

    try:
        config = get_validated_config(
            config_file_name=config_file_path,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            log_wire_file=INSTALL_WIRELOG_FILEPATH,
            logger_debug=INSTALL_LOGGER,
            msg_update_callback=console_message_printer)

        configure_cse.install_template(
            template_name=template_name,
            template_revision=template_revision,
            config_file_name=config_file_path,
            config=config,
            force_create=force_create,
            retain_temp_vapp=retain_temp_vapp,
            ssh_key=ssh_key,
            skip_config_decryption=skip_config_decryption,
            decryption_password=password,
            msg_update_callback=console_message_printer)
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        # block the process to let telemetry handler to finish posting data to
        # VAC. HACK!!!
        time.sleep(3)


@uiplugin.command('register', short_help="Register UI plugin with vCD.")
@click.pass_context
@click.argument('plugin_file_path',
                metavar='PLUGIN_FILE_PATH',
                type=click.Path(exists=True))
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
def register_ui_plugin(ctx, plugin_file_path, config_file_path,
                       skip_config_decryption):
    """."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    client = None
    tempdir = None
    try:
        # We don't want to validate config file, because server startup or
        # installation is not being performed. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        config_dict = _get_unvalidated_config(
            config_file_path=config_file_path,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer)

        tempdir = tempfile.mkdtemp(dir='.')
        plugin_zip = ZipFile(plugin_file_path, 'r')
        plugin_zip.extractall(path=tempdir)
        plugin_zip.close()
        manifest_file = None
        extracted_files = os.listdir(tempdir)
        for filename in extracted_files:
            if filename == 'manifest.json':
                manifest_file = os.path.join(tempdir, filename)
                break
        if manifest_file is None:
            raise Exception('Invalid plugin zip. Manifest file not found.')

        manifest = json.load(open(manifest_file, 'r'))
        register_request_payload = {
            'pluginName': manifest['name'],
            'vendor': manifest['vendor'],
            'description': manifest['description'],
            'version': manifest['version'],
            'license': manifest['license'],
            'link': manifest['link'],
            'tenant_scoped': "tenant" in manifest['scope'],
            'provider_scoped': "service-provider" in manifest['scope'],
            'enabled': True
        }

        log_wire_file = None
        log_wire = str_to_bool(config_dict['service'].get('log_wire'))
        if log_wire:
            log_wire_file = SERVER_DEBUG_WIRELOG_FILEPATH

        client, cloudapi_client = _get_clients_from_config(
            config_dict, log_wire_file=log_wire_file, log_wire=log_wire)

        msg = "Registering plugin with vCD."
        SERVER_CLI_LOGGER.debug(msg)
        console_message_printer.info(msg)
        try:
            response_body = cloudapi_client.do_request(
                method=RequestMethod.POST,
                resource_url_relative_path=f"{CloudApiResource.EXTENSION_UI}",
                payload=register_request_payload)
            plugin_id = response_body.get('id')
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == requests.codes.bad_request and \
                    'VCD_50012' in err.response.text:
                raise Exception("Plugin is already registered. Please "
                                "de-register it first if you wish to register "
                                "it again.")
            raise

        msg = "Preparing to upload plugin to vCD."
        SERVER_CLI_LOGGER.debug(msg)
        console_message_printer.info(msg)
        transfer_request_payload = {
            "fileName": os.path.split(plugin_file_path)[1],
            "size": os.stat(plugin_file_path).st_size
        }
        cloudapi_client.do_request(
            method=RequestMethod.POST,
            resource_url_relative_path=f"{CloudApiResource.EXTENSION_UI}/{plugin_id}/plugin",  # noqa: E501
            payload=transfer_request_payload)

        msg = "Uploading plugin to vCD."
        SERVER_CLI_LOGGER.debug(msg)
        console_message_printer.info(msg)
        transfer_url = None
        content_type = None
        response_headers = cloudapi_client.get_last_response_headers()
        # E.g. Link Header - <https://bos1-vcd-sp-static-199-101.eng.vmware.com/transfer/f7fd8885-1fdb-4e3c-90cc-9411363abdcb/container-ui-plugin.zip>;rel="upload:default";type="application/octet-stream"  # noqa: E501
        tokens = response_headers.get("Link").split(";")
        for token in tokens:
            if token.startswith("<"):
                transfer_url = token[1:-1]  # get rid of the < and >
            if token.startswith("type"):
                fragments = token.split("\"")
                content_type = fragments[1]
        file_content = open(plugin_file_path, 'rb')
        cloudapi_client.do_request(
            method=RequestMethod.PUT,
            resource_url_absolute_path=transfer_url,
            payload=file_content,
            content_type=content_type)
        msg = "Plugin upload complete."
        SERVER_CLI_LOGGER.debug(msg)
        console_message_printer.general(msg)

        msg = "Waiting for plugin to be ready."
        console_message_printer.info(msg)
        SERVER_CLI_LOGGER.debug(msg)
        while True:
            response_body = cloudapi_client.do_request(
                method=RequestMethod.GET,
                resource_url_relative_path=f"{CloudApiResource.EXTENSION_UI}/{plugin_id}")  # noqa: E501
            plugin_status = response_body.get('plugin_status')
            msg = f"Plugin status : {plugin_status}"
            console_message_printer.info(msg)
            SERVER_CLI_LOGGER.debug(msg)
            if plugin_status == 'ready':
                break
        msg = "Plugin registration complete."
        SERVER_CLI_LOGGER.debug(msg)
        console_message_printer.general(msg)
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        if client:
            client.logout()
        if tempdir:
            shutil.rmtree(tempdir)


@uiplugin.command('deregister', short_help="De-register UI plugin from vCD.")
@click.pass_context
@click.argument('plugin_id', metavar='PLUGIN_ID')
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
def deregister_ui_plugin(ctx, plugin_id, config_file_path,
                         skip_config_decryption):
    """."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    check_python_version(console_message_printer)

    client = None
    try:
        # We don't want to validate config file, because server startup or
        # installation is not being performed. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        config_dict = _get_unvalidated_config(
            config_file_path=config_file_path,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer)

        log_filename = None
        log_wire = str_to_bool(config_dict['service'].get('log_wire'))
        if log_wire:
            log_filename = SERVER_CLI_WIRELOG_FILEPATH

        client, cloudapi_client = _get_clients_from_config(
            config_dict, log_wire_file=log_filename, log_wire=log_wire)

        cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            resource_url_relative_path=f"{CloudApiResource.EXTENSION_UI}/{plugin_id}")  # noqa: E501

        msg = f"Removed plugin with id : {plugin_id}."
        SERVER_CLI_LOGGER.debug(msg)
        console_message_printer.general(msg)
    except Exception as err:
        SERVER_CLI_LOGGER.debug(str(err))
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        if client:
            client.logout()


@uiplugin.command('list',
                  short_help="List all UI plugins registered with vCD.")
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
def list_ui_plugin(ctx, config_file_path, skip_config_decryption):
    """."""
    SERVER_CLI_LOGGER.debug(f"Executing command: {ctx.command_path}")
    console_message_printer = ConsoleMessagePrinter()
    # Suppress the python version check message from being printed on
    # console
    check_python_version()

    client = None
    try:
        # We don't want to validate config file, because server startup or
        # installation is not being performed. If values in config file are
        # missing or bad, appropriate exception will be raised while accessing
        # or using them.
        config_dict = _get_unvalidated_config(
            config_file_path=config_file_path,
            skip_config_decryption=skip_config_decryption,
            msg_update_callback=console_message_printer)

        log_filename = None
        log_wire = str_to_bool(config_dict['service'].get('log_wire'))
        if log_wire:
            log_filename = SERVER_DEBUG_WIRELOG_FILEPATH

        client, cloudapi_client = _get_clients_from_config(
            config_dict, log_wire_file=log_filename, log_wire=log_wire)

        result = []
        response_body = cloudapi_client.do_request(
            method=RequestMethod.GET,
            resource_url_relative_path=f"{CloudApiResource.EXTENSION_UI}")  # noqa: E501
        if len(response_body) > 0:
            for plugin in response_body:
                ui_plugin = {
                    'name': plugin['pluginName'],
                    'vendor': plugin['vendor'],
                    'version': plugin['version'],
                    'id': plugin['id']
                }
                result.append(ui_plugin)

        stdout(result, ctx, sort_headers=False, show_id=True)
        SERVER_CLI_LOGGER.debug(result)
    except Exception as err:
        SERVER_CLI_LOGGER.error(str(err))
        console_message_printer.error(str(err))
        sys.exit(1)
    finally:
        if client:
            client.logout()


def _get_unvalidated_config(config_file_path,
                            skip_config_decryption,
                            msg_update_callback=NullPrinter()):
    password = None
    if not skip_config_decryption:
        password = os.getenv('CSE_CONFIG_PASSWORD') or prompt_text(
            PASSWORD_FOR_CONFIG_DECRYPTION_MSG,
            color='green', hide_input=True)

    try:
        if skip_config_decryption:
            with open(config_file_path) as config_file:
                config_dict = yaml.safe_load(config_file) or {}
        else:
            msg_update_callback.info(
                f"Decrypting '{config_file_path}'")
            config_dict = yaml.safe_load(
                get_decrypted_file_contents(
                    config_file_path, password)) or {}
        msg_update_callback.general(f"Retrieved config from "
                                    f"'{config_file_path}'")

        # To suppress the warning message that pyvcloud prints if
        # ssl_cert verification is skipped.
        if config_dict and config_dict.get('vcd') and \
                not config_dict['vcd'].get('verify'):
            requests.packages.urllib3.disable_warnings()

        # Store telemetry instance id, url and collector id in config
        # This step should be done after suppressing the cert validation
        # warnings
        store_telemetry_settings(config_dict)

        return config_dict
    except cryptography.fernet.InvalidToken:
        raise Exception(CONFIG_DECRYPTION_ERROR_MSG)


def _get_clients_from_config(config, log_wire_file, log_wire):
    client = vcd_client.Client(
        config['vcd']['host'],
        api_version=config['vcd']['api_version'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file=log_wire_file,
        log_requests=log_wire,
        log_headers=log_wire,
        log_bodies=log_wire)
    credentials = vcd_client.BasicLoginCredentials(
        config['vcd']['username'],
        SYSTEM_ORG_NAME,
        config['vcd']['password'])
    client.set_credentials(credentials)

    logger_wire = NULL_LOGGER
    if log_wire:
        logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER

    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client,
        SERVER_CLI_LOGGER,
        logger_wire)

    return client, cloudapi_client


if __name__ == '__main__':
    cli()
