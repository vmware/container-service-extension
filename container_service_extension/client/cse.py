# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from os.path import expanduser
from os.path import join

import click

from container_service_extension.client.cluster import Cluster

from vcd_cli.utils import restore_session
from vcd_cli.utils import stderr
from vcd_cli.utils import stdout
from vcd_cli.vcd import abort_if_false
from vcd_cli.vcd import vcd

import yaml

@vcd.group(short_help='manage clusters')
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


@cse.group(short_help='work with clusters')
@click.pass_context
def cluster(ctx):
    """Work with kubernetes clusters."""

    if ctx.invoked_subcommand is not None:
        try:
            restore_session(ctx)
            if not ctx.obj['profiles'].get('vdc_in_use') or \
               not ctx.obj['profiles'].get('vdc_href'):
                raise Exception('select a virtual datacenter')
        except Exception as e:
            stderr(e, ctx)


@cse.group(short_help='manage CSE templates')
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
            result.append({'name': t['name'],
                           'description': t['description'],
                           'catalog': t['catalog'],
                           'catalog_item': t['catalog_item'],
                           'is_default': t['is_default'],
                           })
        stdout(result, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cluster.command('list', short_help='list clusters')
@click.pass_context
def list_clusters(ctx):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        result = []
        clusters = cluster.get_clusters()
        for c in clusters:
            result.append({'name': c['name'],
                           'IP master': c['leader_endpoint'],
                           'template': c['template'],
                           'VMs': c['number_of_vms'],
                           'vdc': c['vdc_name']
                           })
        stdout(result, ctx, show_id=True)
    except Exception as e:
        stderr(e, ctx)


@cluster.command(short_help='delete cluster')
@click.pass_context
@click.argument('name',
                metavar='<name>',
                required=True)
@click.option('-y',
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


@cluster.command(short_help='create cluster')
@click.pass_context
@click.argument('name',
                metavar='<name>',
                required=True)
@click.option('-N',
              '--nodes',
              'node_count',
              required=False,
              default=2,
              metavar='<nodes>',
              help='Number of nodes to create')
@click.option('-c',
              '--cpu',
              'cpu_count',
              required=False,
              default=None,
              metavar='<cpu-count>',
              help='Number of virtual cpus on each node')
@click.option('-m',
              '--memory',
              'memory',
              required=False,
              default=None,
              metavar='<memory>',
              help='Amount of memory (in MB) on each node')
@click.option('-n',
              '--network',
              'network_name',
              default=None,
              required=False,
              metavar='<network>',
              help='Network name')
@click.option('-s',
              '--storage-profile',
              'storage_profile',
              required=False,
              default=None,
              metavar='<storage-profile>',
              help='Name of the storage profile for the nodes')
@click.option('-k',
              '--ssh-key',
              'ssh_key_file',
              required=False,
              default=None,
              type=click.File('r'),
              metavar='<ssh-key>',
              help='SSH public key to connect to the guest OS on the VM')
@click.option('-t',
              '--template',
              'template',
              required=False,
              default=None,
              metavar='<template>',
              help='Name of the template to instantiate nodes from')
def create(ctx, name, node_count, cpu_count, memory, network_name,
           storage_profile, ssh_key_file, template):
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
                    cpu_count=cpu_count,
                    memory=memory,
                    storage_profile=storage_profile,
                    ssh_key=ssh_key,
                    template=template)
        stdout(result, ctx)
    except Exception as e:
        stderr(e, ctx)


@cluster.command(short_help='get cluster config')
@click.pass_context
@click.argument('name',
                metavar='<name>',
                required=True)
def config(ctx, name):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
        click.secho(cluster.get_config(name))
    except Exception as e:
        stderr(e, ctx)


@cluster.command('add-node', short_help='add node')
@click.pass_context
@click.argument('name',
                metavar='<name>',
                required=True)
@click.option('-N',
              '--nodes',
              'node_count',
              required=False,
              default=1,
              metavar='<nodes>',
              help='Number of nodes to add')
@click.option('-c',
              '--cpu',
              'cpu_count',
              required=False,
              default=None,
              metavar='<cpu-count>',
              help='Number of virtual cpus on each node')
@click.option('-m',
              '--memory',
              'memory',
              required=False,
              default=None,
              metavar='<memory>',
              help='Amount of memory (in MB) on each node')
@click.option('-n',
              '--network',
              'network_name',
              default=None,
              required=False,
              metavar='<network>',
              help='Network name')
@click.option('-s',
              '--storage-profile',
              'storage_profile',
              required=False,
              default=None,
              metavar='<storage-profile>',
              help='Name of the storage profile for the nodes')
@click.option('-k',
              '--ssh-key',
              'ssh_key_file',
              required=False,
              default=None,
              type=click.File('r'),
              metavar='<ssh-key>',
              help='SSH public key to connect to the guest OS on the VM')
@click.option('-t',
              '--template',
              'template',
              required=False,
              default=None,
              metavar='<template>',
              help='Name of the template to instantiate nodes from')
@click.option('--type',
              'node_type',
              required=False,
              default='node',
              type=click.Choice(['node']),
              help='type of node to add')
def add_node(ctx, name, node_count, cpu_count, memory, network_name,
           storage_profile, ssh_key_file, template, node_type):
    try:
        client = ctx.obj['client']
        cluster = Cluster(client)
    except Exception as e:
        stderr(e, ctx)


@cluster.command('save-config')
@click.pass_context
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
                # elif k == 'clusters':
                #     for cluster in v:
                #         print(cluster['name'], cluster['cluster']['server'])
                # elif k == 'users':
                #     for user in v:
                #         print(user['name'], user['user'])

    except Exception as e:
        stderr(e, ctx)
