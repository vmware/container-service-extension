# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import logging
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import RESOURCE_TYPES


TYPE_MASTER = 'master'
TYPE_NODE = 'node'
LOGGER = logging.getLogger(__name__)


class Node(object):

    def __init__(self, name, node_type=TYPE_NODE, node_id='', href=''):
        self.name = name
        self.node_type = node_type
        self.node_id = node_id
        self.href = href
        self.ip = ''
        self.cluster_id = ''
        self.cluster_name = ''

    def __repr__(self):
        return self.toJSON()

    def toJSON(self):
        return json.dumps(self,
                          default=lambda o: o.__dict__,
                          sort_keys=True,
                          indent=4)


class Cluster(object):

    def __init__(self, name=None, cluster_id=''):
        self.name = name
        self.cluster_id = cluster_id
        self.master_nodes = []
        self.nodes = []
        self.vdc = None
        self.status = None
        self.leader_endpoint = None

    def __repr__(self):
        return self.toJSON()

    def toJSON(self):
        return json.dumps(self,
                          default=lambda o: o.__dict__,
                          sort_keys=True,
                          indent=4)


#  TODO(optimize after fix for bug #1945003)
def load_from_metadata(client, name=None):
    clusters = []
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
                nodes.append({'vapp_name': record.get('name'),
                              'vapp_id': record.get('id'),
                              'vdc_name': record.get('vdcName'),
                              'node_type': md.TypedValue.Value})
                break

    for node in nodes:
        q = client.get_typed_query(
                'vApp',
                query_result_format=QueryResultFormat.
                ID_RECORDS,
                qfilter='id==%s' % node['vapp_id'],
                fields='metadata:cse.cluster.name,metadata:cse.cluster.id,metadata:cse.node.type')
        records = list(q.execute())
        for record in records:
            for md in record.Metadata.MetadataEntry:
                if md.Key == 'cse.cluster.name':
                    node['cluster_name'] = md.TypedValue.Value
                elif md.Key == 'cse.cluster.id':
                    node['cluster_id'] = md.TypedValue.Value

    clusters_dict = {}
    for node in nodes:
        print(node)
        if node['cluster_name'] in clusters_dict.keys():
            cluster = clusters_dict[node['cluster_name']]
        else:
            cluster = {'name': '%s' % node['cluster_name']}
            if 'cluster_id' in node.keys():
                cluster['cluster_id'] = '%s' % node['cluster_id']
            else:
                cluster['cluster_id'] = ''
            cluster['status'] = ''
            cluster['leader_endpoint'] = ''
            cluster['vdc_name'] = '%s' % node['vdc_name']
            cluster['master_nodes'] = []
            cluster['nodes'] = []
        if node['node_type'] == TYPE_MASTER:
            cluster['master_nodes'].append(node['vapp_name'])
            cluster['leader_endpoint'] = '%s' % node['vapp_name']
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
        nodes.append({'vapp_name': record.get('name'),
                      'vapp_id': record.get('id'),
                      'vapp_href': record.get('href'),
                      'vdc_name': record.get('vdcName'),
                      'vdc_href': record.get('vdc')})
    return nodes
