# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout

from container_service_extension.client.cluster import Cluster
import container_service_extension.client.utils as client_utils
from container_service_extension.common.constants.server_constants import K8S_PROVIDER_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import K8sProvider  # noqa: E501
from container_service_extension.logging.logger import CLIENT_LOGGER


@click.group(name='node', short_help='Manage nodes of native clusters')
@click.pass_context
def node_group(ctx):
    """Manage nodes of native clusters.

These commands will only work with clusters created by native
Kubernetes runtime.
    """
    pass


@node_group.command('info',
                    short_help='Display info about a node in a cluster that '
                               'was created with native Kubernetes provider')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.argument('node_name', required=True)
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
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
def node_info(ctx, cluster_name, node_name, org_name, vdc):
    """Display info about a node in a native Kubernetes provider cluster.

\b
Example
    vcd cse node info mycluster node-xxxx
        Display detailed information about node 'node-xxxx' in cluster
        'mycluster'.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)

        if org_name is None and not client.is_sysadmin():
            org_name = ctx.obj['profiles'].get('org_in_use')
        node_info = cluster.get_node_info(cluster_name, node_name,
                                          org_name, vdc)
        value_field_to_display_field = {
            'name': 'Name',
            'node_type': 'Node Type',
            'ipAddress': 'IP Address',
            'numberOfCpus': 'Number of CPUs',
            'memoryMB': 'Memory MB',
            'status': 'Status'
        }
        filtered_node_info = client_utils.filter_columns(
            node_info, value_field_to_display_field)
        stdout(filtered_node_info, ctx, sort_headers=False)
        CLIENT_LOGGER.debug(filtered_node_info)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@node_group.command('create',
                    short_help='Add node(s) to a cluster that was created '
                               'with native Kubernetes provider')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.option(
    '-N',
    '--nodes',
    'node_count',
    required=False,
    default=1,
    type=click.INT,
    help='Number of nodes to create')
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
    required=True,
    help='Network name')
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
    help='SSH public key to connect to the guest OS on the VM')
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
    help='Enable NFS on all created nodes')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    help='Disable rollback on node deployment failure')
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
def create_node(ctx, cluster_name, node_count, org, vdc, cpu, memory,
                network_name, storage_profile, ssh_key_file, template_name,
                template_revision, enable_nfs, disable_rollback):
    """Add node(s) to a cluster that uses native Kubernetes provider.

\b
Example
    vcd cse node create mycluster --nodes 2 --enable-nfs --network mynetwork \\
    --template-name photon-v2 --template-revision 1 --cpu 3 --memory 1024 \\
    --storage-profile mystorageprofile --ssh-key ~/.ssh/id_rsa.pub \\
        Add 2 nfs nodes to vApp named 'mycluster' on vCD.
        The nodes will be connected to org VDC network 'mynetwork'.
        All VMs will use the template 'photon-v2'.
        Each VM will have 3 vCPUs and 1024mb of memory.
        All VMs will use the storage profile 'mystorageprofile'.
        The public ssh key at '~/.ssh/id_rsa.pub' will be placed into all
        VMs for user accessibility.

    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        if (template_name and not template_revision) or \
                (not template_name and template_revision):
            raise Exception("Both --template-name (-t) and "
                            "--template-revision (-r) must be specified.")

        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if org is None and not client.is_sysadmin():
            org = ctx.obj['profiles'].get('org_in_use')
        cluster = Cluster(client)
        ssh_key = None
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()
        result = cluster.add_node(
            network_name,
            cluster_name,
            node_count=node_count,
            org=org,
            vdc=vdc,
            cpu=cpu,
            memory=memory,
            storage_profile=storage_profile,
            ssh_key=ssh_key,
            template_name=template_name,
            template_revision=template_revision,
            enable_nfs=enable_nfs,
            rollback=not disable_rollback)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@node_group.command('list',
                    short_help='Display nodes of a cluster that was created '
                               'with native Kubernetes provider')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-o',
    '--org',
    'org',
    default=None,
    required=False,
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
def list_nodes(ctx, name, org, vdc):
    """Display nodes of a cluster that uses native Kubernetes provider.

\b
Example
    vcd cse node list mycluster
        Displays nodes in 'mycluster'.

    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if org is None and not client.is_sysadmin():
            org = ctx.obj['profiles'].get('org_in_use')
        cluster = Cluster(client)
        cluster_info = cluster.get_cluster_info(name, org=org, vdc=vdc)
        if cluster_info.get(K8S_PROVIDER_KEY) != K8sProvider.NATIVE:
            raise Exception("'node list' operation is not supported by non "
                            "native clusters.")
        all_nodes = cluster_info['master_nodes'] + cluster_info['nodes']
        value_field_to_display_field = {
            'name': 'Name',
            'ipAddress': 'IP Address',
            'numberOfCpus': 'Number of CPUs',
            'memoryMB': 'Memory MB'
        }
        filtered_nodes = client_utils.filter_columns(all_nodes, value_field_to_display_field)  # noqa: E501
        stdout(filtered_nodes, ctx, show_id=True, sort_headers=False)
        CLIENT_LOGGER.debug(all_nodes)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))


@node_group.command('delete',
                    short_help='Delete node(s) in a cluster that was created '
                               'with native Kubernetes provider')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.argument('node_names', nargs=-1, required=True)
@click.confirmation_option(prompt='Are you sure you want to delete '
                                  'the node(s)?')
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
def delete_nodes(ctx, cluster_name, node_names, org, vdc):
    """Delete node(s) in a cluster that uses native Kubernetes provider.

\b
Example
    vcd cse node delete mycluster node-xxxx --yes
        Delete node 'node-xxxx' in cluster 'mycluster' without prompting.
    """
    CLIENT_LOGGER.debug(f'Executing command: {ctx.command_path}')
    try:
        client_utils.cse_restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        cluster = Cluster(client)
        result = cluster.delete_nodes(cluster_name, list(node_names), org=org,
                                      vdc=vdc)
        stdout(result, ctx)
        CLIENT_LOGGER.debug(result)
    except Exception as e:
        stderr(e, ctx)
        CLIENT_LOGGER.error(str(e))
