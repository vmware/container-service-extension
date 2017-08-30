# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.vapp import VApp


TYPE_MASTER = 'master'
TYPE_NODE = 'node'
LOGGER = logging.getLogger(__name__)


#  TODO(optimize after fix for bug #1945003)
def load_from_metadata(client, name=None):
    q = client.get_typed_query(
            'vApp',
            query_result_format=QueryResultFormat.
            ID_RECORDS,
            qfilter='metadata:cse.node.type==STRING:*',
            fields='metadata:cse.node.type')
    records = list(q.execute())
    nodes = []
    for record in records:
        for md in record.Metadata.MetadataEntry:
            if md.Key == 'cse.node.type':
                vapp_id = record.get('id').split(':')[-1]
                nodes.append({'vapp_name': record.get('name'),
                              'vapp_id': vapp_id,
                              'vapp_href': '%s/vApp/vapp-%s' %
                              (client._uri, vapp_id),
                              'vdc_name': record.get('vdcName'),
                              'node_type': md.TypedValue.Value})
                break

    for node in nodes:
        q = client.get_typed_query(
                'vApp',
                query_result_format=QueryResultFormat.
                ID_RECORDS,
                qfilter='id==%s' % node['vapp_id'],
                fields='metadata:cse.cluster.name' +
                       ',metadata:cse.cluster.id' +
                       ',metadata:cse.node.type')
        records = list(q.execute())
        for record in records:
            for md in record.Metadata.MetadataEntry:
                if md.Key == 'cse.cluster.name':
                    node['cluster_name'] = md.TypedValue.Value
                elif md.Key == 'cse.cluster.id':
                    node['cluster_id'] = md.TypedValue.Value

    clusters_dict = {}
    for node in nodes:
        if node['cluster_name'] in clusters_dict.keys():
            cluster = clusters_dict[node['cluster_name']]
        else:
            cluster = {'name': '%s' % node['cluster_name']}
            if 'cluster_id' in node.keys():
                cluster['cluster_id'] = '%s' % node['cluster_id']
            else:
                cluster['cluster_id'] = ''
            cluster['status'] = ''
            cluster['leader_endpoint'] = None
            cluster['vdc_name'] = '%s' % node['vdc_name']
            cluster['master_nodes'] = []
            cluster['nodes'] = []
        if node['node_type'] == TYPE_MASTER:
            cluster['master_nodes'].append(node['vapp_name'])
            cluster['leader_endpoint'] = None
            if node['vapp_name'].endswith('-m1'):
                try:
                    vapp = VApp(client, vapp_href=node['vapp_href'])
                    cluster['leader_endpoint'] = '%s' % \
                        vapp.get_primary_ip(node['vapp_name'])
                except Exception:
                    import traceback
                    LOGGER.debug(traceback.format_exc())
        elif node['node_type'] == TYPE_NODE:
            cluster['nodes'].append(node['vapp_name'])
        clusters_dict[node['cluster_name']] = cluster
    return clusters_dict.values()


#  TODO(optimize after fix for bug #1945003)
def load_from_metadata_by_id(client, cluster_id):
    q = client.get_typed_query(
            'vApp',
            query_result_format=QueryResultFormat.
            RECORDS,
            qfilter='metadata:cse.cluster.id==STRING:%s' % cluster_id,
            fields='metadata:cse.cluster.name,metadata:cse.node.type')
    records = list(q.execute())
    nodes = []
    for record in records:
        node = {'vapp_name': record.get('name'),
                'vapp_id': record.get('id'),
                'vapp_href': record.get('href'),
                'vdc_name': record.get('vdcName'),
                'vdc_href': record.get('vdc')}
        if node['vapp_name'].endswith('-m1'):
            node['node_type'] = TYPE_MASTER
        else:
            node['node_type'] = TYPE_NODE
        vapp = VApp(client, vapp_href=record.get('href'))
        node['ip'] = vapp.get_primary_ip(record.get('name'))
        node['moid'] = vapp.get_vm_moid(record.get('name'))
        nodes.append(node)
    return nodes


#  TODO(optimize after fix for bug #1945003)
def load_from_metadata_by_name(client, cluster_name):
    q = client.get_typed_query(
            'vApp',
            query_result_format=QueryResultFormat.
            RECORDS,
            qfilter='metadata:cse.cluster.name==STRING:%s' % cluster_name,
            fields='metadata:cse.cluster.name,metadata:cse.node.type')
    records = list(q.execute())
    nodes = []
    for record in records:
        node = {'vapp_name': record.get('name'),
                'vapp_id': record.get('id'),
                'vapp_href': record.get('href'),
                'vdc_name': record.get('vdcName'),
                'vdc_href': record.get('vdc')}
        if node['vapp_name'].endswith('-m1'):
            node['node_type'] = TYPE_MASTER
        else:
            node['node_type'] = TYPE_NODE
        vapp = VApp(client, vapp_href=record.get('href'))
        node['ip'] = vapp.get_primary_ip(record.get('name'))
        node['moid'] = vapp.get_vm_moid(record.get('name'))
        nodes.append(node)
    return nodes
