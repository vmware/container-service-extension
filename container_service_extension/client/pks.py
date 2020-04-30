# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os

import click
from vcd_cli.utils import restore_session
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout

from container_service_extension.client.ovdc import Ovdc
from container_service_extension.client.pks_cluster import PksCluster
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY


@click.group(name='pks', short_help='Manage Ent-PKS clusters')
@click.pass_context
def pks_group(ctx):
    """Manage Enterprise PKS Kubernetes clusters."""


@pks_group.group('cluster', short_help='Manage Ent-PKS Kubernetes clusters')
@click.pass_context
def cluster_group(ctx):
    """Manage Kubernetes clusters.

\b
Cluster names should follow the syntax for valid names and can have
up to 25 characters .
\b
Examples
    vcd cse pks cluster list
        Display clusters in Ent-PKS that are visible to the logged in user.
\b
    vcd cse pks cluster list --vdc ovdc1
        Display clusters in Ent-PKS backed by 'ovdc1'.
\b
    vcd cse pks cluster create mycluster
        Create an Ent-PKS cluster named 'mycluster'.
        The cluster will have number of worker nodes defined by the plan.
\b
    vcd cse pks cluster create mycluster --nodes 1 --vdc othervdc
        Create an Ent-PKS cluster named 'mycluster' on org VDC 'othervdc'.
        The cluster will have 1 worker node.
        On create failure, cluster will be left cluster in error state for
        troubleshooting.
\b
    vcd cse pks cluster resize mycluster --nodes 5
        Resize the cluster to have 5 worker nodes. On resize failure,
        cluster will be left in error state for troubleshooting.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse pks cluster resize mycluster -N 10
        Resize the cluster size to 10 worker nodes. On resize failure,
        cluster will be left in error state for troubleshooting.
\b
    vcd cse pks cluster config mycluster > ~/.kube/config
        Write cluster config details into '~/.kube/config' to manage cluster
        using kubectl.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse pks cluster info mycluster
        Display detailed information about cluster 'mycluster'.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse pks cluster delete mycluster --yes
        Delete cluster 'mycluster' without prompting.
        '--vdc' option can be used for faster command execution.
    """
    pass


@cluster_group.command('list',
                       short_help='Display clusters in Ent-PKS '
                                  'that are visible to the logged in user')
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
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Filter list to show clusters from a specific org")
def list_clusters(ctx, vdc, org_name):
    """Display clusters in Ent-PKS that are visible to the logged in user."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = PksCluster(client)
        if not client.is_sysadmin() and org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        result = cluster.get_clusters(vdc=vdc, org=org_name)
        stdout(result, ctx, show_id=True, sort_headers=False)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('delete', short_help='Delete an Ent-PKS cluster')
@click.pass_context
@click.argument('cluster_name', required=True)
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
def cluster_delete(ctx, cluster_name, vdc, org):
    """Delete an Ent-PKS cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = PksCluster(client)
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        result = cluster.delete_cluster(cluster_name, org, vdc)
        # result is empty for delete cluster operation on Ent-PKS clusters.
        # In that specific case, below check helps to print out a meaningful
        # message to users.
        if len(result) == 0:
            click.secho(f"Delete cluster operation has been initiated on "
                        f"{cluster_name}, please check the status using"
                        f" 'vcd cse pks-cluster info {cluster_name}'.", fg='yellow')  # noqa: E501
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('create', short_help='Create an Ent-PKS cluster')
@click.pass_context
@click.argument('cluster_name', required=True)
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
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Org to use. Defaults to currently logged-in org')
def cluster_create(ctx, cluster_name, vdc, node_count, org_name):
    """Create an Ent-PKS Kubernetes cluster (max name length is 25 characters)."""  # noqa: E501
    try:

        restore_session(ctx)
        if vdc is None:
            vdc = ctx.obj['profiles'].get('vdc_in_use')
            if not vdc:
                raise Exception("Virtual datacenter context is not set. "
                                "Use either command 'vcd vdc use' or option "
                                "'--vdc' to set the vdc context.")
        if org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        client = ctx.obj['client']
        cluster = PksCluster(client)
        result = cluster.create_cluster(
            vdc,
            cluster_name,
            node_count=node_count,
            org=org_name)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('resize',
                       short_help='Resize the Ent-PKS cluster to contain the '
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
def cluster_resize(ctx, cluster_name, node_count, org_name, vdc_name):
    """Resize the Ent-PKS to contain the specified number of worker nodes.

    Clusters that use native Kubernetes provider can not be sized down
    (use 'vcd cse node delete' command to do so).
    """
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        if not client.is_sysadmin() and org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        cluster = PksCluster(client)
        result = cluster.resize_cluster(
            cluster_name,
            node_count=node_count,
            org=org_name,
            vdc=vdc_name)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('config', short_help='Display Ent-PKS cluster configuration')  # noqa: E501
@click.pass_context
@click.argument('cluster_name', required=True)
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
def cluster_config(ctx, cluster_name, vdc, org):
    """Display Ent-PKS cluster configuration.

    To write to a file: `vcd cse pks-cluster config mycluster > ~/.kube/my_config`  # noqa: E501
    """
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = PksCluster(client)
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        cluster_config = cluster.get_cluster_config(cluster_name, vdc=vdc, org=org).get(RESPONSE_MESSAGE_KEY) # noqa: E501
        # Config information with linux new-line should be converted to
        # carriage-return to output in windows console.
        if os.name == 'nt':
            cluster_config = str.replace(cluster_config, '\n', '\r\n')

        click.secho(cluster_config)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('info',
                       short_help='Display info about an Ent-PKS K8 cluster')
@click.pass_context
@click.argument('cluster_name', required=True)
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
def cluster_info(ctx, cluster_name, org, vdc):
    """Display info about an Ent-PKS K8 cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = PksCluster(client)
        if not client.is_sysadmin() and org is None:
            org = ctx.obj['profiles'].get('org_in_use')
        cluster_info = cluster.get_cluster_info(cluster_name, org=org, vdc=vdc)
        stdout(cluster_info, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@pks_group.group('ovdc',
                 short_help='Manage Kubernetes provider '
                            'to be Ent-PKS for org VDCs')
@click.pass_context
def ovdc_group(ctx):
    """Manage Kubernetes provider to be Ent-PKS for org VDCs.

All commands execute in the context of user's currently logged-in
organization. Use a different organization by using the '--org' option.

\b
Examples
    vcd cse ovdc enable ovdc2 --pks-plan 'plan1' \\
     --pks-cluster-domain 'myorg.com'
        Set 'ovdc2' Kubernetes provider to be ent-pks.
        Use pks plan 'plan1' for 'ovdc2'.
        Set cluster domain to be 'myorg.com'.
    """
    pass


@ovdc_group.command('enable',
                    short_help='Set Kubernetes provider to be Ent-PKS for an org VDC')  # noqa: E501
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='VDC_NAME')
@click.option(
    '-p',
    '--pks-plan',
    'pks_plan',
    required=True,
    metavar='PLAN_NAME',
    help="PKS plan to use for all cluster deployments in this org VDC ")
@click.option(
    '-d',
    '--pks-cluster-domain',
    'pks_cluster_domain',
    required=True,
    help=f"Domain name suffix used to construct FQDN of deployed clusters "
    f"in this org VDC ")
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Org to use. Defaults to currently logged-in org")
def ovdc_enable(ctx, ovdc_name, pks_plan,
                pks_cluster_domain, org_name):
    """Set Kubernetes provider to be Ent-PKS for an org VDC."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            ovdc = Ovdc(client)
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.update_ovdc_for_k8s(
                enable=True,
                ovdc_name=ovdc_name,
                org_name=org_name,
                k8s_provider=K8sProvider.PKS,
                pks_plan=pks_plan,
                pks_cluster_domain=pks_cluster_domain)
            stdout(result, ctx)
        else:
            stderr("Insufficient permission to perform operation.", ctx)
    except Exception as e:
        stderr(e, ctx)
