# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.response_processor import process_response # noqa: E501
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RequestMethod


class Cluster:
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def get_templates(self):
        method = RequestMethod.GET
        uri = f"{self._uri}/templates"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)

    def get_clusters(self, vdc=None, org=None):
        method = RequestMethod.GET
        uri = f"{self._uri}/clusters"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_cluster_info(self, name, org=None, vdc=None):
        method = RequestMethod.GET
        uri = f'{self._uri}/cluster/{name}'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        method = RequestMethod.GET
        uri = f'{self._uri}/cluster/{cluster_name}/upgrade-plan'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def upgrade_cluster(self, cluster_name, template_name, template_revision,
                        org_name=None, ovdc_name=None):
        method = RequestMethod.POST
        uri = f'{self._uri}/cluster/{cluster_name}/action/upgrade'
        data = {
            RequestKey.CLUSTER_NAME: cluster_name,
            RequestKey.TEMPLATE_NAME: template_name,
            RequestKey.TEMPLATE_REVISION: template_revision,
            RequestKey.ORG_NAME: org_name,
            RequestKey.OVDC_NAME: ovdc_name,
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def create_cluster(self,
                       vdc,
                       network_name,
                       name,
                       node_count=None,
                       cpu=None,
                       memory=None,
                       storage_profile=None,
                       ssh_key=None,
                       template_name=None,
                       template_revision=None,
                       enable_nfs=False,
                       rollback=True,
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
        :param template_name: (str): The name of the template to use to
            instantiate the nodes
        :param template_revision: (str): The revision of the template to use to
            instantiate the nodes
        :param enable_nfs: (bool): bool value to indicate if NFS node is to be
            created
        :param rollback: (bool): Flag to control weather rollback
            should be performed or not in case of errors.
        :param pks_ext_host: (str): Address from which to access the Kubernetes
        API for PKS.
        :param pks_plan: (str): Preconfigured PKS plan to use for deploying the
        cluster.
        :param org: (str): name of the organization in which the vdc to be
        used for cluster creation.

        :return: (json) A parsed json object describing the requested cluster.
        """
        method = RequestMethod.POST
        uri = f"{self._uri}/clusters"
        data = {
            RequestKey.CLUSTER_NAME: name,
            RequestKey.NUM_WORKERS: node_count,
            RequestKey.OVDC_NAME: vdc,
            RequestKey.NUM_CPU: cpu,
            RequestKey.MB_MEMORY: memory,
            RequestKey.NETWORK_NAME: network_name,
            RequestKey.STORAGE_PROFILE_NAME: storage_profile,
            RequestKey.SSH_KEY: ssh_key,
            RequestKey.TEMPLATE_NAME: template_name,
            RequestKey.TEMPLATE_REVISION: template_revision,
            RequestKey.ENABLE_NFS: enable_nfs,
            RequestKey.ROLLBACK: rollback,
            RequestKey.ORG_NAME: org
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
                       rollback=True,
                       template_name=None,
                       template_revision=None):
        method = RequestMethod.PUT
        uri = f"{self._uri}/cluster/{cluster_name}"
        data = {
            RequestKey.CLUSTER_NAME: cluster_name,
            RequestKey.NUM_WORKERS: node_count,
            RequestKey.ORG_NAME: org,
            RequestKey.OVDC_NAME: vdc,
            RequestKey.NETWORK_NAME: network_name,
            RequestKey.ROLLBACK: rollback,
            RequestKey.TEMPLATE_NAME: template_name,
            RequestKey.TEMPLATE_REVISION: template_revision,
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
        method = RequestMethod.DELETE
        uri = f"{self._uri}/cluster/{cluster_name}"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})
        return process_response(response)

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        method = RequestMethod.GET
        uri = f"{self._uri}/cluster/{cluster_name}/config"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.ORG_NAME: org, RequestKey.OVDC_NAME: vdc})

        return process_response(response)

    def get_node_info(self, cluster_name, node_name, org=None, vdc=None):
        method = RequestMethod.GET
        uri = f"{self._uri}/node/{node_name}"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={
                RequestKey.ORG_NAME: org,
                RequestKey.OVDC_NAME: vdc,
                RequestKey.CLUSTER_NAME: cluster_name
            })
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
                 template_name=None,
                 template_revision=None,
                 enable_nfs=False,
                 rollback=True):
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
        :param template_name: (str): The name of the catalog template to use to
            instantiate the nodes
        :param template_revision: (str): The revision of the template to use to
            instantiate the nodes
        :param enable_nfs: (bool): Flag to enable NFS software on worker nodes
        :param rollback: (bool): Flag to control whether rollback
            should be performed or not in case of errors.

        :return: (json) A parsed json object describing the requested cluster.
        """
        method = RequestMethod.POST
        uri = f'{self._uri}/nodes'
        data = {
            RequestKey.CLUSTER_NAME: cluster_name,
            RequestKey.NUM_WORKERS: node_count,
            RequestKey.ORG_NAME: org,
            RequestKey.OVDC_NAME: vdc,
            RequestKey.NUM_CPU: cpu,
            RequestKey.MB_MEMORY: memory,
            RequestKey.NETWORK_NAME: network_name,
            RequestKey.STORAGE_PROFILE_NAME: storage_profile,
            RequestKey.SSH_KEY: ssh_key,
            RequestKey.TEMPLATE_NAME: template_name,
            RequestKey.TEMPLATE_REVISION: template_revision,
            RequestKey.ENABLE_NFS: enable_nfs,
            RequestKey.ROLLBACK: rollback
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def delete_nodes(self, cluster_name, nodes, org=None, vdc=None):
        """Delete nodes from a Kubernetes cluster.

        :param org: (str): Name of the organization that contains the cluster
        :param vdc: (str): The name of the vdc that contains the cluster
        :param name: (str): The name of the cluster
        :param nodes: (list(str)): The list of nodes to delete
        :return: (json) A parsed json object describing the requested cluster
            operation.
        """
        method = RequestMethod.DELETE
        uri = f"{self._uri}/nodes"
        data = {
            RequestKey.CLUSTER_NAME: cluster_name,
            RequestKey.ORG_NAME: org,
            RequestKey.OVDC_NAME: vdc,
            RequestKey.NODE_NAMES_LIST: nodes
        }
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)
