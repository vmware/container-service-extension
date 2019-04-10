# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import requests

from container_service_extension.cluster import TYPE_NODE
from container_service_extension.exceptions import CseClientError
from container_service_extension.exceptions import VcdResponseError
from container_service_extension.utils import ERROR_UNKNOWN
from container_service_extension.utils import process_response
from container_service_extension.utils import response_to_exception


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
        return process_response(response)

    def get_clusters(self, vdc=None, org=None):
        method = 'GET'
        uri = self._uri
        params = {}
        if vdc:
            params['vdc'] = vdc
        if org:
            params['org'] = org
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None,
            params=params)
        return process_response(response)

    def get_cluster_info(self, name, vdc=None):
        method = 'GET'
        uri = '%s/%s/info' % (self._uri, name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None,
            params={'vdc': vdc} if vdc else None)
        try:
            result = process_response(response)
        except VcdResponseError as e:
            if e.error_message == ERROR_UNKNOWN:
                raise CseClientError("Invalid cluster name")
            else:
                raise e
        return result

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
                       pks_ext_host=None,
                       pks_plan=None,
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
        uri = self._uri
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
            'pks_ext_host': pks_ext_host,
            'pks_plan': pks_plan,
            'org': org
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        return process_response(response)

    def resize_cluster(self,
                       network_name,
                       cluster_name,
                       node_count=1,
                       vdc=None,
                       disable_rollback=True):
        method = 'PUT'
        uri = f"{self._uri}/{cluster_name}"
        data = {
            'name': cluster_name,
            'node_count': node_count,
            'node_type': TYPE_NODE,
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

    def delete_cluster(self, cluster_name, vdc=None):
        method = 'DELETE'
        uri = '%s/%s' % (self._uri, cluster_name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/*+json',
            params={'vdc': vdc} if vdc else None)
        try:
            result = process_response(response)
        except VcdResponseError as e:
            if e.error_message == ERROR_UNKNOWN:
                raise CseClientError("Invalid cluster/node name")
            else:
                raise e
        return result

    def get_config(self, cluster_name, vdc=None):
        method = 'GET'
        uri = '%s/%s/config' % (self._uri, cluster_name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='text/x-yaml',
            auth=None,
            params={'vdc': vdc} if vdc else None)
        if response.status_code == requests.codes.ok:
            return response.content.decode('utf-8').replace('\\n', '\n')[1:-1]
        try:
            response_to_exception(response)
        except VcdResponseError as e:
            if e.error_message == ERROR_UNKNOWN:
                raise CseClientError("Invalid cluster name")
            else:
                raise e

    def get_node_info(self, cluster_name, node_name):
        method = 'GET'
        uri = '%s/%s/%s/info' % (self._uri, cluster_name, node_name)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        try:
            result = process_response(response)
        except VcdResponseError as e:
            if e.error_message == ERROR_UNKNOWN:
                raise CseClientError("Invalid cluster/node name")
            else:
                raise e
        return result

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
                 node_type=TYPE_NODE,
                 disable_rollback=True):
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
        :param disable_rollback: (bool): Flag to control weather rollback
            should be performed or not in case of errors. True to rollback,
            False to not rollback

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
            'template': template,
            'node_type': node_type,
            'disable_rollback': disable_rollback
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        return process_response(response)

    def delete_nodes(self, vdc, name, nodes, force=False):
        """Delete nodes from a Kubernetes cluster.

        :param vdc: (str): The name of the vdc that contains the cluster
        :param name: (str): The name of the cluster
        :param nodes: (list(str)): The list of nodes to delete
        :param force: (bool): Force delete the node VM even if kubernetes fails
        :return: (json) A parsed json object describing the requested cluster
            operation.
        """
        method = 'DELETE'
        uri = '%s/%s/node' % (self._uri, name)
        data = {'name': name, 'vdc': vdc, 'nodes': nodes, 'force': force}
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        return process_response(response)
