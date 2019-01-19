# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pksclient.api_client import ApiClient
from container_service_extension.pksclient.api.cluster_api import ClusterApi
from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pksclient.models.cluster_parameters import ClusterParameters
from container_service_extension.pksclient.models.cluster_request import ClusterRequest
from container_service_extension.pksclient.models.update_cluster_parameters import UpdateClusterParameters
from container_service_extension.uaaclient.uaaclient import UaaClient
from container_service_extension.utils import exception_handler
from container_service_extension.utils import ACCEPTED
from container_service_extension.utils import OK


class PKSBroker(object):
    """PKSBroker makes appropriate API calls to PKS server to perform CRUD
    operations on Kubernetes clusters.
    """
    def __init__(self, ovdc_cache=None):
        """Initializes PKS broker

        :param ovdc_cache: ovdc cache (subject to change) is used to initialize PKS broker
        """
        self.host = 'api.pks.local'
        self.port = 9021
        self.username = 'admin'
        self.secret = 'YtAU6Rl2dEvj1_hH9wEQxDUkxO1Lcjm3'
        self.proxy = '10.161.148.112'
        self.pks_host_uri = f'https://{self.host}:{self.port}/v1'
        self.uaac_port = 8443
        self.uaac_uri = f'https://{self.host}:{self.uaac_port}'
        self.proxy_uri = f'http://{self.proxy}:80'
        self.verify = False #TODO pks_config['pks']['verify']
        self.pks_client = self._get_pks_client()

    def _get_pks_config(self):
        """Connects to UAA server and constructs PKS configuration.
        (PKS configuration is required to construct pksclient: container_service_extension.pksclient.api_client.ApiClient)

        :return: PKS configuration

        :rtype: container_service_extension.pksclient.configuration.Configuration
        """
        uaaClient = UaaClient(self.uaac_uri, self.username, self.secret)
        token = uaaClient.getToken()
        pks_config = Configuration()
        pks_config.proxy = self.proxy_uri
        pks_config.host = self.pks_host_uri
        pks_config.access_token = token
        pks_config.username = self.username
        pks_config.verify_ssl = self.verify
        return pks_config

    def _get_pks_client(self):
        """Gets PKS client

        :return: PKS client

        :rtype: container_service_extension.pksclient.api_client.ApiClient
        """
        pks_config = self._get_pks_config()
        self.pks_client = ApiClient(configuration=pks_config)
        return self.pks_client

    @exception_handler
    def list_clusters(self):
        """Gets list of clusters ((TODO)for a given vCD user) in PKS environment.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        cluster_api = ClusterApi(api_client=self.pks_client)
        LOGGER.debug('Sending request to PKS: %s to list all clusters', self.host)
        clusters = cluster_api.list_clusters()
        list_of_cluster_dicts = []
        for cluster in clusters:
            cluster_dict = {
                'name': cluster.name,
                'plan-name': cluster.plan_name,
                'uuid': cluster.uuid,
                'status': cluster.last_action_state,
                'last-action': cluster.last_action,
                'k8_master_ips': cluster.kubernetes_master_ips
            }
            list_of_cluster_dicts.append(cluster_dict)
        LOGGER.debug('Received response from PKS: %s on list of clusters: %s', self.host, list_of_cluster_dicts)
        result['body'] = list_of_cluster_dicts
        return result

    @exception_handler
    def create_cluster(self, name, plan, external_host_name='cluster.pks.local', network_profile=None):
        """Creates cluster in PKS environment

        :param str name: Name of the cluster
        :param str plan: PKS plan. It should be one of {Plan 1, Plan 2, Plan 3} that PKS supports.
        :param str external_host_name: User-preferred external hostname of the K8 cluster
        :param container_service_extension.pksclient.models.network_profile.NetworkProfile network_profile: Network profile params for the cluster to be deployed.
        :return: Details of the cluster.

        :rtype: dict
        """
        # Note: Do not accept cluster names with '-'. Validate this in cse client.
        result = {}
        result['body'] = []
        cluster_api = ClusterApi(api_client=self.pks_client)
        cluster_params = ClusterParameters(kubernetes_master_host=external_host_name, nsxt_network_profile=network_profile)
        cluster_request = ClusterRequest(name=name, plan_name=plan, parameters=cluster_params)
        LOGGER.debug('Sending request to PKS: %s to create cluster of name: %s', self.host, name)
        cluster = cluster_api.add_cluster(cluster_request)
        cluster_dict = cluster.to_dict()
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)
        LOGGER.debug('PKS: %s accepted the request to create cluster: %s', self.host, name)
        result['body'] = cluster_dict
        result['status_code'] = ACCEPTED
        return result

    @exception_handler
    def get_cluster_info(self, name):
        """Gets the details of a cluster with a given name in PKS environment.

        :param str name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        cluster_api = ClusterApi(api_client=self.pks_client)
        LOGGER.debug('Sending request to PKS: %s to get details of cluster with name: %s', self.host, name)
        cluster = cluster_api.get_cluster(cluster_name=name)
        cluster_dict = cluster.to_dict()
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)
        LOGGER.debug('Received response from PKS: %s on cluster %s details: %s', self.host, name, cluster_dict)
        result['body'] = cluster_dict
        print(cluster_dict)
        return result

    @exception_handler
    def delete_cluster(self, name):
        """Deletes the cluster with a given name in PKS environment.

        :param str name: Name of the cluster
        :return: None
        """
        result = {}
        result['body'] = []
        cluster_api = ClusterApi(api_client=self.pks_client)
        LOGGER.debug('Sending request to PKS: %s to delete the cluster with name: %s', self.host, name)
        cluster_api.delete_cluster(cluster_name=name)
        LOGGER.debug('PKS: %s accepted the request to delete the cluster: %s', self.host, name)
        result['status_code'] = ACCEPTED
        return result

    @exception_handler
    def resize_cluster(self, name, num_worker_nodes):
        """Resizes the cluster of a given name to given number of worker nodes.

        :param str name: Name of the cluster
        :param int num_worker_nodes: New size of the worker nodes
        (should be greater than the current number).
        :return: None
        """
        result = {}
        result['body'] = []
        cluster_api = ClusterApi(api_client=self.pks_client)
        LOGGER.debug('Sending request to PKS: %s to resize the cluster with name: %s to %s worker nodes', self.host, name, num_worker_nodes)
        resize_params = UpdateClusterParameters(kubernetes_worker_instances=num_worker_nodes)
        cluster_api.update_cluster(name, body=resize_params)
        LOGGER.debug('PKS: %s accepted the request to resize the cluster: %s', self.host, name)
        result['status_code'] = ACCEPTED
        return result




p = PKSBroker(ovdc_cache=None)
#p.create_cluster('k8s6','Plan 1')
#p.get_cluster_info('k8s1')
#print(p.list_clusters())
p.resize_cluster('k8s3',4)

#p.get_cluster_info('k8s3')
#p.delete_cluster('k8s4')


