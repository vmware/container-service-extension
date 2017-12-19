# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
from pyvcloud.vcd.client import QueryResultFormat

TYPE_MASTER = 'master'
TYPE_NODE = 'node'
LOGGER = logging.getLogger(__name__)


def load_from_metadata(client, name=None, cluster_id=None,
                       get_leader_ip=False):
    clusters_dict = {}
    if cluster_id is None:
        query_filter = 'metadata:cse.cluster.id==STRING:*'
    else:
        query_filter = 'metadata:cse.cluster.id==STRING:%s' % cluster_id
    if name is not None:
        query_filter += ';name==%s' % name
    resource_type = 'vApp'
    if client.is_sysadmin():
        resource_type = 'adminVApp'
    q = client.get_typed_query(
        resource_type,
        query_result_format=QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields='metadata:cse.cluster.id')
    records = list(q.execute())
    nodes = []
    for record in records:
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]
        node = {
            'vapp_name': record.get('name'),
            'vdc_name': record.get('vdcName'),
            'vapp_id': vapp_id,
            'vapp_href': '%s/vApp/vapp-%s' % (client._uri, vapp_id),
            'vdc_href': '%s/vdc/%s' % (client._uri, vdc_id)
        }
        if hasattr(record, 'Metadata'):
            for me in record.Metadata.MetadataEntry:
                if me.Key == 'cse.cluster.id':
                    node['cluster_id'] = str(me.TypedValue.Value)
                elif me.Key == 'cse.version':
                    node['cse_version'] = str(me.TypedValue.Value)
        nodes.append(node)
    for node in nodes:
        cluster = {}
        cluster['name'] = node['vapp_name']
        cluster['cluster_id'] = node['cluster_id']
        cluster['status'] = ''
        cluster['leader_endpoint'] = None
        cluster['vapp_id'] = node['vapp_id']
        cluster['vapp_href'] = node['vapp_href']
        cluster['vdc_name'] = node['vdc_name']
        cluster['vdc_href'] = node['vdc_href']
        cluster['master_nodes'] = []
        cluster['nodes'] = []
        clusters_dict[cluster['name']] = cluster
    return list(clusters_dict.values())
