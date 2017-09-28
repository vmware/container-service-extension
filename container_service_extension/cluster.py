# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.vapp import VApp


TYPE_MASTER = 'master'
TYPE_NODE = 'node'
LOGGER = logging.getLogger(__name__)


def load_from_metadata(client,
                       name=None,
                       cluster_id=None,
                       get_leader_ip=False):
    clusters_dict = {}
    if name is not None:
        query_filter = 'metadata:cse.cluster.name==STRING:%s' % name
    elif cluster_id is not None:
        query_filter = 'metadata:cse.cluster.id==STRING:%s' % cluster_id
    else:
        query_filter = 'metadata:cse.cluster.id==STRING:*'
    q = client.get_typed_query(
            'vApp',
            query_result_format=QueryResultFormat.
            ID_RECORDS,
            qfilter=query_filter,
            fields='metadata:cse.cluster.name' +
                   ',metadata:cse.cluster.id' +
                   ',metadata:cse.node.type')
    records = list(q.execute())
    nodes = []
    for record in records:
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]
        node = {'vapp_name': record.get('name'),
                'vdc_name': record.get('vdcName'),
                'vapp_id': vapp_id,
                'vapp_href': '%s/vApp/vapp-%s' %
                (client._uri, vapp_id),
                'vdc_href': '%s/vdc/%s' %
                (client._uri, vdc_id)
                }
        if hasattr(record, 'Metadata'):
            for me in record.Metadata.MetadataEntry:
                if me.Key == 'cse.cluster.name':
                    node['cluster_name'] = me.TypedValue.Value
                elif me.Key == 'cse.cluster.id':
                    node['cluster_id'] = me.TypedValue.Value
                elif me.Key == 'cse.node.type':
                    node['node_type'] = me.TypedValue.Value
            nodes.append(node)
    for node in nodes:
        if 'cluster_name' in node:
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
                cluster['vdc_href'] = node['vdc_href']
                cluster['master_nodes'] = []
                cluster['nodes'] = []
            n = {'name': node['vapp_name'],
                 'href': node['vapp_href']}
            if node['node_type'] == TYPE_MASTER:
                cluster['master_nodes'].append(n)
                cluster['leader_endpoint'] = None
                if get_leader_ip and node['vapp_name'].endswith('-m1'):
                    try:
                        vapp = VApp(client, href=node['vapp_href'])
                        cluster['leader_endpoint'] = '%s' % \
                            vapp.get_primary_ip(node['vapp_name'])
                        cluster['leader_moid'] = vapp.get_vm_moid(
                            node['vapp_name'])
                    except Exception:
                        import traceback
                        LOGGER.debug(traceback.format_exc())
            elif node['node_type'] == TYPE_NODE:
                cluster['nodes'].append(n)
            clusters_dict[node['cluster_name']] = cluster
    return list(clusters_dict.values())
