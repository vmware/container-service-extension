# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import click
from pyvcloud.vcd.client import Client
import requests
from vcd_cli.profiles import Profiles

from container_service_extension.client import system as syst
from container_service_extension.client.constants import CSE_SERVER_RUNNING
import container_service_extension.def_.utils as def_utils
from container_service_extension.exceptions import CseResponseError
from container_service_extension.shared_constants import CSE_SERVER_API_VERSION

_RESTRICT_CLI_TO_TKG_OPERATIONS = False


def is_cli_for_tkg_only():
    global _RESTRICT_CLI_TO_TKG_OPERATIONS
    return _RESTRICT_CLI_TO_TKG_OPERATIONS


def restrict_cli_to_tkg_operations():
    global _RESTRICT_CLI_TO_TKG_OPERATIONS
    _RESTRICT_CLI_TO_TKG_OPERATIONS = True


def enable_cli_for_all_operations():
    global _RESTRICT_CLI_TO_TKG_OPERATIONS
    _RESTRICT_CLI_TO_TKG_OPERATIONS = False


def cse_restore_session(ctx, vdc_required=False) -> None:
    """Restores the session with vcd client with right server api version.

    Replace the vcd client in ctx.obj with new client created with server api
    version. Also saves the server api version in profiles.

    :param <click.core.Context> ctx: click context
    :param bool vdc_required: is vdc required or not
    :return:
    """
    # Always override the vcd_client by new client with CSE server api version.
    if type(ctx.obj) is not dict or not ctx.obj.get('client'):
        profiles = Profiles.load()
        token = profiles.get('token')
        if token is None or len(token) == 0:
            raise Exception('Can\'t restore session, please login again.')
        if not profiles.get('verify'):
            if not profiles.get('disable_warnings'):
                click.secho(
                    'InsecureRequestWarning: '
                    'Unverified HTTPS request is being made. '
                    'Adding certificate verification is strongly '
                    'advised.',
                    fg='yellow',
                    err=True)
            requests.packages.urllib3.disable_warnings()

        client = Client(
            profiles.get('host'),
            api_version=profiles.get('api_version'),
            verify_ssl_certs=profiles.get('verify'),
            log_file='vcd.log',
            log_requests=profiles.get('log_request'),
            log_headers=profiles.get('log_header'),
            log_bodies=profiles.get('log_body'))
        client.rehydrate_from_token(
            profiles.get('token'), profiles.get('is_jwt_token'))

        ctx.obj = {}
        ctx.obj['client'] = client

    _override_client(ctx)

    if vdc_required:
        if not ctx.obj['profiles'].get('vdc_in_use') or \
                not ctx.obj['profiles'].get('vdc_href'):
            raise Exception('select a virtual datacenter')


def _override_client(ctx) -> None:
    """Replace the vcd client in ctx.obj with new one.

    New vcd client takes the CSE server_api_version as api_version param.
    Save profile also with 'cse_server_api_version' for subsequent commands.

    :param <click.core.Context> ctx: click context
    """
    profiles = Profiles.load()
    # if the key CSE_SERVER_RUNNING is not present in the profiles.yaml,
    # we make an assumption that CSE server is running
    is_cse_server_running = profiles.get(CSE_SERVER_RUNNING, default=True)
    cse_server_api_version = profiles.get(CSE_SERVER_API_VERSION)
    if not is_cse_server_running:
        restrict_cli_to_tkg_operations()
        ctx.obj['profiles'] = profiles
        return

    # Get server_api_version; save it in profiles if doesn't exist
    if not cse_server_api_version:
        try:
            system = syst.System(ctx.obj['client'])
            sys_info = system.get_info()
            cse_server_api_version = sys_info.get(CSE_SERVER_API_VERSION)
            profiles.set(CSE_SERVER_API_VERSION, cse_server_api_version)
            profiles.set(CSE_SERVER_RUNNING, True)
            profiles.save()
        except CseResponseError:
            # If request to CSE server times out
            profiles.set(CSE_SERVER_RUNNING, False)
            # restrict CLI for only TKG operations
            restrict_cli_to_tkg_operations()
            ctx.obj['profiles'] = profiles
            profiles.save()
            return
    client = Client(
        profiles.get('host'),
        api_version=cse_server_api_version,
        verify_ssl_certs=profiles.get('verify'),
        log_file='vcd.log',
        log_requests=profiles.get('log_request'),
        log_headers=profiles.get('log_header'),
        log_bodies=profiles.get('log_body'))
    client.rehydrate_from_token(profiles.get('token'), profiles.get('is_jwt_token'))  # noqa: E501
    ctx.obj['client'] = client
    ctx.obj['profiles'] = profiles


def construct_filters(**kwargs):
    filters = {}
    if kwargs.get('org'):
        filters[def_utils.ClusterEntityFilterKey.ORG_NAME.value] = kwargs['org']  # noqa: E501
    if kwargs.get('vdc'):
        filters[def_utils.ClusterEntityFilterKey.OVDC_NAME.value] = kwargs['vdc']  # noqa: E501
    return filters
