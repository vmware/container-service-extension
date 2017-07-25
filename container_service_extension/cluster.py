# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import logging

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
