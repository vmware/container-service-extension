# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import os

import click
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout
import yaml

from container_service_extension.client.cluster import Cluster
import container_service_extension.client.command_filter as cmd_filter
import container_service_extension.client.constants as cli_constants
from container_service_extension.client.de_cluster_native import DEClusterNative  # noqa: E501
import container_service_extension.client.sample_generator as client_sample_generator  # noqa: E501
import container_service_extension.client.utils as client_utils
from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
from container_service_extension.exception.exceptions import CseResponseError
from container_service_extension.exception.exceptions import CseServerNotRunningError  # noqa: E501
from container_service_extension.exception.minor_error_codes import MinorErrorCode  # noqa: E501
from container_service_extension.logging.logger import CLIENT_LOGGER
import container_service_extension.rde.utils as def_utils


@click.group(name='cluster', cls=cmd_filter.GroupCommandFilter,
             short_help='Manage Kubernetes clusters (native and vSphere with '
                        'Tanzu)')
@click.pass_context
def cluster_group(ctx):
    """Manage Kubernetes clusters (Native, vSphere with Tanzu and Ent-PKS).

\b
Cluster names should follow the syntax for valid hostnames and can have
up to 25 characters .`system`, `template` and `swagger*` are reserved
words and cannot be used to name a cluster.
    """
    pass


@cluster_group.command('list',
                       short_help='Display clusters in vCD that are visible '
                                  'to the logged in user')
@click.pass_context
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Filter list to show clusters from a specific org VDC')
@click.option(
    '-A',
    '--all',
    'should_print_all',
    is_flag=True,
    default=False,
    required=False,
    metavar='DISPLAY_ALL',
    help='Display all the clusters non-interactively')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Filter list to show clusters from a specific org")
def list_clusters(ctx, vdc, org_name, should_print_all):
    """Display clusters in vCD that are visible to the logged in user.

\b
Examples
    vcd cse cluster list
        Display clusters in vCD that are visible to the logged in user.
\b
    vcd cse cluster list -vdc ovdc1
        Display clusters in vdc 'ovdc1'.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        if not client.is_sysadmin() and org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        client_utils.print_paginated_result(cluster.list_clusters(vdc=vdc, org=org_name),  # noqa: E501
                                            should_print_all=should_print_all,
                                            logger=CLIENT_LOGGER)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('delete',
                       short_help='Delete a cluster')
@click.pass_context
@click.argument('name', required=False, default=None)
@click.confirmation_option(prompt='Are you sure you want to delete the '
                                  'cluster?')
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind; Supported only for'
         ' vcd api version >= 35')
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster which needs to be deleted;"
         "Supported only for CSE api version >= 35."
         "ID gets precedence over cluster name.")
def cluster_delete(ctx, name, vdc, org, k8_runtime=None, cluster_id=None):
    """Delete a Kubernetes cluster.

\b
Example
    vcd cse cluster delete mycluster --yes
        Delete cluster 'mycluster' without prompting.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse cluster delete --id urn:vcloud:entity:cse:nativeCluster:1.0.0:0632c7c7-a613-427c-b4fc-9f1247da5561
        Delete cluster with cluster ID 'urn:vcloud:entity:cse:nativeCluster:1.0.0:0632c7c7-a613-427c-b4fc-9f1247da5561'.
        (--id option is supported only applicable for api version >= 35)
    """  # noqa: E501
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        if not (cluster_id or name):
            # --id is not required when working with api version 33 and 34
            raise Exception("Please specify cluster name (or) cluster Id. "
                            "Note that '--id' flag is applicable for API versions >= 35 only.")  # noqa: E501

        client = ctx.obj['client']
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for native
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value
        cluster = Cluster(client, k8_runtime=k8_runtime)
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        result = cluster.delete_cluster(name, cluster_id=cluster_id,
                                        org=org, vdc=vdc)
        if len(result) == 0:
            # TODO(CLI): Update message to use vcd task wait instead
            click.secho(f"Delete cluster operation has been initiated on "
                        f"{name}, please check the status using"
                        f" 'vcd cse cluster info {name}'.", fg='yellow')
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('create', short_help='Create a Kubernetes cluster')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Org VDC to use. Defaults to currently logged-in org VDC')
@click.option(
    '-N',
    '--nodes',
    'node_count',
    required=False,
    default=None,
    type=click.INT,
    help='Number of worker nodes to create')
@click.option(
    '-c',
    '--cpu',
    'cpu',
    required=False,
    default=None,
    type=click.INT,
    help='Number of virtual CPUs on each node')
@click.option(
    '-m',
    '--memory',
    'memory',
    required=False,
    default=None,
    type=click.INT,
    help='Megabytes of memory on each node')
@click.option(
    '-n',
    '--network',
    'network_name',
    default=None,
    required=False,
    help='Org vDC network name (Required)')
@click.option(
    '-s',
    '--storage-profile',
    'storage_profile',
    required=False,
    default=None,
    help='Name of the storage profile for the nodes')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='SSH public key filepath')
@click.option(
    '-t',
    '--template-name',
    'template_name',
    required=False,
    default=None,
    help='Name of the template to create new nodes from. '
         'If not specified, server default will be used '
         '(Must be used with --template-revision).')
@click.option(
    '-r',
    '--template-revision',
    'template_revision',
    required=False,
    default=None,
    help='Revision number of the template to create new nodes from. '
         'If not specified, server default will be used '
         '(Must be used with --template-revision).')
@click.option(
    '--enable-nfs',
    'enable_nfs',
    is_flag=True,
    help='Create 1 additional NFS node (if --nodes=2, then CSE will create '
         '2 worker nodes and 1 NFS node)')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    help='Disable rollback on cluster creation failure')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Org to use. Defaults to currently logged-in org')
def cluster_create(ctx, name, vdc, node_count, network_name,
                   storage_profile, ssh_key_file, template_name,
                   template_revision, enable_nfs, disable_rollback, org_name,
                   cpu=None, memory=None):
    """Create a Kubernetes cluster (max name length is 25 characters).

\b
Examples
    vcd cse cluster create mycluster --network mynetwork
        Create a Kubernetes cluster named 'mycluster'.
        The cluster will have 2 worker nodes.
        The cluster will be connected to org VDC network 'mynetwork'.
        All VMs will use the default template.
        On create failure, the invalid cluster is deleted.
\b
    vcd cse cluster create mycluster --nodes 1 --enable-nfs \\
    --network mynetwork --template-name photon-v2 --template-revision 1 \\
    --cpu 3 --memory 1024 --storage-profile mystorageprofile \\
    --ssh-key ~/.ssh/id_rsa.pub --disable-rollback --vdc othervdc
        Create a Kubernetes cluster named 'mycluster' on org VDC 'othervdc'.
        The cluster will have 1 worker node and 1 NFS node.
        The cluster will be connected to org VDC network 'mynetwork'.
        All VMs will use the template 'photon-v2'.
        Each VM in the cluster will have 3 vCPUs and 1024mb of memory.
        All VMs will use the storage profile 'mystorageprofile'.
        The public ssh key at '~/.ssh/id_rsa.pub' will be placed into all
        VMs for user accessibility.
        On create failure, cluster will be left cluster in error state for
        troubleshooting.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        if (template_name and not template_revision) or \
                (not template_name and template_revision):
            raise Exception("Both flags --template-name(-t) and "
                            "--template-revision (-r) must be specified.")

        client_utils.cse_restore_session(ctx)
        if vdc is None:
            vdc = ctx.obj['profiles'].get('vdc_in_use')
            if not vdc:
                raise Exception("Virtual datacenter context is not set. "
                                "Use either command 'vcd vdc use' or option "
                                "'--vdc' to set the vdc context.")
        if org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        ssh_key = None
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()

        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.create_cluster(
            vdc,
            network_name,
            name,
            node_count=node_count,
            cpu=cpu,
            memory=memory,
            storage_profile=storage_profile,
            ssh_key=ssh_key,
            template_name=template_name,
            template_revision=template_revision,
            enable_nfs=enable_nfs,
            rollback=not disable_rollback,
            org=org_name)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except CseResponseError as e:
        minor_error_code_to_error_message = {
            MinorErrorCode.REQUEST_KEY_NETWORK_NAME_MISSING: 'Missing option "-n" / "--network".',  # noqa: E501
            MinorErrorCode.REQUEST_KEY_NETWORK_NAME_INVALID: 'Invalid or missing value for option "-n" / "--network".'  # noqa: E501
        }
        e.error_message = \
            minor_error_code_to_error_message.get(
                e.minor_error_code, e.error_message)
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('resize',
                       short_help='Resize the cluster to contain the '
                                  'specified number of worker nodes')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.option(
    '-N',
    '--nodes',
    'node_count',
    required=True,
    default=None,
    type=click.INT,
    help='Desired number of worker nodes for the cluster')
@click.option(
    '-n',
    '--network',
    'network_name',
    default=None,
    required=False,
    help='Network name (Exclusive to native Kubernetes provider) (Required)')
@click.option(
    '-v',
    '--vdc',
    'vdc_name',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    help='Disable rollback on node creation failure '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '-t',
    '--template-name',
    'template_name',
    required=False,
    default=None,
    help='Name of the template to create new nodes from. '
         'If not specified, server default will be used '
         '(Exclusive to native Kubernetes provider) '
         '(Must be used with --template-revision).')
@click.option(
    '-r',
    '--template-revision',
    'template_revision',
    required=False,
    default=None,
    help='Revision number of the template to create new nodes from. '
         'If not specified, server default will be used '
         '(Exclusive to native Kubernetes provider) '
         '(Must be used with --template-revision).')
@click.option(
    '-c',
    '--cpu',
    'cpu',
    required=False,
    default=None,
    type=click.INT,
    help='Number of virtual CPUs on each node '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '-m',
    '--memory',
    'memory',
    required=False,
    default=None,
    type=click.INT,
    help='Megabytes of memory on each node '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='SSH public key filepath (Exclusive to native Kubernetes provider)')
def cluster_resize(ctx, cluster_name, node_count, network_name, org_name,
                   vdc_name, disable_rollback, template_name,
                   template_revision, cpu, memory, ssh_key_file):
    """Resize the cluster to contain the specified number of worker nodes.

    Clusters that use native Kubernetes provider can not be sized down
    (use 'vcd cse node delete' command to do so).
\b
Examples
    vcd cse cluster resize mycluster --nodes 5 --network mynetwork
        Resize the cluster to have 5 worker nodes. On resize failure,
        returns cluster to original size.
        Nodes will be created from server default template at default revision.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse cluster resize mycluster -N 10 --template-name my_template \\
    --template-revision 2 --disable-rollback
        Resize the cluster size to 10 worker nodes. On resize failure,
        cluster will be left cluster in error state for troubleshooting.
        Nodes will be created from template 'my_template' revision 2.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        if (template_name and not template_revision) or \
                (not template_name and template_revision):
            raise Exception("Both --template-name (-t) and "
                            "--template-revision (-r) must be specified.")

        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin() and org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')

        ssh_key = None
        if ssh_key_file:
            ssh_key = ssh_key_file.read()
        cluster = Cluster(client)
        result = cluster.resize_cluster(
            network_name,
            cluster_name,
            node_count=node_count,
            org=org_name,
            vdc=vdc_name,
            rollback=not disable_rollback,
            template_name=template_name,
            template_revision=template_revision,
            cpu=cpu,
            memory=memory,
            ssh_key=ssh_key)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except CseResponseError as e:
        minor_error_code_to_error_message = {
            MinorErrorCode.REQUEST_KEY_NETWORK_NAME_MISSING: 'Missing option "-n" / "--network".',  # noqa: E501
            MinorErrorCode.REQUEST_KEY_NETWORK_NAME_INVALID: 'Invalid or missing value for option "-n" / "--network".'  # noqa: E501
        }
        e.error_message = \
            minor_error_code_to_error_message.get(
                e.minor_error_code, e.error_message)
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('apply',
                       short_help='apply a configuration to a cluster resource'
                                  ' by filename. The resource will be created '
                                  'if it does not exist. (The command can be '
                                  'used to create the cluster, scale-up/down '
                                  'worker count, scale-up NFS nodes, upgrade '
                                  'the cluster to a new K8s version. Note '
                                  'that for api_version <36.0, upgrades are '
                                  'not supported with this command.)')
@click.pass_context
@click.argument(
    'cluster_config_file_path',
    required=False,
    metavar='CLUSTER_CONFIG_FILE_PATH',
    type=click.Path(exists=True))
@click.option(
    '-s',
    '--sample',
    'generate_sample_config',
    is_flag=True,
    required=False,
    default=False,
    help="generate sample cluster configuration file; This flag can't be used together with CLUSTER_CONFIG_FILE_PATH")  # noqa: E501
@click.option(
    '-n',
    '--native',
    'k8_runtime',
    is_flag=True,
    flag_value=shared_constants.ClusterEntityKind.NATIVE.value,
    help="should be used with --sample, this flag generates sample yaml for k8 runtime: native"  # noqa: E501
)
@click.option(
    '-k',
    '--tkg-s',
    'k8_runtime',
    is_flag=True,
    flag_value=shared_constants.ClusterEntityKind.TKG_S.value,
    help="should be used with --sample, this flag generates sample yaml for k8 runtime: TKG"  # noqa: E501
)
@click.option(
    '-p',
    '--tkg-plus',
    'k8_runtime',
    is_flag=True,
    hidden=not utils.is_environment_variable_enabled(cli_constants.ENV_CSE_TKG_PLUS_ENABLED),  # noqa: E501
    flag_value=shared_constants.ClusterEntityKind.TKG_PLUS.value,
    help="should be used with --sample, this flag generates sample yaml for k8 runtime: TKG+"  # noqa: E501
)
@click.option(
    '-o',
    '--output',
    'output',
    required=False,
    default=None,
    metavar='OUTPUT_FILE_NAME',
    help="Filepath to write sample configuration file to; This flag should be used with -s")  # noqa: E501
@click.option(
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORGANIZATION',
    help="Organization on which the cluster configuration needs to be applied")
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster to which the configuration should be applied;"
         "Supported only for CSE api version >=35."
         "ID gets precedence over cluster name.")
def apply(ctx, cluster_config_file_path, generate_sample_config, k8_runtime, output, org, cluster_id):  # noqa: E501
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        console_message_printer = utils.ConsoleMessagePrinter()
        if cluster_config_file_path and (generate_sample_config or output or k8_runtime):  # noqa: E501
            console_message_printer.general_no_color(ctx.get_help())
            msg = "-s/-o/-n/-t/-k flag can't be used together with CLUSTER_CONFIG_FILE_PATH"  # noqa: E501
            CLIENT_LOGGER.error(msg)
            raise Exception(msg)

        if not cluster_config_file_path and not generate_sample_config:
            console_message_printer.general_no_color(ctx.get_help())
            msg = "No option chosen/invalid option"
            CLIENT_LOGGER.error(msg)
            raise Exception(msg)

        client = ctx.obj['client']
        if generate_sample_config:
            if not k8_runtime:
                console_message_printer.general_no_color(ctx.get_help())
                msg = "with option --sample you must specify either of options: --native or --tkg-s"  # noqa: E501
                if utils.is_environment_variable_enabled(cli_constants.ENV_CSE_TKG_PLUS_ENABLED):  # noqa: E501
                    msg += " or --tkg-plus"
                CLIENT_LOGGER.error(msg)
                raise Exception(msg)
            elif k8_runtime == shared_constants.ClusterEntityKind.TKG_PLUS.value \
                    and not utils.is_environment_variable_enabled(cli_constants.ENV_CSE_TKG_PLUS_ENABLED):  # noqa: E501
                raise Exception(f"{shared_constants.ClusterEntityKind.TKG_PLUS.value} not enabled")  # noqa: E501
            else:
                # since apply command is not exposed when CSE server is not
                # running, it is safe to get the server_rde_version from
                # VCD API version as VCD API version will be the supported by
                # CSE server.
                server_rde_version = \
                    def_utils.get_runtime_rde_version_by_vcd_api_version(
                        client.get_api_version())
                sample_cluster_config = \
                    client_sample_generator.get_sample_cluster_configuration(
                        output=output,
                        k8_runtime=k8_runtime,
                        server_rde_in_use=server_rde_version)
                console_message_printer.general_no_color(sample_cluster_config)
                return

        with open(cluster_config_file_path) as f:
            cluster_config_map = yaml.safe_load(f) or {}

        k8_runtime = cluster_config_map.get('kind')
        if not k8_runtime:
            raise Exception("Cluster kind missing from the spec.")
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for native
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value
        org_name = None
        if k8_runtime == shared_constants.ClusterEntityKind.TKG_S.value:
            org_name = org
            if not org:
                org_name = ctx.obj['profiles'].get('org_in_use')

        cluster = Cluster(client, k8_runtime=cluster_config_map.get('kind'))
        result = cluster.apply(cluster_config_map, cluster_id=cluster_id,
                               org=org_name)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e), exc_info=True)


@cluster_group.command('delete-nfs',
                       help="Examples:\n\nvcd cse cluster delete-nfs mycluster nfs-uitj",  # noqa: E501
                       short_help='Delete nfs node from Native Kubernetes cluster')  # noqa: E501
@click.pass_context
@click.argument('cluster_name', required=True)
@click.argument('node_name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
def delete_nfs(ctx, cluster_name, node_name, vdc, org):
    """Remove nfs node in a cluster that uses native Kubernetes provider."""
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    # NOTE: command is exposed only if cli is enabled for native clusters
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        cluster = DEClusterNative(client)
        result = cluster.delete_nfs_node(cluster_name, node_name, org=org, vdc=vdc)  # noqa: E501
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('upgrade-plan',
                       short_help='Display templates that the specified '
                                  'native cluster can be upgraded to')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specific org VDC')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Restrict cluster search to specific org")
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind; Supported only '
         'for vcd api version >= 35.')
def cluster_upgrade_plan(ctx, cluster_name, vdc, org_name, k8_runtime=None):
    """Display templates that the specified cluster can upgrade to.

\b
Examples
    vcd cse cluster upgrade-plan my-cluster
    (Supported only for vcd api version < 35)
\b
    vcd cse cluster upgrade-plan --k8-runtime native my-cluster
    (Supported only for vcd api version >= 35)
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    # NOTE: Command is exposed only if CLI is enabled for native clusters
    try:
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for native
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value
        client = ctx.obj['client']
        cluster = Cluster(client, k8_runtime=k8_runtime)
        if not client.is_sysadmin() and org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')

        templates = cluster.get_upgrade_plan(cluster_name, vdc=vdc,
                                             org=org_name)
        result = []
        for template in templates:
            result.append({
                'Template Name': template[LocalTemplateKey.NAME],
                'Template Revision': template[LocalTemplateKey.REVISION],
                'Kubernetes': template[LocalTemplateKey.KUBERNETES_VERSION],
                'Docker-CE': template[LocalTemplateKey.DOCKER_VERSION],
                'CNI': f"{template[LocalTemplateKey.CNI]} {template[LocalTemplateKey.CNI_VERSION]}"  # noqa: E501
            })

        if not templates:
            result = f"No valid upgrade targets for cluster '{cluster_name}'"
        stdout(result, ctx, sort_headers=False)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('upgrade',
                       help="Examples:\n\nvcd cse cluster upgrade my-cluster ubuntu-16.04_k8-1.18_weave-2.6.4 1"  # noqa: E501
                            "\n(Supported only for vcd api version < 35)"
                            "\n\nvcd cse cluster upgrade -k native mcluster photon-v2_k8-1.14_weave-2.5.2 2"  # noqa: E501
                            "\n(Supported only for vcd api version >= 35)",
                       short_help="Upgrade native cluster software to "
                                  "specified template's software versions")
@click.pass_context
@click.argument('cluster_name', required=True)
@click.argument('template_name', required=True)
@click.argument('template_revision', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specific org VDC')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Restrict cluster search to specific org")
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind; Supported '
         'only for vcd api version >= 35.')
def cluster_upgrade(ctx, cluster_name, template_name, template_revision,
                    vdc, org_name, k8_runtime=None):
    """Upgrade cluster software to specified template's software versions.

\b
Example
    vcd cse cluster upgrade my-cluster ubuntu-16.04_k8-1.18_weave-2.6.4 1
        Upgrade cluster 'mycluster' Docker-CE, Kubernetes, and CNI to match
        template 'ubuntu-16.04_k8-1.18_weave-2.6.4' at revision 1.
        Affected software: Docker-CE, Kubernetes, CNI
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    # NOTE: Command is exposed only if CLI is enabled for native
    try:
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for native
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value
        client = ctx.obj['client']
        cluster = Cluster(client, k8_runtime=k8_runtime)
        if not client.is_sysadmin() and org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')

        result = cluster.upgrade_cluster(cluster_name, template_name,
                                         template_revision, ovdc_name=vdc,
                                         org_name=org_name)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('config',
                       short_help='Retrieve cluster configuration details')
@click.pass_context
@click.argument('name', default=None, required=False)
@click.option(
    '-o',
    '--org',
    'org',
    required=False,
    default=None,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind;'
         'Supported only for vcd api version >= 35')
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster whose cluster config has to be obtained;"
         "supported only for CSE api version >= 35."
         "ID gets precedence over cluster name.")
def cluster_config(ctx, name, vdc, org, k8_runtime=None, cluster_id=None):
    """Display cluster configuration.

\b
Examples:
    vcd cse cluster config my-cluster
    (Supported only for vcd api version < 35)
\b
    vcd cse cluster config -k native my-cluster
    (Supported only for vcd api version >= 35)

    To write to a file: `vcd cse cluster config mycluster > ~/.kube/my_config`
\b
    vcd cse cluster config --id urn:vcloud:entity:cse:nativeCluster:1.0.0:0632c7c7-a613-427c-b4fc-9f1247da5561
    (--id option is supported only for vcd api version >= 35)
    """  # noqa: E501
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        if not (cluster_id or name):
            # --id is not required when working with api version 33 and 34
            raise Exception("Please specify cluster name (or) cluster Id. "
                            "Note that '--id' flag is applicable for API versions >= 35 only.")  # noqa: E501
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for native
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value
        client = ctx.obj['client']
        cluster = Cluster(client, k8_runtime=k8_runtime)
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        ret_val = cluster.get_cluster_config(
            name,
            cluster_id=cluster_id,
            vdc=vdc,
            org=org
        ).get(shared_constants.RESPONSE_MESSAGE_KEY)
        if os.name == 'nt':
            ret_val = str.replace(ret_val, '\n', '\r\n')

        click.secho(ret_val)
        CLIENT_LOGGER.debug(ret_val)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('info',
                       short_help='Display info about a cluster')
@click.pass_context
@click.argument('name', default=None, required=False)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind;'
         'Supported only for vcd api version >=35')
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster whose info has to be obtained;"
         "Supported only for CSE api version >=35. "
         "ID gets precedence over cluster name.")
def cluster_info(ctx, name, org, vdc, k8_runtime=None, cluster_id=None):
    """Display info about a Kubernetes cluster.

\b
Example
    vcd cse cluster info mycluster
        Display detailed information about cluster 'mycluster'.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse cluster info --id urn:vcloud:entity:cse:nativeCluster:1.0.0:0632c7c7-a613-427c-b4fc-9f1247da5561
        Display cluster information about cluster with
        ID 'urn:vcloud:entity:cse:nativeCluster:1.0.0:0632c7c7-a613-427c-b4fc-9f1247da5561'
        (--id option is supported only for api version >= 35)
    """  # noqa: E501
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        if not (cluster_id or name):
            # --id is not required when working with api version 33 and 34
            raise Exception("Please specify cluster name (or) cluster Id. "
                            "Note that '--id' flag is applicable for API versions >= 35 only.")  # noqa: E501
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for native
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value
        client = ctx.obj['client']
        cluster = Cluster(client, k8_runtime=k8_runtime)
        # Users should be explicit in their intent about the org on which the
        # command needs to be executed.
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        result = cluster.get_cluster_info(name, cluster_id=cluster_id,
                                          org=org, vdc=vdc)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('share',
                       short_help='Share a cluster with at least one user')
@click.pass_context
@click.argument('users', nargs=-1, required=True)
@click.option(
    '-n',
    '--name',
    'name',
    required=False,
    default=None,
    metavar='CLUSTER_NAME',
    help='Name of the cluster to share')
@click.option(
    '--acl',
    'acl',
    required=True,
    default=None,
    metavar='ACL',
    help=f'access control: {shared_constants.READ_ONLY}, '
         f'{shared_constants.READ_WRITE}, or {shared_constants.FULL_CONTROL}')
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind')
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster to share; "
         "ID gets precedence over cluster name.")
def cluster_share(ctx, name, acl, users, vdc, org, k8_runtime, cluster_id):
    """Share cluster with users.

Either the cluster name or cluster id is required.
By default, this command searches for the cluster in the currently logged in user's org.

Note: this command does not remove an ACL entry.

\b
Examples:
    vcd cse cluster share --name mycluster --acl FullControl user1 user2
        Share cluster 'mycluster' with FullControl access with 'user1' and 'user2'
\b
    vcd cse cluster share --id urn:vcloud:entity:vmware:tkgcluster:1.0.0:71fa7b01-84dc-4a58-ae54-a1098219b057 --acl ReadOnly user1
        Share TKG-S cluster with cluster ID 'urn:vcloud:entity:vmware:tkgcluster:1.0.0:71fa7b01-84dc-4a58-ae54-a1098219b057'
        with ReadOnly access with 'user1'
    """  # noqa: E501
    try:
        # Verify access level and cluster name/id arguments
        access_level_id = shared_constants.ACCESS_LEVEL_TYPE_TO_ID.get(acl.lower())  # noqa: E501
        if not access_level_id:
            raise Exception(f'Please enter a valid access control type: '
                            f'{shared_constants.READ_ONLY}, '
                            f'{shared_constants.READ_WRITE}, or '
                            f'{shared_constants.FULL_CONTROL}')
        if not (cluster_id or name):
            raise Exception("Please specify cluster name or cluster id.")
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for TKG-S
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value

        client = ctx.obj['client']
        # Users should be explicit in their intent about the org on which the
        # command needs to be executed.
        is_system_user = client.is_sysadmin()
        if not is_system_user and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        elif is_system_user and org is None:
            raise Exception("Need to specify cluster org since logged in user is in system org")  # noqa: E501

        users_list = list(users)
        cluster = Cluster(client, k8_runtime)
        cluster.share_cluster(cluster_id, name, users_list, access_level_id,
                              org, vdc)
        stdout(f'Cluster {cluster_id or name} successfully shared with: {users_list}')  # noqa: E501
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('share-list',
                       short_help='List access information of shared cluster '
                                  'users')
@click.pass_context
@click.option(
    '-A',
    '--all',
    'should_print_all',
    is_flag=True,
    default=False,
    required=False,
    metavar='DISPLAY_ALL',
    help="Display all cluster user access information non-interactively")
@click.option(
    '-n',
    '--name',
    'name',
    required=False,
    default=None,
    metavar='CLUSTER_NAME',
    help='Name of the cluster to list shared users')
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind')
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster whose share lists we want to retrieve; "
         "ID gets precedence over cluster name.")
def cluster_share_list(ctx, should_print_all, name, vdc, org, k8_runtime,
                       cluster_id):
    """List cluster shared user information.

    Either the cluster name or cluster id is required.
\b
Examples:
    vcd cse cluster share-list --name mycluster
        List shared user information for cluster 'mycluster'
\b
    vcd cse cluster share --id urn:vcloud:entity:vmware:tkgcluster:1.0.0:71fa7b01-84dc-4a58-ae54-a1098219b057
        List shared user information for cluster with cluster ID 'urn:vcloud:entity:vmware:tkgcluster:1.0.0:71fa7b01-84dc-4a58-ae54-a1098219b057'
    """  # noqa: E501
    try:
        if not (cluster_id or name):
            raise Exception("Please specify cluster name or cluster id.")
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for TKG-S
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value

        # Determine cluster type and retrieve cluster id if needed
        client = ctx.obj['client']
        # Users should be explicit in their intent about the org on which the
        # command needs to be executed.
        is_system_user = client.is_sysadmin()
        if not is_system_user and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        elif is_system_user and org is None:
            raise Exception("Need to specify cluster org since logged in user is in system org")  # noqa: E501

        cluster = Cluster(client, k8_runtime)
        share_entries = cluster.list_share_entries(cluster_id, name, org, vdc)
        client_utils.print_paginated_result(share_entries, should_print_all)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@cluster_group.command('unshare',
                       short_help='Unshare a cluster with specified user(s)')
@click.pass_context
@click.argument('users', nargs=-1, required=True)
@click.option(
    '-n',
    '--name',
    'name',
    required=False,
    default=None,
    metavar='CLUSTER_NAME',
    help='Name of the cluster to share')
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Restrict cluster search to specified org')
@click.option(
    '-k',
    '--k8-runtime',
    'k8_runtime',
    default=None,
    required=False,
    metavar='K8-RUNTIME',
    help='Restrict cluster search to cluster kind')
@click.option(
    '--id',
    'cluster_id',
    default=None,
    required=False,
    metavar='CLUSTER_ID',
    help="ID of the cluster to unshare; "
         "ID gets precedence over cluster name.")
def cluster_unshare(ctx, name, users, vdc, org, k8_runtime, cluster_id):
    """Remove access from current shared cluster users.

Either the cluster name or cluster id is required. By default, this command searches
for the cluster in the currently logged in user's org.

\b
Examples:
    vcd cse cluster unshare --name mycluster user1 user2
        Unshare cluster 'mycluster' with FullControl access with 'user1' and 'user2'
\b
    vcd cse cluster unshare --id urn:vcloud:entity:vmware:tkgcluster:1.0.0:71fa7b01-84dc-4a58-ae54-a1098219b057 user1
        Unshare TKG-S cluster with cluster ID 'urn:vcloud:entity:vmware:tkgcluster:1.0.0:71fa7b01-84dc-4a58-ae54-a1098219b057' with 'user1'
    """  # noqa: E501
    try:
        if not (cluster_id or name):
            raise Exception("Please specify cluster name or cluster id.")
        client_utils.cse_restore_session(ctx)
        if client_utils.is_cli_for_tkg_s_only():
            if k8_runtime in [shared_constants.ClusterEntityKind.NATIVE.value,
                              shared_constants.ClusterEntityKind.TKG_PLUS.value]:  # noqa: E501
                # Cannot run the command as cse cli is enabled only for tkg
                raise CseServerNotRunningError()
            k8_runtime = shared_constants.ClusterEntityKind.TKG_S.value

        client = ctx.obj['client']
        # Users should be explicit in their intent about the org on which the
        # command needs to be executed.
        is_system_user = client.is_sysadmin()
        if not is_system_user and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        elif is_system_user and org is None:
            raise Exception("Need to specify cluster org since logged in user is in system org")  # noqa: E501

        users_list = list(users)
        cluster = Cluster(client, k8_runtime)
        cluster.unshare_cluster(cluster_id, name, users_list, org, vdc)

        stdout(f'Cluster {cluster_id or name} successfully unshared with: {users_list}')  # noqa: E501
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
