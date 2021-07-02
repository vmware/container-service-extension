# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import click
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout
import yaml

import container_service_extension.client.command_filter as cmd_filter
import container_service_extension.client.constants as cli_constants
from container_service_extension.client.ovdc import Ovdc
import container_service_extension.client.utils as client_utils
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
from container_service_extension.logging.logger import CLIENT_LOGGER


@click.group(name='ovdc', cls=cmd_filter.GroupCommandFilter,
             short_help='Manage ovdc enablement for native clusters')
@click.pass_context
def ovdc_group(ctx):
    """Manage ovdc enablement for native clusters.

All commands execute in the context of user's currently logged-in
organization. Use a different organization by using the '--org' option.
    """
    pass


@ovdc_group.command('list',
                    short_help='Display org VDCs in vCD that are visible '
                               'to the logged in user')
@click.pass_context
@click.option(
    '-A',
    '--all',
    'should_print_all',
    is_flag=True,
    default=False,
    required=False,
    metavar='DISPLAY_ALL',
    help='Display all the OVDCs non-interactively')
def list_ovdcs(ctx, should_print_all=False):
    """Display org VDCs in vCD that are visible to the logged in user.

\b
Example
    vcd cse ovdc list
        Display ovdcs in vCD that are visible to the logged in user.
        The user might be prompted if more results needs to be displayed
\b
    vcd cse ovdc list -A
        Display ovdcs in vCD that are visible to the logged in user without
        prompting the user.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        ovdc = Ovdc(client)
        client_utils.print_paginated_result(ovdc.list_ovdc(),
                                            should_print_all=should_print_all,
                                            logger=CLIENT_LOGGER)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@ovdc_group.command('enable',
                    short_help='Enable ovdc for native cluster deployments')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='VDC_NAME')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Org to use. Defaults to currently logged-in org")
@click.option(
    '-n',
    '--native',
    'enable_native',
    is_flag=True,
    help="Enable OVDC for k8 runtime native"
)
@click.option(
    '-p',
    '--tkg-plus',
    'enable_tkg_plus',
    is_flag=True,
    hidden=not utils.is_environment_variable_enabled(cli_constants.ENV_CSE_TKG_PLUS_ENABLED),  # noqa: E501
    help="Enable OVDC for k8 runtime TKG plus"
)
def ovdc_enable(ctx, ovdc_name, org_name, enable_native, enable_tkg_plus=None):
    """Set Kubernetes provider for an org VDC.

\b
Example
    vcd cse ovdc enable --native --org org1 ovdc1
        Enable native cluster deployment in ovdc1 of org1.
        Supported only for vcd api version >= 35.
\b
    vcd cse ovdc enable ovdc1
        Enable ovdc1 for native cluster deployment.
        Supported only for vcd api version < 35.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    if not (enable_native or enable_tkg_plus):
        msg = "Please specify at least one k8 runtime to enable"
        stderr(msg, ctx)
        CLIENT_LOGGER.error(msg)
    k8_runtime = []
    if enable_native:
        k8_runtime.append(shared_constants.ClusterEntityKind.NATIVE.value)
    if enable_tkg_plus:
        k8_runtime.append(shared_constants.ClusterEntityKind.TKG_PLUS.value)
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            ovdc = Ovdc(client)
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.update_ovdc(
                enable=True,
                ovdc_name=ovdc_name,
                org_name=org_name,
                k8s_runtime=k8_runtime)
            stdout(result, ctx)
            CLIENT_LOGGER.debug(result)
        else:
            msg = "Insufficient permission to perform operation."
            stderr(msg, ctx)
            CLIENT_LOGGER.error(msg)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@ovdc_group.command('disable',
                    short_help='Disable further native cluster deployments on '
                               'the ovdc')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='VDC_NAME')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Org to use. Defaults to currently logged-in org")
@click.option(
    '-n',
    '--native',
    'disable_native',
    is_flag=True,
    help="Disable OVDC for k8 runtime native cluster"
)
@click.option(
    '-p',
    '--tkg-plus',
    'disable_tkg_plus',
    is_flag=True,
    hidden=not utils.is_environment_variable_enabled(cli_constants.ENV_CSE_TKG_PLUS_ENABLED),  # noqa: E501
    help="Disable OVDC for k8 runtime TKG plus"
)
@click.option(
    '-f',
    '--force',
    'remove_cp_from_vms_on_disable',
    is_flag=True,
    help="Remove the compute policies from deployed VMs as well. "
         "Does not remove the compute policy from vApp templates in catalog. ")
def ovdc_disable(ctx, ovdc_name, org_name,
                 disable_native, disable_tkg_plus=None,
                 remove_cp_from_vms_on_disable=False):
    """Disable Kubernetes cluster deployment for an org VDC.

\b
Examples
    vcd cse ovdc disable --native --org org1 ovdc1
        Disable native cluster deployment in ovdc1 of org1.
        Supported only for vcd api version >= 35.
\b
    vcd cse ovdc disable --native --org org1 --force ovdc1
        Force disable native cluster deployment in ovdc1 of org1.
        Replaces CSE policies with VCD default policies.
        Supported only for vcd api version >= 35.
\b
    vcd cse ovdc disable ovdc3
        Disable ovdc3 for any further native cluster deployments.
        Supported only for vcd api version < 35.

    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    if not (disable_native or disable_tkg_plus):
        msg = "Please specify at least one k8 runtime to disable"
        stderr(msg, ctx)
        CLIENT_LOGGER.error(msg)
    k8_runtime = []
    if disable_native:
        k8_runtime.append(shared_constants.ClusterEntityKind.NATIVE.value)
    if disable_tkg_plus:
        k8_runtime.append(shared_constants.ClusterEntityKind.TKG_PLUS.value)
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            ovdc = Ovdc(client)
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.update_ovdc(enable=False,
                                      ovdc_name=ovdc_name,
                                      org_name=org_name,
                                      k8s_runtime=k8_runtime,
                                      remove_cp_from_vms_on_disable=remove_cp_from_vms_on_disable)  # noqa: E501
            stdout(result, ctx)
            CLIENT_LOGGER.debug(result)
        else:
            msg = "Insufficient permission to perform operation."
            stderr(msg, ctx)
            CLIENT_LOGGER.error(msg)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@ovdc_group.command('info',
                    short_help='Display information about Kubernetes provider '
                               'for an org VDC')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='VDC_NAME')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Org to use. Defaults to currently logged-in org")
def ovdc_info(ctx, ovdc_name, org_name):
    """Display information about Kubernetes provider for an org VDC.

\b
Example
    vcd cse ovdc info ovdc1
        Display detailed information about ovdc 'ovdc1'.

    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            ovdc = Ovdc(client)
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.info_ovdc(ovdc_name, org_name)
            stdout(yaml.dump(result), ctx)
            CLIENT_LOGGER.debug(result)
        else:
            msg = "Insufficient permission to perform operation"
            stderr(msg, ctx)
            CLIENT_LOGGER.error(msg)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@ovdc_group.group('compute-policy',
                  short_help='Manage compute policies for an org VDC')
@click.pass_context
def compute_policy_group(ctx):
    """Manage compute policies for org VDCs.

System administrator operations.

\b
Examples
    vcd cse ovdc compute-policy list --org ORG_NAME --vdc VDC_NAME
        List all compute policies for a specific ovdc in a specific org.
\b
    vcd cse ovdc compute-policy add POLICY_NAME --org ORG_NAME --vdc VDC_NAME
        Add a compute policy to a specific ovdc in a specific org.
\b
    vcd cse ovdc compute-policy remove POLICY_NAME --org ORG_NAME --vdc VDC_NAME
        Remove a compute policy from a specific ovdc in a specific org.
    """  # noqa: E501
    pass


@compute_policy_group.command('list', short_help='')
@click.pass_context
@click.option(
    '-o',
    '--org',
    'org_name',
    metavar='ORG_NAME',
    required=True,
    help="(Required) Org to use")
@click.option(
    '-v',
    '--vdc',
    'ovdc_name',
    metavar='VDC_NAME',
    required=True,
    help="(Required) Org VDC to use")
def compute_policy_list(ctx, org_name, ovdc_name):
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin():
            raise Exception("Insufficient permission to perform operation.")

        ovdc = Ovdc(client)
        result = ovdc.list_ovdc_compute_policies(ovdc_name, org_name)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@compute_policy_group.command('add', short_help='')
@click.pass_context
@click.argument('compute_policy_name', metavar='COMPUTE_POLICY_NAME')
@click.option(
    '-o',
    '--org',
    'org_name',
    metavar='ORG_NAME',
    required=True,
    help="(Required) Org to use")
@click.option(
    '-v',
    '--vdc',
    'ovdc_name',
    metavar='VDC_NAME',
    required=True,
    help="(Required) Org VDC to use")
def compute_policy_add(ctx, org_name, ovdc_name, compute_policy_name):
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin():
            raise Exception("Insufficient permission to perform operation.")

        ovdc = Ovdc(client)
        result = ovdc.update_ovdc_compute_policies(ovdc_name,
                                                   org_name,
                                                   compute_policy_name,
                                                   shared_constants.ComputePolicyAction.ADD,  # noqa: E501
                                                   False)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@compute_policy_group.command('remove', short_help='')
@click.pass_context
@click.argument('compute_policy_name', metavar='COMPUTE_POLICY_NAME')
@click.option(
    '-o',
    '--org',
    'org_name',
    metavar='ORG_NAME',
    required=True,
    help="(Required) Org to use")
@click.option(
    '-v',
    '--vdc',
    'ovdc_name',
    metavar='VDC_NAME',
    required=True,
    help="(Required) Org VDC to use")
@click.option(
    '-f',
    '--force',
    'remove_compute_policy_from_vms',
    is_flag=True,
    help="Remove the specified compute policy from deployed VMs as well. "
         "Affected VMs will have 'System Default' compute policy. "
         "Does not remove the compute policy from vApp templates in catalog. "
         "This VM compute policy update is irreversible.")
def compute_policy_remove(ctx, org_name, ovdc_name, compute_policy_name,
                          remove_compute_policy_from_vms):
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin():
            raise Exception("Insufficient permission to perform operation.")

        ovdc = Ovdc(client)
        result = ovdc.update_ovdc_compute_policies(
            ovdc_name,
            org_name,
            compute_policy_name,
            shared_constants.ComputePolicyAction.REMOVE,
            remove_compute_policy_from_vms)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
