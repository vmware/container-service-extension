# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
from os.path import expanduser
from os.path import join

import click
from vcd_cli.utils import restore_session
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout
from vcd_cli.vcd import abort_if_false
from vcd_cli.vcd import vcd
import yaml

from container_service_extension.client.cluster import Cluster
from container_service_extension.client.ovdc import Ovdc
from container_service_extension.client.system import System
from container_service_extension.service import Service


@vcd.group(short_help='manage kubernetes clusters')
@click.pass_context
def cse(ctx):
    """Work with Kubernetes clusters in vCloud Director.

\b
    Examples
        vcd cse version
            Display CSE version. If CSE version is displayed, then vcd-cli has
            been properly configured to run CSE commands.
    """


@cse.command(short_help='show version')
@click.pass_context
def version(ctx):
    """Show CSE version."""
    ver_obj = Service.version()
    ver_str = '%s, %s, version %s' % (ver_obj['product'],
                                      ver_obj['description'],
                                      ver_obj['version'])
    stdout(ver_obj, ctx, ver_str)


@cse.group('cluster', short_help='work with clusters')
@click.pass_context
def cluster_group(ctx):
    """Work with Kubernetes clusters.

\b
    Cluster names should follow the syntax for valid hostnames and can have
    up to 25 characters .`system`, `template` and `swagger*` are reserved
    words and cannot be used to name a cluster.
\b
    Examples
        vcd cse cluster list
            Displays clusters in vCD that are visible to your user status.
\b
        vcd cse cluster list -vdc myOvdc
            Displays clusters residing in vdc 'myOvdc'.
\b
        vcd cse cluster delete mycluster --yes
            Attempts to delete cluster 'mycluster' without prompting.
\b
        vcd cse cluster delete mycluster -vdc myOvdc
            Deletes cluster residing in vdc 'myOvdc'. Specifying optional
            param --vdc lets CSE server to efficiently locate and
            delete the cluster.
\b
        vcd cse cluster create mycluster -n mynetwork
            Attempts to create a Kubernetes cluster named 'mycluster'
            with 2 worker nodes in the current VDC. This cluster will be
            connected to Org VDC network 'mynetwork'. All VMs will use the
            default template.
\b
        vcd cse cluster create mycluster -n mynetwork --template photon-v2 \\
        --nodes 1 --cpu 3 --memory 1024 --storage-profile mystorageprofile \\
        --ssh-key ~/.ssh/id_rsa.pub --enable-nfs
            Attempts to create a Kubernetes cluster named 'mycluster' on vCD
            with 1 worker node and 1 NFS node. This cluster will be connected
            to Org VDC network 'mynetwork'. All VMs will use the template
            'photon-v2'. All VMs in the cluster will have 3 vCPUs on each node
            with 1024mb of memory each. All VMs will use the storage profile
            'mystorageprofile'. The public ssh key at '~/.ssh/id_rsa.pub' will
            be placed into all VMs for user accessibility.
\b
        vcd cse cluster resize mycluster -N 10 --network mynetwork
            Attempts to resize the cluster size to 10 worker nodes. The Option
             "--network" is mandatory if the cluster is vCD-powered and
             it is optional if the cluster is PKS-powered.
\b
        vcd cse cluster resize mycluster -N 10 --vcd myovdc
            Attempts to resize the cluster size to 10 worker nodes. Specifying
             optional param --vdc forces CSE server to narrow down the search
             range of locating the cluster to 'myOvdc' only (improves
             turnaround time of the command).
\b
        vcd cse cluster resize mycluster -N 10 --disable-rollback
            Attempts to resize the cluster size to 10 worker nodes. On any
            failure of creation of nodes, it leaves the nodes as-is in an error
            state for admins to troubleshoot.
\b
        vcd cse cluster delete mycluster --yes
            Attempts to delete cluster 'mycluster' without prompting.
\b
        vcd cse cluster delete mycluster -vdc myOvdc
            Deletes cluster residing in vdc 'myOvdc'. Specifying optional param
             --vdc forces CSE server to narrow down the search range of
             locating the cluster to 'myOvdc' only. (improves turnaround time
             of the command).
\b
        vcd cse cluster create mycluster --pks-external-hostname api.pks.local
        --pks-plan 'myPlan'
            Attempts to create a Kubernetes cluster named 'mycluster' with
            external host name as 'api.pks.local' and available PKS-plan 'myPlan
            using the VDC in context explicitly dedicated for PKS cluster creation.

\b
        vcd cse cluster create mycluster --pks-external-hostname api.pks.local
        --pks-plan 'myPlan' --vdc 'myVdc'
            Attempts to create a Kubernetes cluster named 'mycluster' with
            external host name as 'api.pks.local' and available PKS-plan 'myPlan
            in the given VDC dedicated explicitly for PKS cluster creation.
\b
        vcd cse cluster config mycluster
            Display configuration information about cluster named 'mycluster'.

\b
        vcd cse cluster config mycluster --vdc myVdc
            Display configuration information about cluster named 'mycluster'.
            Specifying optional param --vdc lets CSE server to efficiently
            locate and retrieve the cluster configuration.

\b
        vcd cse cluster info mycluster
            Display detailed information about cluster named 'mycluster'.
\b
        vcd cse cluster info mycluster --vdc myOvdc
            Display detailed information on cluster 'mycluster', which is
            residing in vdc 'myOvdc'. Specifying optional param --vdc
            forces CSE server to narrow down the search range of locating the
            cluster to 'myOvdc' only. (improves turnaround time of the command)
    """
    pass


@cse.group(short_help='work with templates')
@click.pass_context
def template(ctx):
    """Work with CSE templates.

\b
    Examples
        vcd cse template list
            Displays list of available VM templates from which Kubernetes
            cluster nodes can be instantiated.
    """
    pass


@template.command('list', short_help='list templates')
@click.pass_context
def list_templates(ctx):
    """Display CSE templates."""
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


@cluster_group.command('list', short_help='list clusters')
@click.pass_context
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    help='Name of the virtual datacenter')
def list_clusters(ctx, vdc):
    """Display list of Kubernetes clusters."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.get_clusters(vdc)
        stdout(result, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='delete cluster')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    help='Name of the virtual datacenter')
@click.option(
    '-y',
    '--yes',
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to delete the cluster?')
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


@cluster_group.command(short_help='create cluster')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    help='Name of the virtual datacenter')
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
    help='Number of virtual CPUs on each node')
@click.option(
    '-m',
    '--memory',
    'memory',
    required=False,
    default=None,
    type=click.INT,
    help='Amount of memory (in MB) on each node')
@click.option(
    '-n',
    '--network',
    'network_name',
    default=None,
    required=False,
    help='Network name (Mandatory field to be '
         'specified for vCD powered clusters. '
         'Optional for PKS backed clusters)')
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
    '--enable-nfs',
    'enable_nfs',
    is_flag=True,
    required=False,
    default=False,
    metavar='[enable nfs]',
    help='Creates an additional node of type NFS')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    required=False,
    default=True,
    help='Disable rollback for cluster')
@click.option(
    '--pks-external-hostname',
    'pks_ext_host',
    required=False,
    default=None,
    help='Address from which to access Kubernetes API for PKS. '
         'Required for deploying PKS clusters. Optional otherwise.')
@click.option(
    '--pks-plan',
    'pks_plan',
    required=False,
    default=None,
    help='Preconfigured PKS plan to use for deploying the cluster. '
         'Required for deploying PKS clusters. Optional otherwise.')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='<org-name>',
    help="org name - optional")
def create(ctx, name, vdc, node_count, cpu, memory, network_name, storage_profile,
           ssh_key_file, template, enable_nfs, disable_rollback,
           pks_ext_host, pks_plan, org_name):
    """Create a Kubernetes cluster."""
    try:
        restore_session(ctx, vdc_required=True)
        client = ctx.obj['client']
        cluster = Cluster(client)
        ssh_key = None
        vdc_to_use = vdc if vdc is not None \
            else ctx.obj['profiles'].get('vdc_in_use')
        if org_name is None:
            org_name = ctx.obj['profiles'].get('org_in_use')
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()
        result = cluster.create_cluster(
            vdc_to_use,
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
            pks_ext_host=pks_ext_host,
            pks_plan=pks_plan,
            org=org_name)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='resize cluster')
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
    help='Network name (mandatory for vCD-powered clusters; '
         'optional for PKS-powered clusters')
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    help='Name of the virtual datacenter')
@click.option(
    '--disable-rollback',
    'disable_rollback',
    is_flag=True,
    required=False,
    default=True,
    help='Disable rollback for failed node creation '
         '(applicable only for vCD-powered clusters')
def resize(ctx, name, node_count, network_name, vdc, disable_rollback):
    """Resize the cluster to specified worker node count.

    Automatic scale down is not supported on vCD powered Kubernetes clusters.
    Use 'vcd cse node delete' command to do so.
    """
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.resize_cluster(
            vdc=ctx.obj['profiles'].get('vdc_in_use') if vdc is None else vdc,
            network_name=network_name,
            cluster_name=name,
            node_count=node_count,
            disable_rollback=disable_rollback)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='get cluster config')
@click.pass_context
@click.argument('name', required=True)
@click.option('-s', '--save', is_flag=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    help='Name of the virtual datacenter')
def config(ctx, name, save, vdc):
    """Display cluster configuration info."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_config = cluster.get_config(name, vdc)
        if os.name == 'nt':
            cluster_config = str.replace(cluster_config, '\n', '\r\n')
        if save:
            save_config(ctx)
        else:
            click.secho(cluster_config)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('info', short_help='get cluster info')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-v',
    '--vdc',
    'vdc',
    required=False,
    default=None,
    help='Name of the virtual datacenter')
def cluster_info(ctx, name, vdc):
    """Display info about a Kubernetes cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_info = cluster.get_cluster_info(name, vdc)
        stdout(cluster_info, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cse.group('node', short_help='work with nodes')
@click.pass_context
def node_group(ctx):
    """Work with CSE cluster nodes.

\b
    Examples
        vcd cse node create mycluster -n mynetwork
            Attempts to add a node to Kubernetes cluster named 'mycluster' on
            vCD. The node will be connected to Org VDC network 'mynetwork' and
            will be created from the default template.
\b
        vcd cse node create mycluster -n mynetwork --nodes 2 --cpu 3 \\
        --memory 1024 --storage-profile mystorageprofile \\
        --ssh-key ~/.ssh/id_rsa.pub --template photon-v2 --type nfsd
            Attempts to add 2 nfsd nodes to Kubernetes cluster named
            'mycluster' on vCD. The nodes will be connected to Org VDC
            network 'mynetwork' and will be created from the template
            'photon-v2'. Each node will use 3 vCPUs, have 1024mb of memory,
            and use the storage profile 'mystorageprofile'. The public ssh
            key at '~/.ssh/id_rsa.pub' will be placed into all VMs for
            user accessibility.
\b
        vcd cse node list mycluster
            Displays nodes in 'mycluster' that are visible to your user status.
\b
        vcd cse node info mycluster node-xxxx
            Display information about 'node-xxxx' in 'mycluster', such as
            IP address, memory, name, node type, cpu, status. If node is
            type 'nfs', 'exports' shared will also be displayed.
\b
        vcd cse node delete mycluster node-xxxx --yes
            Attempts to delete node 'node-xxxx' in 'mycluster'
            without prompting.
    """
    pass


@node_group.command('info', short_help='get node info')
@click.pass_context
@click.argument('cluster_name', required=True)
@click.argument('node_name', required=True)
def node_info(ctx, cluster_name, node_name):
    """Display info about a specific node."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        node_info = cluster.get_node_info(cluster_name, node_name)
        stdout(node_info, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@node_group.command('create', short_help='add node(s) to cluster')
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
    help='Amount of memory (in MB) on each node')
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
    help='type of node to add')
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
    """Add a node to a Kubernetes cluster."""
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


@node_group.command('list', short_help='list nodes')
@click.pass_context
@click.argument('name', required=True)
def list_nodes(ctx, name):
    """Display nodes in a Kubernetes cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_info = cluster.get_cluster_info(name)
        all_nodes = cluster_info['master_nodes'] + cluster_info['nodes']
        stdout(all_nodes, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@node_group.command('delete', short_help='delete node(s)')
@click.pass_context
@click.argument('name', required=True)
@click.argument('node-names', nargs=-1)
@click.option(
    '-y',
    '--yes',
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to delete the node(s)')
@click.option('-f', '--force', is_flag=True, help='Force delete node VM(s)')
def delete_nodes(ctx, name, node_names, force):
    """Delete node(s) in a Kubernetes cluster."""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.delete_nodes(ctx.obj['profiles'].get('vdc_in_use'),
                                      name, node_names, force)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


def save_config(ctx):
    try:
        f = join(expanduser('~'), '.kube/config')
        stream = open(f, 'r')
        docs = yaml.safe_load_all(stream)
        for doc in docs:
            for k, v in doc.items():
                if k == 'contexts':
                    for c in v:
                        print(c['name'])
                        print('  cluster: %s' % c['context']['cluster'])
                        print('  user:    %s' % c['context']['user'])
                elif k == 'clusters':
                    for cluster in v:
                        print(cluster['name'], cluster['cluster']['server'])
                elif k == 'users':
                    for user in v:
                        print(user['name'], user['user'])
    except Exception as e:
        stderr(e, ctx)


@cse.group('system', short_help='work with CSE service')
@click.pass_context
def system_group(ctx):
    """Work with CSE service (system daemon).

\b
    Examples
        vcd cse system info
            Displays detailed information about CSE
\b
        vcd cse system enable --yes
            Attempts to enable CSE system daemon without prompting
\b
        vcd cse system stop --yes
            Attempts to stop CSE system daemon without prompting
\b
        vcd cse system disable --yes
            Attempts to disable CSE system daemon without prompting
    """
    pass


@system_group.command('info', short_help='CSE system info')
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


@system_group.command('stop', short_help='gracefully stop CSE service')
@click.pass_context
@click.option(
    '-y',
    '--yes',
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to stop the service?')
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


@system_group.command('enable', short_help='enable CSE service')
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


@system_group.command('disable', short_help='disable CSE service')
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


@cse.group('ovdc', short_help='enable/disable ovdc for kubernetes on container'
                              ' providers like PKS or vCD',
           options_metavar='[options]')
@click.pass_context
def ovdc_group(ctx):
    """Enable/disable ovdc for kubernetes deployment on container-provider.

\b
    Note
       All sub-commands execute in the context of organization specified
       via --org option; it defaults to current organization-in-use
       if --org option is not specified.

\b
    Examples
        vcd cse ovdc enablek8s 'myOrgVdc' --container-provider pks
        --pks-plans 'plan1,plan2'
            Enable 'myOrgVdc' for k8s deployment on container-provider
            PKS with plans 'plan1' and 'plan2'. If no --org-name is provided,
            organization of the logged-in user is used to find 'myOrgVdc'.
\b
        vcd cse ovdc enablek8s 'myOrgVdc' --container-provider pks
        --pks-plans 'plan1,plan2' --org 'myOrg'
            Enable 'myOrgVdc' that backs organization 'myOrg', for k8s
            deployment on PKS with plans:'plan1' and 'plan2'.
\b
        vcd cse ovdc enablek8s 'myOrgVdc' --container-provider vcd
        --org 'myOrg'
            Enable 'myOrgVdc' that backs 'myOrg' for k8s deployment on vCD.
\b
        vcd cse ovdc disablek8s 'myOrgVdc' --org 'myOrg'
            Disable 'myOrgVdc' that backs 'myOrg' for k8s deployment.
\b
        vcd cse ovdc disablek8s 'myOrgVdc'
            Disable 'myOrgVdc' that backs organization of the logged-in user
            for k8s deployment.
\b
        vcd cse ovdc infok8s 'myOrgVdc' --org 'myOrg'
            Displays metadata information about 'myOrgVdc' that backs
            organization 'myOrg' of the logged-in user for k8s deployment.
\b
        vcd cse ovdc list
            Displays list of ovdcs in a given org. If executed by
            System-administrator, it will display all ovdcs from all orgs.
    """
    pass

@ovdc_group.command('list', short_help='list ovdcs')
@click.pass_context
def list(ctx):
    """List ovdcs in a given Org or System"""
    try:
        restore_session(ctx)
        client = ctx.obj['client']
        ovdc = Ovdc(client)
        result = ovdc.list()
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@ovdc_group.command('enablek8s', short_help='enable ovdc for kubernetes')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='<ovdc_name>')
@click.option(
    '-c',
    '--container-provider',
    'container_provider',
    required=True,
    type=click.Choice(['vcd', 'pks']),
    help="name of the container provider. If set to 'pks', --pks-plans "
         "argument is required")
@click.option(
    '-p',
    '--pks-plans',
    'pks_plans',
    required=False,
    help="This is a required argument, if --container-provider"
         " is set to 'pks'")
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='[org-name]',
    help="org name")
def enablek8s(ctx, ovdc_name, container_provider, pks_plans, org_name):
    """Enable ovdc for k8s deployment on PKS or vCD."""
    if 'pks' == container_provider and pks_plans is None:
        click.echo("Must provide PKS plans using --pks-plans")
    else:
        try:
            restore_session(ctx)
            client = ctx.obj['client']
            ovdc = Ovdc(client)
            if client.is_sysadmin():
                if org_name is None:
                    org_name = ctx.obj['profiles'].get('org_in_use')
                result = ovdc.enable_ovdc_for_k8s(
                    ovdc_name,
                    container_provider=container_provider,
                    pks_plans=pks_plans,
                    org_name=org_name)
            else:
                stderr("Unauthorized operation", ctx)
            stdout(result, ctx)
        except Exception as e:
            stderr(e, ctx)


@ovdc_group.command('disablek8s', short_help='disable ovdc for kubernetes')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='<ovdc_name>')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='[org-name]',
    help="org name")
def disablek8s(ctx, ovdc_name, org_name):
    """Disable ovdc for k8s deployment."""
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


@ovdc_group.command('infok8s', short_help='info on ovdc for kubernetes')
@click.pass_context
@click.argument('ovdc_name', required=True, metavar='<ovdc_name>')
@click.option(
    '-o',
    '--org',
    'org_name',
    default=None,
    required=False,
    metavar='[org-name]',
    help="org name")
def infok8s(ctx, ovdc_name, org_name):
    """Get information on ovdc for k8s deployment."""
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
