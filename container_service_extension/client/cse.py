# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os

import click
from vcd_cli.utils import restore_session
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout
from vcd_cli.vcd import vcd

from container_service_extension.client.cluster import Cluster
from container_service_extension.client.ovdc import Ovdc
from container_service_extension.client.system import System
from container_service_extension.server_constants import K8sProviders
from container_service_extension.service import Service


@vcd.group(short_help='Manage Kubernetes clusters')
@click.pass_context
def cse(ctx):
    """Manage Kubernetes clusters.

\b
Examples
    vcd cse version
        Display CSE version. If CSE version is displayed, then vcd-cli has
        been properly configured to run CSE commands.
    """


@cse.command(short_help='Display CSE version')
@click.pass_context
def version(ctx):
    """Display CSE version."""
    ver_obj = Service.version()
    ver_str = '%s, %s, version %s' % (ver_obj['product'],
                                      ver_obj['description'],
                                      ver_obj['version'])
    stdout(ver_obj, ctx, ver_str)


@cse.group('cluster', short_help='Manage Kubernetes clusters')
@click.pass_context
def cluster_group(ctx):
    """Manage Kubernetes clusters.

\b
Cluster names should follow the syntax for valid hostnames and can have
up to 25 characters .`system`, `template` and `swagger*` are reserved
words and cannot be used to name a cluster.
\b
Examples
    vcd cse cluster list
        Display clusters in vCD that are visible to the logged in user.
\b
    vcd cse cluster list -vdc ovdc1
        Display clusters in vdc 'ovdc1'.
\b
    vcd cse cluster create mycluster --network mynetwork
        Create a Kubernetes cluster named 'mycluster'.
        The cluster will have 2 worker nodes.
        The cluster will be connected to org VDC network 'mynetwork'.
        All VMs will use the default template.
        On create failure, the invalid cluster is deleted.
        '--network' is only applicable for clusters using native (vCD)
        Kubernetes provider.
\b
    vcd cse cluster create mycluster --nodes 1 --enable-nfs \\
    --network mynetwork --template photon-v2 --cpu 3 --memory 1024 \\
    --storage-profile mystorageprofile --ssh-key ~/.ssh/id_rsa.pub \\
    --disable-rollback --vdc othervdc
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
        All of these options except for '--nodes' and '--vdc' are only
        applicable for clusters using native (vCD) Kubernetes provider.
\b
    vcd cse cluster resize mycluster --network mynetwork
        Resize the cluster to have 1 worker node. On resize failure,
        returns cluster to original size.
        '--network' is only applicable for clusters using
        native (vCD) Kubernetes provider.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse cluster resize mycluster -N 10 --disable-rollback
        Resize the cluster size to 10 worker nodes. On resize failure,
        cluster will be left cluster in error state for troubleshooting.
\b
    vcd cse cluster config mycluster > ~/.kube/config
        Write cluster config details into '~/.kube/config' to manage cluster
        using kubectl.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse cluster info mycluster
        Display detailed information about cluster 'mycluster'.
        '--vdc' option can be used for faster command execution.
\b
    vcd cse cluster delete mycluster --yes
        Delete cluster 'mycluster' without prompting.
        '--vdc' option can be used for faster command execution.
    """
    pass


@cse.group(short_help='Manage native Kubernetes provider templates')
@click.pass_context
def template(ctx):
    """Manage native Kubernetes provider templates.

\b
Examples
    vcd cse template list
        Display templates that can be used by native Kubernetes provider.
    """
    pass


@template.command('list',
                  short_help='List native Kubernetes provider templates')
@click.pass_context
def list_templates(ctx):
    """Display templates that can be used by native Kubernetes provider."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = []
        templates = cluster.get_templates()
        for t in templates:
            result.append({
                'name': t['name'],
                'description': t['description'],
                'catalog': t['catalog'],
                'catalog_item': t['catalog_item'],
                'is_default': t['is_default'],
            })
        stdout(result, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


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
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Filter list to show clusters from a specific org")
def list_clusters(ctx, vdc, org_name):
    """Display clusters in vCD that are visible to the logged in user."""
    try:
        restore_session(ctx)
        if org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.get_clusters(vdc=vdc, org=org_name)
        stdout(result, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('delete',
                       short_help='Delete a Kubernetes cluster')
@click.pass_context
@click.argument('name', required=True)
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
def delete(ctx, name, vdc):
    """Delete a Kubernetes cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.delete_cluster(name, vdc)
        # result is empty for delete cluster operation on PKS-managed clusters.
        # In that specific case, below check helps to print out a meaningful
        # message to users.
        if len(result) == 0:
            click.secho(f"Delete cluster operation has been initiated on "
                        f"{name}, please check the status using"
                        f" 'vcd cse cluster info {name}'.", fg='yellow')
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='Create a Kubernetes cluster')
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
    default=2,
    type=click.INT,
    help='Number of nodes to create')
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
    '-n',
    '--network',
    'network_name',
    default=None,
    required=False,
    help='Network name (Exclusive to native Kubernetes provider) (Required)')
@click.option(
    '-s',
    '--storage-profile',
    'storage_profile',
    required=False,
    default=None,
    help='Name of the storage profile for the nodes '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    help='SSH public key to connect to the guest OS on the VM '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '-t',
    '--template',
    'template',
    required=False,
    default=None,
    help='Name of the template to instantiate nodes from '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '--enable-nfs',
    'enable_nfs',
    is_flag=True,
    required=False,
    default=False,
    help='Create an additional NFS node '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    required=False,
    default=True,
    help='Disable rollback on failed cluster creation '
         '(Exclusive to native Kubernetes provider)')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help='Org to use. Defaults to currently logged-in org')
def create(ctx, name, vdc, node_count, cpu, memory, network_name,
           storage_profile, ssh_key_file, template, enable_nfs,
           disable_rollback, org_name):
    """Create a Kubernetes cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)

        if vdc is None:
            vdc = ctx.obj['profiles'].get('vdc_in_use')
            if not vdc:
                raise Exception(f"Virtual datacenter context is not set. "
                                "Use either command 'vcd vdc use' or option "
                                "'--vdc' to set the vdc context.")
        if org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        ssh_key = None
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()

        result = cluster.create_cluster(
            vdc,
            network_name,
            name,
            node_count=node_count,
            cpu=cpu,
            memory=memory,
            storage_profile=storage_profile,
            ssh_key=ssh_key,
            template=template,
            enable_nfs=enable_nfs,
            disable_rollback=disable_rollback,
            org=org_name)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('resize',
                       short_help='Resize the cluster to contain the '
                                  'specified number of worker nodes')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-N',
    '--nodes',
    'node_count',
    required=False,
    default=1,
    type=click.INT,
    help='New size of the cluster (or) new worker node count of the cluster')
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
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    required=False,
    default=True,
    help='Disable rollback on failed node creation '
         '(Exclusive to native Kubernetes provider)')
def resize(ctx, name, node_count, network_name, vdc, disable_rollback):
    """Resize the cluster to contain the specified number of worker nodes.

    Clusters that use native Kubernetes provider can not be sized down
    (use 'vcd cse node delete' command to do so).
    """
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.resize_cluster(
            network_name,
            name,
            node_count=node_count,
            vdc=vdc,
            disable_rollback=disable_rollback)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('config', short_help='Display cluster configuration')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
def config(ctx, name, vdc):
    """Display cluster configuration.

    To write to a file: `vcd cse cluster config mycluster > ~/.kube/my_config`
    """
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_config = cluster.get_config(name, vdc=vdc)
        if os.name == 'nt':
            cluster_config = str.replace(cluster_config, '\n', '\r\n')

        click.secho(cluster_config)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('info',
                       short_help='Display info about a Kubernetes cluster')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    metavar='VDC_NAME',
    help='Restrict cluster search to specified org VDC')
def cluster_info(ctx, name, vdc):
    """Display info about a Kubernetes cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_info = cluster.get_cluster_info(name, vdc=vdc)
        stdout(cluster_info, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cse.group('node',
           short_help='Manage nodes of clusters created by native '
                      'Kubernetes provider')
@click.pass_context
def node_group(ctx):
    """Manage nodes of clusters created by native Kubernetes provider.

These commands will only work with clusters created by native
Kubernetes provider.

\b
Examples
    vcd cse node create mycluster --network mynetwork
        Add 1 node to vApp named 'mycluster' on vCD.
        The node will be connected to org VDC network 'mynetwork'.
        The VM will use the default template.
\b
    vcd cse node create mycluster --nodes 2 --type nfsd --network mynetwork \\
    --template photon-v2 --cpu 3 --memory 1024 \\
    --storage-profile mystorageprofile --ssh-key ~/.ssh/id_rsa.pub \\
        Add 2 nfsd nodes to vApp named 'mycluster' on vCD.
        The nodes will be connected to org VDC network 'mynetwork'.
        All VMs will use the template 'photon-v2'.
        Each VM will have 3 vCPUs and 1024mb of memory.
        All VMs will use the storage profile 'mystorageprofile'.
        The public ssh key at '~/.ssh/id_rsa.pub' will be placed into all
        VMs for user accessibility.
\b
    vcd cse node list mycluster
        Displays nodes in 'mycluster'.
\b
    vcd cse node info mycluster node-xxxx
        Display detailed information about node 'node-xxxx' in cluster
        'mycluster'.
\b
    vcd cse node delete mycluster node-xxxx --yes
        Delete node 'node-xxxx' in cluster 'mycluster' without prompting.
    """
    pass


@node_group.command('info',
                    short_help='Display info about a node in a cluster that '
                               'was created with native Kubernetes provider')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.argument('node_name', required=True)
def node_info(ctx, cluster_name, node_name):
    """Display info about a node in a native Kubernetes provider cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        node_info = cluster.get_node_info(cluster_name, node_name)
        stdout(node_info, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@node_group.command('create',
                    short_help='Add node(s) to a cluster that was created '
                               'with native Kubernetes provider')
@click.pass_context
@click.argument('name', required=True)
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
    '--template',
    'template',
    required=False,
    default=None,
    help='Name of the template to instantiate nodes from')
@click.option(
    '--type',
    'node_type',
    required=False,
    default='node',
    type=click.Choice(['node', 'nfsd']),
    help='Type of node to add')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    required=False,
    default=True,
    help='Disable rollback for node')
def create_node(ctx, name, node_count, cpu, memory, network_name,
                storage_profile, ssh_key_file, template, node_type,
                disable_rollback):
    """Add node(s) to a cluster that uses native Kubernetes provider."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        ssh_key = None
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()
        result = cluster.add_node(
            ctx.obj['profiles'].get('vdc_in_use'),
            network_name,
            name,
            node_count=node_count,
            cpu=cpu,
            memory=memory,
            storage_profile=storage_profile,
            ssh_key=ssh_key,
            template=template,
            node_type=node_type,
            disable_rollback=disable_rollback)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@node_group.command('list',
                    short_help='Display nodes of a cluster that was created '
                               'with native Kubernetes provider')
@click.pass_context
@click.argument('name', required=True)
def list_nodes(ctx, name):
    """Display nodes of a cluster that uses native Kubernetes provider."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_info = cluster.get_cluster_info(name)
        all_nodes = cluster_info['master_nodes'] + cluster_info['nodes']
        stdout(all_nodes, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@node_group.command('delete',
                    short_help='Delete node(s) in a cluster that was created '
                               'with native Kubernetes provider')
@click.pass_context
@click.argument('name', required=True)
@click.argument('node-names', nargs=-1)
@click.confirmation_option(prompt='Are you sure you want to delete the '
                                  'node(s)?')
@click.option(
    '-f',
    '--force',
    is_flag=True,
    help='Force delete node VM(s)')
def delete_nodes(ctx, name, node_names, force):
    """Delete node(s) in a cluster that uses native Kubernetes provider."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.delete_nodes(ctx.obj['profiles'].get('vdc_in_use'),
                                      name, node_names, force)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cse.group('system', short_help='Manage CSE service (system daemon)')
@click.pass_context
def system_group(ctx):
    """Manage CSE service (system daemon).

\b
Examples
    vcd cse system info
        Display detailed information about CSE.
\b
    vcd cse system enable --yes
        Enable CSE system daemon without prompting.
\b
    vcd cse system stop --yes
        Stop CSE system daemon without prompting.
\b
    vcd cse system disable --yes
        Disable CSE system daemon without prompting.
    """
    pass


@system_group.command('info', short_help='Display info about CSE')
@click.pass_context
def info(ctx):
    """Display info about CSE."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.get_info()
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@system_group.command('stop', short_help='Gracefully stop CSE service')
@click.pass_context
@click.confirmation_option(prompt='Are you sure you want to stop the service?')
def stop_service(ctx):
    """Stop CSE system daemon."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.stop()
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@system_group.command('enable', short_help='Enable CSE service')
@click.pass_context
def enable_service(ctx):
    """Enable CSE system daemon."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.enable_service()
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@system_group.command('disable', short_help='Disable CSE service')
@click.pass_context
def disable_service(ctx):
    """Disable CSE system daemon."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        system = System(client)
        result = system.enable_service(False)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cse.group('ovdc', short_help='Manage Kubernetes provider for org VDCs')
@click.pass_context
def ovdc_group(ctx):
    """Manage Kubernetes provider for org VDCs.

All commands execute in the context of user's currently logged-in
organization. Use a different organization by using the '--org' option.

Currently supported Kubernetes-providers:

- native (vCD)

- ent-pks (Enterprise PKS)

\b
Examples
    vcd cse ovdc enable ovdc1 --k8s-provider native
        Set 'ovdc1' Kubernetes provider to be native (vCD).
\b
    vcd cse ovdc enable ovdc2 --k8s-provider ent-pks \\
    --pks-plan 'plan1' --pks-cluster-domain 'myorg.com'
        Set 'ovdc2' Kubernetes provider to be ent-pks.
        Use pks plan 'plan1' for 'ovdc2'.
        Set cluster domain to be 'myorg.com'.
\b
    vcd cse ovdc disable ovdc3
        Set 'ovdc3' Kubernetes provider to be none,
        which disables Kubernetes cluster deployment on 'ovdc3'.
\b
    vcd cse ovdc info ovdc1
        Display detailed information about ovdc 'ovdc1'.
\b
    vcd cse ovdc list
        Display ovdcs in vCD that are visible to the logged in user.
        vcd cse ovdc list
\b
        vcd cse ovdc list --pks-plans
            Displays list of ovdcs in a given org along with available PKS
            plans if any. If executed by System-administrator, it will
            display all ovdcs from all orgs.
    """
    pass


@ovdc_group.command('list',
                    short_help='Display org VDCs in vCD that are visible '
                               'to the logged in user')
@click.option(
    '-p',
    '--pks-plans',
    'list_pks_plans',
    required=False,
    is_flag=True,
    default=False,
    help="Display available PKS plans if org VDC is backed by "
         "Enterprise PKS infrastructure")
@click.pass_context
def list_ovdcs(ctx, list_pks_plans):
    """Display org VDCs in vCD that are visible to the logged in user."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        ovdc = Ovdc(client)
        result = ovdc.list(list_pks_plans=list_pks_plans)
        stdout(result, ctx, sort_headers=False)
    except Exception as e:
        stderr(e, ctx)


@ovdc_group.command('enable',
                    short_help='Set Kubernetes provider for an org VDC')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='VDC_NAME')
@click.option(
    '-k',
    '--k8s-provider',
    'k8s_provider',
    required=True,
    type=click.Choice([K8sProviders.NATIVE, K8sProviders.PKS]),
    help="Name of the Kubernetes provider to use for this org VDC")
@click.option(
    '-p',
    '--pks-plan',
    'pks_plan',
    required=False,
    metavar='PLAN_NAME',
    help=f"PKS plan to use for all cluster deployments in this org VDC "
         f"(Exclusive to --k8s-provider={K8sProviders.PKS}) (Required)")
@click.option(
    '-d',
    '--pks-cluster-domain',
    'pks_cluster_domain',
    required=False,
    help=f"Domain name suffix used to construct FQDN of deployed clusters "
         f"in this org VDC "
         f"(Exclusive to --k8s-provider={K8sProviders.PKS}) (Required)")
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='ORG_NAME',
    help="Org to use. Defaults to currently logged-in org")
def ovdc_enable(ctx, ovdc_name, k8s_provider, pks_plan, pks_cluster_domain,
                org_name):
    """Set Kubernetes provider for an org VDC."""
    if k8s_provider == K8sProviders.PKS and \
            (pks_plan is None or pks_cluster_domain is None):
        click.secho("One or both of the required params (--pks-plan,"
                    " --pks-cluster-domain) are missing", fg='yellow')
        return

    try:
        restore_session(ctx)
        client = ctx.obj['client']
        ovdc = Ovdc(client)
        if client.is_sysadmin():
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.enable_ovdc_for_k8s(
                ovdc_name,
                k8s_provider=k8s_provider,
                pks_plan=pks_plan,
                pks_cluster_domain=pks_cluster_domain,
                org_name=org_name)
        else:
            stderr("Unauthorized operation", ctx)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@ovdc_group.command('disable',
                    short_help='Disable Kubernetes cluster deployment for '
                               'an org VDC')
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
def ovdc_disable(ctx, ovdc_name, org_name):
    """Disable Kubernetes cluster deployment for an org VDC."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            ovdc = Ovdc(client)
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.disable_ovdc_for_k8s(ovdc_name, org_name=org_name)
            stdout(result, ctx)
        else:
            stderr("Unauthorized operation", ctx)
    except Exception as e:
        stderr(e, ctx)


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
    """Display information about Kubernetes provider for an org VDC."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        if client.is_sysadmin():
            ovdc = Ovdc(client)
            if org_name is None:
                org_name = ctx.obj['profiles'].get('org_in_use')
            result = ovdc.info_ovdc_for_k8s(ovdc_name, org_name=org_name)
            stdout(result, ctx)
        else:
            stderr("Unauthorized operation", ctx)
    except Exception as e:
        stderr(e, ctx)
