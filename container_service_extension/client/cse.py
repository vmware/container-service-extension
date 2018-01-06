# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

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


@vcd.group(short_help='manage kubernetes clusters')
@click.pass_context
def cse(ctx):
    """Work with kubernetes clusters in vCloud Director.

\b
    Examples
        vcd cse cluster list
            Get list of kubernetes clusters in current virtual datacenter.
\b
        vcd cse cluster create dev-cluster --network net1
            Create a kubernetes cluster in current virtual datacenter.
\b
        vcd cse cluster create prod-cluster --nodes 4 \\
                    --network net1 --storage-profile '*'
            Create a kubernetes cluster with 4 worker nodes.
\b
        vcd cse cluster delete dev-cluster
            Delete a kubernetes cluster by name.
\b
        vcd cse cluster create c1 --nodes 0 --network net1
            Create a single node kubernetes cluster for dev/test.
\b
        vcd cse template list
            Get list of CSE templates available.
    """
    if ctx.invoked_subcommand is not None:
        try:
            restore_session(ctx)
            if not ctx.obj['profiles'].get('vdc_in_use') or \
               not ctx.obj['profiles'].get('vdc_href'):
                raise Exception('select a virtual datacenter')
        except Exception as e:
            stderr(e, ctx)


@cse.group('cluster', short_help='work with clusters')
@click.pass_context
def cluster_group(ctx):
    """Work with kubernetes clusters."""
    if ctx.invoked_subcommand is not None:
        try:
            restore_session(ctx)
            if not ctx.obj['profiles'].get('vdc_in_use') or \
               not ctx.obj['profiles'].get('vdc_href'):
                raise Exception('select a virtual datacenter')
        except Exception as e:
            stderr(e, ctx)


@cse.group(short_help='work with templates')
@click.pass_context
def template(ctx):
    """Work with CSE templates."""
    if ctx.invoked_subcommand is not None:
        try:
            restore_session(ctx)
            if not ctx.obj['profiles'].get('vdc_in_use') or \
               not ctx.obj['profiles'].get('vdc_href'):
                raise Exception('select a virtual datacenter')
        except Exception as e:
            stderr(e, ctx)


@template.command('list', short_help='list templates')
@click.pass_context
def list_templates(ctx):
    try:
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
def list_clusters(ctx):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = []
        clusters = cluster.get_clusters()
        for c in clusters:
            result.append({
                'name': c['name'],
                'IP master': c['leader_endpoint'],
                'template': c['template'],
                'VMs': c['number_of_vms'],
                'vdc': c['vdc_name']
            })
        stdout(result, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='delete cluster')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-y',
    '--yes',
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to delete the cluster?')
def delete(ctx, name):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = cluster.delete_cluster(name)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='create cluster')
@click.pass_context
@click.argument('name', required=True)
@click.option(
    '-N',
    '--nodes',
    'node_count',
    required=False,
    default=2,
    help='Number of nodes to create')
@click.option(
    '-c',
    '--cpu',
    'cpu',
    required=False,
    default=None,
    help='Number of virtual cpus on each node')
@click.option(
    '-m',
    '--memory',
    'memory',
    required=False,
    default=None,
    help='Amount of memory (in MB) on each node')
@click.option(
    '-n',
    '--network',
    'network_name',
    default=None,
    required=False,
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
def create(ctx, name, node_count, cpu, memory, network_name, storage_profile,
           ssh_key_file, template):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        ssh_key = None
        if ssh_key_file is not None:
            ssh_key = ssh_key_file.read()
        result = cluster.create_cluster(
            ctx.obj['profiles'].get('vdc_in_use'),
            network_name,
            name,
            node_count=node_count,
            cpu=cpu,
            memory=memory,
            storage_profile=storage_profile,
            ssh_key=ssh_key,
            template=template)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command(short_help='get cluster config')
@click.pass_context
@click.argument('name', required=True)
@click.option('-s', '--save', is_flag=True)
def config(ctx, name, save):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_config = cluster.get_config(name)
        if save:
            save_config(ctx)
        else:
            click.secho(cluster_config)
    except Exception as e:
        stderr(e, ctx)


@cluster_group.command('info', short_help='get cluster info')
@click.pass_context
@click.argument('name', required=True)
def cluster_info(ctx, name):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        cluster_info = cluster.get_cluster_info(name)
        stdout(cluster_info, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cse.group('node', short_help='work with nodes')
@click.pass_context
def node_group(ctx):
    """Work with CSE cluster nodes."""
    if ctx.invoked_subcommand is not None:
        try:
            restore_session(ctx)
            if not ctx.obj['profiles'].get('vdc_in_use') or \
               not ctx.obj['profiles'].get('vdc_href'):
                raise Exception('select a virtual datacenter')
        except Exception as e:
            stderr(e, ctx)


@node_group.command('create', short_help='add node(s) to cluster')
@click.pass_context
@click.argument('name', metavar='<name>', required=True)
@click.option(
    '-N',
    '--nodes',
    'node_count',
    required=False,
    default=1,
    metavar='<nodes>',
    help='Number of nodes to add')
@click.option(
    '-c',
    '--cpu',
    'cpu',
    required=False,
    default=None,
    metavar='<cpu>',
    help='Number of virtual cpus on each node')
@click.option(
    '-m',
    '--memory',
    'memory',
    required=False,
    default=None,
    metavar='<memory>',
    help='Amount of memory (in MB) on each node')
@click.option(
    '-n',
    '--network',
    'network_name',
    default=None,
    required=False,
    metavar='<network>',
    help='Network name')
@click.option(
    '-s',
    '--storage-profile',
    'storage_profile',
    required=False,
    default=None,
    metavar='<storage-profile>',
    help='Name of the storage profile for the nodes')
@click.option(
    '-k',
    '--ssh-key',
    'ssh_key_file',
    required=False,
    default=None,
    type=click.File('r'),
    metavar='<ssh-key>',
    help='SSH public key to connect to the guest OS on the VM')
@click.option(
    '-t',
    '--template',
    'template',
    required=False,
    default=None,
    metavar='<template>',
    help='Name of the template to instantiate nodes from')
@click.option(
    '--type',
    'node_type',
    required=False,
    default='node',
    type=click.Choice(['node']),
    help='type of node to add')
def create_node(ctx, name, node_count, cpu, memory, network_name,
                storage_profile, ssh_key_file, template, node_type):
    try:
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
            template=template)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@node_group.command('list', short_help='list nodes')
@click.pass_context
@click.argument('name', required=True)
def list_nodes(ctx, name):
    try:
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
    try:
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
        docs = yaml.load_all(stream)
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
