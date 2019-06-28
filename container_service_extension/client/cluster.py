# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import requests

from container_service_extension.client.response_processor import \
    process_response
from container_service_extension.client.response_processor import \
    response_to_exception
from container_service_extension.cluster import TYPE_NODE


class Cluster(object):
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def get_templates(self):
        method = 'GET'
        uri = f"{self._uri}/templates"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)

    def get_clusters(self, vdc=None, org=None):
        method = 'GET'
        uri = f"{self._uri}/clusters"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={'org': org, 'vdc': vdc})
        return process_response(response)

    def get_cluster_info(self, name, org=None, vdc=None):
        method = 'GET'
        uri = f'{self._uri}/cluster/{name}'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={'org': org, 'vdc': vdc})
        return process_response(response)

    def create_cluster(self,
                       vdc,
                       network_name,
                       name,
                       node_count=2,
                       cpu=None,
                       memory=None,
                       storage_profile=None,
                       ssh_key=None,
                       template=None,
                       enable_nfs=False,
                       disable_rollback=True,
                       org=None):
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
        :param enable_nfs: (bool): bool value to indicate if NFS node is to be
            created
        :param disable_rollback: (bool): Flag to control weather rollback
            should be performed or not in case of errors. True to rollback,
            False to not rollback
        :param pks_ext_host: (str): Address from which to access the Kubernetes
        API for PKS.
        :param pks_plan: (str): Preconfigured PKS plan to use for deploying the
        cluster.
        :param org: (str): name of the organization in which the vdc to be
        used for cluster creation.

        :return: (json) A parsed json object describing the requested cluster.
        """
        method = 'POST'
        uri = f"{self._uri}/clusters"
        data = {
            'cluster_name': name,
            'node_count': node_count,
            'vdc': vdc,
            'cpu': cpu,
            'memory': memory,
            'network': network_name,
            'storage_profile': storage_profile,
            'ssh_key': ssh_key,
            'template': template,
            'enable_nfs': enable_nfs,
            'disable_rollback': disable_rollback,
            'org': org
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def resize_cluster(self,
                       network_name,
                       cluster_name,
                       node_count,
                       org=None,
                       vdc=None,
                       disable_rollback=True):
        method = 'PUT'
        uri = f"{self._uri}/cluster/{cluster_name}"
        data = {
            'name': cluster_name,
            'node_count': node_count,
            'node_type': TYPE_NODE,
            'org': org,
            'vdc': vdc,
            'network': network_name,
            'disable_rollback': disable_rollback
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        method = 'DELETE'
        uri = f"{self._uri}/cluster/{cluster_name}"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={'org': org, 'vdc': vdc})
        return process_response(response)

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        method = 'GET'
        uri = f"{self._uri}/cluster/{cluster_name}/config"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='text/x-yaml',
            params={'org': org, 'vdc': vdc})
        if response.status_code == requests.codes.ok:
            return response.content.decode('utf-8').replace('\\n', '\n')[1:-1]
        else:
            response_to_exception(response)

    def get_node_info(self, cluster_name, node_name, org=None, vdc=None):
        method = 'GET'
        uri = f"{self._uri}/node/{node_name}"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={'org': org, 'vdc': vdc, 'cluster_name': cluster_name})
        return process_response(response)

    def add_node(self,
                 network_name,
                 cluster_name,
                 node_count=1,
                 org=None,
                 vdc=None,
                 cpu=None,
                 memory=None,
                 storage_profile=None,
                 ssh_key=None,
                 template=None,
                 node_type=TYPE_NODE,
                 disable_rollback=True):
        """Add nodes to a Kubernetes cluster.

        :param org: (str): The name of the org that contains the cluster
        :param vdc: (str): The name of the vdc that contains the cluster
        :param network_name: (str): The name of the network to which the
            node VMs will connect to
        :param cluster_name: (str): The name of the cluster
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
        :param disable_rollback: (bool): Flag to control weather rollback
            should be performed or not in case of errors. True to rollback,
            False to not rollback

        :return: (json) A parsed json object describing the requested cluster.
        """
        method = 'POST'
        uri = f'{self._uri}/nodes'
        data = {
            'cluster_name': cluster_name,
            'node_count': node_count,
            'org': org,
            'vdc': vdc,
            'cpu': cpu,
            'memory': memory,
            'network': network_name,
            'storage_profile': storage_profile,
            'ssh_key': ssh_key,
            'template': template,
            'node_type': node_type,
            'disable_rollback': disable_rollback
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def delete_nodes(self, cluster_name, nodes, org=None, vdc=None,
                     force=False):
        """Delete nodes from a Kubernetes cluster.

        :param org: (str): Name of the organization that contains the cluster
        :param vdc: (str): The name of the vdc that contains the cluster
        :param name: (str): The name of the cluster
        :param nodes: (list(str)): The list of nodes to delete
        :param force: (bool): Force delete the node VM even if kubernetes fails
        :return: (json) A parsed json object describing the requested cluster
            operation.
        """
        method = 'DELETE'
        uri = f"{self._uri}/nodes"
        data = {'cluster_name': cluster_name, 'org': org, 'vdc': vdc,
                'nodes': nodes, 'force': force}
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)
