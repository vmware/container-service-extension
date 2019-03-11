# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import json

from pyvcloud.vcd.utils import extract_id

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.exceptions import PksConnectionError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pks_cache import PKS_COMPUTE_PROFILE
from container_service_extension.pksclient.api.cluster_api import ClusterApi
from container_service_extension.pksclient.api.profile_api import ProfileApi
from container_service_extension.pksclient.api_client import ApiClient
from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pksclient.models.cluster_parameters\
    import ClusterParameters
from container_service_extension.pksclient.models.cluster_request \
    import ClusterRequest
from container_service_extension.pksclient.models.compute_profile_request \
    import ComputeProfileRequest
from container_service_extension.pksclient.models.update_cluster_parameters\
    import UpdateClusterParameters
from container_service_extension.uaaclient.uaaclient import UaaClient
from container_service_extension.utils import exception_handler
from container_service_extension.utils import OK


def add_vcd_user_context(**decorator_args):
    """Decorate to add unique user id to cluster name.

    Process the response from PKS to filter the cluster names that belong to
    the user. Customized to work for CRUD on pks k8s.

    :param dict decorator_args: arguments that signify if custom processing
    of results returned by decorated function.

    :return: results from the decorated function after post processing
    """
    def decorator(pks_function):
        @functools.wraps(pks_function)
        def wrapper(*args, **kwargs):

            def get_unique_id():
                # Return user id associated with client-session
                broker_instance = args[0]
                session = broker_instance.get_tenant_client_session()
                return extract_id(session.get('userId'))

            def replace_unique_id(cluster_dict):
                # Remove the user id associated with client-session
                if type(cluster_dict) is not dict:
                    return
                # Process every value from the cluster information
                for k, v in cluster_dict.items():
                    if type(v) is str:
                        cluster_dict.update({k: v.replace(unique_id, '')})

            def has_unique_id(cluster_dict):
                # Checks if any of the dict value has unique user id
                # Return upon any first value that has user id
                for val in cluster_dict.values():
                    if unique_id in val:
                        return True
                return False

            def pre_process_cluster_name(k):
                # Append unique id to the key
                if k in kwargs:
                    kwargs[k] += unique_id

            unique_id = get_unique_id()
            # Process the cluster name which may come as 'cluster_name' or
            # 'name'
            pre_process_cluster_name('cluster_name')
            pre_process_cluster_name('name')
            result = pks_function(*args, **kwargs)

            # Check decorator argument for any special post processing of
            # result
            if decorator_args.get('filter_list'):
                filtered_list = [cluster_dict for cluster_dict in result
                                 if has_unique_id(cluster_dict)]
                for cluster_dict in filtered_list:
                    replace_unique_id(cluster_dict)
                return filtered_list

            replace_unique_id(result)
            return result
        return wrapper
    return decorator


class PKSBroker(AbstractBroker):
    """PKSBroker makes API calls to PKS server.

    It performs CRUD operations on Kubernetes clusters.
    """

    def __init__(self, headers, request_body, pks_ctx=None):
        """Initialize PKS broker.

        :param pks_ctx: ovdc cache (subject to change) is used to
        initialize PKS broker.
        """
        super().__init__(headers, request_body)
        self.headers = headers
        self.body = request_body
        self.username = pks_ctx['username']
        self.secret = pks_ctx['secret']
        self.pks_host_uri = \
            f"https://{pks_ctx['host']}:{pks_ctx['port']}/v1"
        self.uaac_uri = \
            f"https://{pks_ctx['host']}:{pks_ctx['uaac_port']}"
        self.proxy_uri = f"http://{pks_ctx['proxy']}:80" \
            if pks_ctx.get('proxy') else None
        self.compute_profile = pks_ctx.get(PKS_COMPUTE_PROFILE, None)
        self.verify = False  # TODO(pks.yaml) pks_config['pks']['verify']
        self.pks_client = self._get_pks_client()
        self.client_session = None

    def _get_pks_config(self):
        """Connect to UAA server and construct PKS configuration.

        (PKS configuration is required to construct pksclient)

        :return: PKS configuration

        :rtype:
        container_service_extension.pksclient.configuration.Configuration
        """
        try:
            uaaClient = UaaClient(self.uaac_uri, self.username, self.secret,
                                  proxy_uri=self.proxy_uri)
            token = uaaClient.getToken()
        except Exception as err:
            raise PksConnectionError(f'Connection establishment to PKS host'
                                     f' {self.uaac_uri} failed: {err}')
        pks_config = Configuration()
        pks_config.proxy = self.proxy_uri
        pks_config.host = self.pks_host_uri
        pks_config.access_token = token
        pks_config.username = self.username
        pks_config.verify_ssl = self.verify

        return pks_config

    def _get_pks_client(self):
        """Get PKS client.

        :return: PKS client

        :rtype: container_service_extension.pksclient.api_client.ApiClient
        """
        pks_config = self._get_pks_config()
        self.pks_client = ApiClient(configuration=pks_config)
        return self.pks_client

    @add_vcd_user_context(filter_list=True)
    def list_clusters(self):
        """Get list of clusters ((TODO)for a given vCD user) in PKS environment.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS: {self.pks_host_uri} '
                     f'to list all clusters')

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

        LOGGER.debug(f'Received response from PKS: {self.pks_host_uri} on the'
                     f' list of clusters: {list_of_cluster_dicts}')
        return list_of_cluster_dicts

    @add_vcd_user_context()
    def create_cluster(self, cluster_name, node_count, pks_plan, pks_ext_host,
                       compute_profile=None, **kwargs):
        """Create cluster in PKS environment.

        :param str cluster_name: Name of the cluster
        :param str plan: PKS plan. It should be one of the three plans
        that PKS supports.
        :param str external_host_name: User-preferred external hostname
         of the K8 cluster
        :param str compute_profile: Name of the compute profile

        :return: Details of the cluster

        :rtype: dict
        """
        # TODO(ClusterParams) Create an inner class "ClusterParams"
        #  in abstract_broker.py and have subclasses define and use it
        #  as instance variable.
        #  Method 'Create_cluster' in VcdBroker and PksBroker should take
        #  ClusterParams either as a param (or)
        #  read from instance variable (if needed only).

        # TODO() Invalidate cluster names containing '-' character.

        compute_profile = compute_profile \
            if compute_profile else self.compute_profile
        cluster_api = ClusterApi(api_client=self.pks_client)
        cluster_params = \
            ClusterParameters(kubernetes_master_host=pks_ext_host,
                              kubernetes_worker_instances=node_count)
        cluster_request = ClusterRequest(name=cluster_name, plan_name=pks_plan,
                                         parameters=cluster_params,
                                         compute_profile_name=compute_profile)

        LOGGER.debug(f'Sending request to PKS: {self.pks_host_uri} to create '
                     f'cluster of name: {cluster_name}')

        cluster = cluster_api.add_cluster(cluster_request)
        cluster_dict = cluster.to_dict()
        # Flattening the dictionary
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)

        LOGGER.debug(f'PKS: {self.pks_host_uri} accepted the request to create'
                     f' cluster: {cluster_name}')
        return cluster_dict

    @add_vcd_user_context()
    def get_cluster_info(self, name):
        """Get the details of a cluster with a given name in PKS environment.

        :param str name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS: {self.pks_host_uri} to get '
                     f'details of cluster with name: {name}')

        cluster = cluster_api.get_cluster(cluster_name=name)
        cluster_dict = cluster.to_dict()
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)

        LOGGER.debug(f'Received response from PKS: {self.pks_host_uri} on '
                     f'cluster: {name} with details: {cluster_dict}')

        return cluster_dict

    @add_vcd_user_context()
    def delete_cluster(self, name):
        """Delete the cluster with a given name in PKS environment.

        :param str name: Name of the cluster
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS: {self.pks_host_uri} to delete '
                     f'the cluster with name: {name}')

        cluster_api.delete_cluster(cluster_name=name)

        LOGGER.debug(f'PKS: {self.pks_host_uri} accepted the request to delete'
                     f' the cluster: {name}')
        return

    @exception_handler
    @add_vcd_user_context()
    def resize_cluster(self, name, num_worker_nodes):
        """Resize the cluster of a given name to given number of worker nodes.

        :param str name: Name of the cluster
        :param int num_worker_nodes: New size of the worker nodes
        (should be greater than the current number).
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS:{self.pks_host_uri} to resize '
                     f'the cluster with name: {name} to '
                     f'{num_worker_nodes} worker nodes')

        resize_params = UpdateClusterParameters(
            kubernetes_worker_instances=num_worker_nodes)
        cluster_api.update_cluster(name, body=resize_params)

        LOGGER.debug(f'PKS: {self.pks_host_uri} accepted the request to resize'
                     f' the cluster: {name}')
        return

    @exception_handler
    def create_compute_profile(self, cp_name, az_name, description, cpi,
                               datacenter_name, cluster_name, ovdc_rp_name):
        """Create a PKS compute profile that maps to a given oVdc in vCD.

        :param str cp_name: Name of the compute profile
        :param str az_name: Name of the PKS availability zone to be defined
        :param str description: Description of the compute profile
        :param str cpi: Unique identifier provided by BOSH
        :param str datacenter_name: Name of the datacenter
        :param str cluster_name: Name of the cluster
        :param str ovdc_rp_name: Name of the oVdc resource pool

        :return: result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        profile_api = ProfileApi(api_client=self.pks_client)

        resource_pool = {
            'resource_pool': ovdc_rp_name
        }

        cloud_properties = {
            'datacenters': [
                {
                    'name': datacenter_name,
                    'clusters': [
                        {
                            cluster_name: resource_pool
                        }
                    ]
                }
            ]
        }

        az_params = {
            'azs': [
                {
                    'name': az_name,
                    'cpi': cpi,
                    'cloud_properties': cloud_properties
                }

            ]
        }

        cp_params_json_str = json.dumps(az_params)
        cp_request = ComputeProfileRequest(name=cp_name,
                                           description=description,
                                           parameters=cp_params_json_str)

        LOGGER.debug(f'Sending request to PKS:{self.pks_host_uri} to create '
                     f'the compute profile: {cp_name} for ovdc {ovdc_rp_name}')

        profile_api.add_compute_profile(body=cp_request)

        LOGGER.debug(f'PKS: {self.pks_host_uri} created the compute profile: '
                     f'{cp_name} for ovdc {ovdc_rp_name}')
        return result

    @exception_handler
    def get_compute_profile(self, name):
        """Get the details of compute profile.

        :param str name: Name of the compute profile
        :return: Details of the compute profile as body of the result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        profile_api = ProfileApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS:{self.pks_host_uri} to get the '
                     f'compute profile: {name} ')

        compute_profile = profile_api.get_compute_profile(profile_name=name)

        LOGGER.debug(f'Received response from PKS: {self.pks_host_uri} on '
                     f'compute-profile: {name} with details: '
                     f'{compute_profile.to_dict()}')

        result['body'] = compute_profile.to_dict()
        return result

    @exception_handler
    def list_compute_profiles(self):
        """Get the list of compute profiles.

        :return: List of compute profile details as body of the result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        profile_api = ProfileApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS:{self.pks_host_uri} to get the '
                     f'list of compute profiles')

        cp_list = profile_api.list_compute_profiles()
        list_of_cp_dicts = [cp.to_dict() for cp in cp_list]

        LOGGER.debug(f'Received response from PKS: {self.pks_host_uri} on '
                     f'list of compute profiles: {list_of_cp_dicts}')

        result['body'] = list_of_cp_dicts
        return result

    @exception_handler
    def delete_compute_profile(self, name):
        """Delete the compute profile with a given name.

        :param str name: Name of the compute profile
        :return: result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        profile_api = ProfileApi(api_client=self.pks_client)

        LOGGER.debug(f'Sending request to PKS:{self.pks_host_uri} to delete '
                     f'the compute profile: {name}')

        profile_api.delete_compute_profile(profile_name=name)

        LOGGER.debug(f'Received response from PKS: {self.pks_host_uri} that'
                     f' it deleted the compute profile: {name}')

        return result
