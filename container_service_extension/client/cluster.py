# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

import requests

from container_service_extension.cluster import TYPE_NODE


class Cluster(object):
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def get_templates(self):
        method = 'GET'
        uri = '%s/template' % (self._uri)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        if response.status_code == requests.codes.ok:
            return json.loads(response.content.decode("utf-8"))
        else:
            raise Exception(json.loads(response.content))

    def get_clusters(self):
        method = 'GET'
        uri = self._uri
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        if response.status_code == requests.codes.ok:
            return json.loads(response.content.decode("utf-8"))
        else:
            raise Exception(json.loads(response.content))

    def get_cluster_info(self, name):
        method = 'GET'
        uri = '%s/%s/info' % (self._uri, name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        if response.status_code == requests.codes.ok:
            return json.loads(response.content.decode("utf-8"))
        else:
            raise Exception(json.loads(response.content))

    def create_cluster(self,
                       vdc,
                       network_name,
                       name,
                       node_count=2,
                       cpu=None,
                       memory=None,
                       storage_profile=None,
                       ssh_key=None,
                       template=None):
        """Create a new Kubernetes cluster.

        :param vdc: (str): The name of the vdc in which the cluster will be
            created
        :param network_name: (str): The name of the network to which the
            cluster vApp will connect to
        :param name: (str): The name of the cluster
        :param node_count: (str): The number ofs nodes
        :param cpu: (str): The number of virtual cpus on each of the
            nodes in the cluster
        :param memory: (str): The amount of memory (in MB) on each of the nodes
            in the cluster
        :param storage_profile: (str): The name of the storage profile which
            will back the cluster
        :param ssh_key: (str): The ssh key that clients can use to log into the
            node vms without explicitly providing passwords
        :param template: (str): The name of the template to use to
            instantiate the nodes
        :return: (json) A parsed json object describing the requested cluster.
        """
        method = 'POST'
        uri = self._uri
        data = {
            'name': name,
            'node_count': node_count,
            'vdc': vdc,
            'cpu': cpu,
            'memory': memory,
            'network': network_name,
            'storage_profile': storage_profile,
            'ssh_key': ssh_key,
            'template': template
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        if response.status_code == requests.codes.accepted:
            return json.loads(response.content)
        else:
            raise Exception(json.loads(response.content).get('message'))

    def delete_cluster(self, cluster_name):
        method = 'DELETE'
        uri = '%s/%s' % (self._uri, cluster_name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/*+json')
        if response.status_code == requests.codes.accepted:
            return json.loads(response.content)
        else:
            raise Exception(json.loads(response.content).get('message'))

    def get_config(self, cluster_name):
        method = 'GET'
        uri = '%s/%s/config' % (self._uri, cluster_name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='text/x-yaml',
            auth=None)
        if response.status_code == requests.codes.ok:
            return response.content.decode('utf-8').replace('\\n', '\n')[1:-1]
        else:
            raise Exception(json.loads(response.content))

    def add_node(self,
                 vdc,
                 network_name,
                 name,
                 node_count=1,
                 cpu=None,
                 memory=None,
                 storage_profile=None,
                 ssh_key=None,
                 template=None,
                 node_type=TYPE_NODE):
        """Add nodes to a Kubernetes cluster.

        :param vdc: (str): The name of the vdc that contains the cluster
        :param network_name: (str): The name of the network to which the
            node VMs will connect to
        :param name: (str): The name of the cluster
        :param node_count: (str): The number of nodes
        :param cpu: (str): The number of virtual cpus on each of the
            new nodes in the cluster
        :param memory: (str): The amount of memory (in MB) on each of the new
            nodes in the cluster
        :param storage_profile: (str): The name of the storage profile which
            will back the new nodes
        :param ssh_key: (str): The ssh key that clients can use to log into the
            node vms without explicitly providing passwords
        :param template: (str): The name of the catalog template to use to
            instantiate the nodes
        :return: (json) A parsed json object describing the requested cluster.
        """
        method = 'POST'
        uri = '%s/%s/node' % (self._uri, name)
        data = {
            'name': name,
            'node_count': node_count,
            'vdc': vdc,
            'cpu': cpu,
            'memory': memory,
            'network': network_name,
            'storage_profile': storage_profile,
            'ssh_key': ssh_key,
            'template': template
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        if response.status_code == requests.codes.accepted:
            return json.loads(response.content)
        else:
            raise Exception(json.loads(response.content).get('message'))

    def delete_nodes(self, vdc, name, nodes):
        """Delete nodes from a Kubernetes cluster.

        :param vdc: (str): The name of the vdc that contains the cluster
        :param name: (str): The name of the cluster
        :param nodes: (list(str)): The list of nodes to delete
        :return: (json) A parsed json object describing the requested cluster
            operation.
        """
        method = 'DELETE'
        uri = '%s/%s/node' % (self._uri, name)
        data = {'name': name, 'vdc': vdc, 'nodes': nodes}
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        if response.status_code == requests.codes.accepted:
            return json.loads(response.content)
        else:
            raise Exception(json.loads(response.content).get('message'))
