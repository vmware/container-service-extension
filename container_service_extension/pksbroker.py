# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from http import HTTPStatus
import json

from pyvcloud.vcd.utils import extract_id
import yaml

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksConnectionError
from container_service_extension.exceptions import PksServerError
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
from container_service_extension.pksclient.rest import ApiException
from container_service_extension.server_constants import \
    CSE_PKS_DEPLOY_RIGHT_NAME
from container_service_extension.uaaclient.uaaclient import UaaClient
from container_service_extension.utils import exception_handler
from container_service_extension.utils import OK


# Delimiter to append with user id context
USER_ID_SEPARATOR = "---"
# Properties that need to be excluded from cluster info before sending
# to the client for reasons: security, too big that runs thru lines
EXCLUDE_KEYS = ['compute_profile']


class PKSBroker(AbstractBroker):
    """PKSBroker makes API calls to PKS server.

    It performs CRUD operations on Kubernetes clusters.
    """

    def __init__(self, request_headers, request_spec, pks_ctx):
        """Initialize PKS broker.

        :param dict pks_ctx: A dictionary with which should atleast have the
            following keys in it ['username', 'secret', 'host', 'port',
            'uaac_port'], 'proxy' and 'pks_compute_profile_name' are optional
            keys. Currently all callers of this method is using ovdc cache
            (subject to change) to initialize PKS broker.
        """
        super().__init__(request_headers, request_spec)
        if not pks_ctx:
            raise ValueError(
                "PKS context is required to establish connection to PKS")
        self.req_headers = request_headers
        self.req_spec = request_spec
        self.username = pks_ctx['username']
        self.secret = pks_ctx['secret']
        self.pks_host_uri = \
            f"https://{pks_ctx['host']}:{pks_ctx['port']}/v1"
        self.uaac_uri = \
            f"https://{pks_ctx['host']}:{pks_ctx['uaac_port']}"
        self.proxy_uri = f"http://{pks_ctx['proxy']}:80" \
            if pks_ctx.get('proxy') else None
        self.compute_profile = pks_ctx.get(PKS_COMPUTE_PROFILE, None)
        # TODO() Add support in pyvcloud to send metadata values with their
        # types intact.
        verify_ssl_value_in_ctx = pks_ctx.get('verify')
        if isinstance(verify_ssl_value_in_ctx, bool):
            self.verify = verify_ssl_value_in_ctx
        elif isinstance(verify_ssl_value_in_ctx, str):
            self.verify = \
                False if verify_ssl_value_in_ctx.lower() == 'false' else True
        else:
            self.verify = True
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
            raise PksConnectionError(f"Connection establishment to PKS host"
                                     f" {self.uaac_uri} failed: {err}")
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

    def list_clusters(self):
        """Get list of clusters in PKS environment.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        self.get_tenant_client_session()
        cluster_list = self._list_clusters()
        if self.tenant_client.is_sysadmin():
            for cluster in cluster_list:
                self._remove_user_id(cluster)
            return cluster_list
        else:
            user_cluster_list = [cluster_dict for cluster_dict in cluster_list
                                 if self._strip_user_id(cluster_dict)]
            return user_cluster_list

    def _list_clusters(self):
        """Get list of clusters in PKS environment.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} "
                     f"to list all clusters")
        try:
            clusters = cluster_api.list_clusters()
        except ApiException as err:
            LOGGER.debug(f"Listing PKS clusters failed with error:\n {err}")
            raise PksServerError(err.status, err.body)

        list_of_cluster_dicts = []
        for cluster in clusters:
            cluster_dict = {
                'name': cluster.name,
                'plan-name': cluster.plan_name,
                'uuid': cluster.uuid,
                'status': cluster.last_action_state,
                'last-action': cluster.last_action,
                'k8_master_ips': cluster.kubernetes_master_ips,
                'compute-profile-name': cluster.compute_profile_name,
                'worker_count': cluster.parameters.kubernetes_worker_instances
            }
            list_of_cluster_dicts.append(cluster_dict)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on the"
                     f" list of clusters: {list_of_cluster_dicts}")
        return list_of_cluster_dicts

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def create_cluster(self, **cluster_params):
        """Create cluster in PKS environment.

        :param dict cluster_params: named parameters necessary to create
        cluster (cluster_name, node_count, pks_plan, pks_ext_host, compute-
        profile_name)

        :return: Details of the cluster

        :rtype: dict
        """
        cluster_params['cluster_name'] = \
            self._append_user_id(cluster_params['cluster_name'])
        created_cluster_info = self._create_cluster(**cluster_params)
        self._remove_user_id(created_cluster_info)
        self._exclude_pks_properties(created_cluster_info)
        return created_cluster_info

    def _create_cluster(self, cluster_name, node_count, pks_plan, pks_ext_host,
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
        # TODO(ClusterSpec) Create an inner class "ClusterSpec"
        #  in abstract_broker.py and have subclasses define and use it
        #  as instance variable.
        #  Method 'Create_cluster' in VcdBroker and PksBroker should take
        #  ClusterSpec either as a param (or)
        #  read from instance variable (if needed only).

        compute_profile = compute_profile \
            if compute_profile else self.compute_profile
        cluster_api = ClusterApi(api_client=self.pks_client)
        cluster_params = \
            ClusterParameters(kubernetes_master_host=pks_ext_host,
                              kubernetes_worker_instances=node_count)
        cluster_request = ClusterRequest(name=cluster_name, plan_name=pks_plan,
                                         parameters=cluster_params,
                                         compute_profile_name=compute_profile)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to create "
                     f"cluster of name: {cluster_name}")
        try:
            cluster = cluster_api.add_cluster(cluster_request)
        except ApiException as err:
            LOGGER.debug(f"Creating cluster {cluster_name} in PKS failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)
        cluster_dict = cluster.to_dict()
        # Flattening the dictionary
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)

        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to create"
                     f" cluster: {cluster_name}")
        # TODO() access self.pks_ctx to get hold of nsxt_info and create dfw
        # rules
        return cluster_dict

    def get_cluster_info(self, cluster_name):
        """Get the details of a cluster with a given name in PKS environment.

        :param str cluster_name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        self.get_tenant_client_session()
        if self.tenant_client.is_sysadmin():
            filtered_cluster_list = \
                self._filter_list_by_cluster_name(self.list_clusters(),
                                                  cluster_name)
            LOGGER.debug(f"filtered Cluster List:{filtered_cluster_list}")
            if len(filtered_cluster_list) > 0:
                return filtered_cluster_list[0]
            else:
                raise PksServerError(HTTPStatus.NOT_FOUND,
                                     f"cluster {cluster_name} not found")
        else:
            cluster_info = \
                self._get_cluster_info(self._append_user_id(cluster_name))
            self._remove_user_id(cluster_info)
            return cluster_info

    def _get_cluster_info(self, cluster_name):
        """Get the details of a cluster with a given name in PKS environment.

        :param str cluster_name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to get "
                     f"details of cluster with name: {cluster_name}")
        try:
            cluster = cluster_api.get_cluster(cluster_name=cluster_name)
        except ApiException as err:
            LOGGER.debug(f"Getting cluster info on {cluster_name} failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)
        cluster_dict = cluster.to_dict()
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on "
                     f"cluster: {cluster_name} with details: {cluster_dict}")

        return cluster_dict

    def get_cluster_config(self, cluster_name):
        """Get the configuration of the cluster with the given name in PKS.

        :param str cluster_name: Name of the cluster
        :return: Configuration of the cluster.

        :rtype: str
        """
        self.get_tenant_client_session()
        if self.tenant_client.is_sysadmin():
            cluster = self.get_cluster_info(cluster_name)
            return self._get_cluster_config(cluster['pks_cluster_name'])
        else:
            pks_cluster_name = self._append_user_id(cluster_name)
            return self._get_cluster_config(pks_cluster_name)

    def _get_cluster_config(self, cluster_name):
        """Get the configuration of the cluster with the given name in PKS.

        :param str cluster_name: Name of the cluster
        :return: Configuration of the cluster.

        :rtype: str
        """
        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to get"
                     f" detailed configuration of cluster with name: "
                     f"{cluster_name}")
        config = cluster_api.create_user(cluster_name=cluster_name)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on "
                     f"cluster: {cluster_name} with details: {config}")
        cluster_config = yaml.safe_dump(config, default_flow_style=False)
        return cluster_config

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def delete_cluster(self, cluster_name):
        """Delete the cluster with a given name in PKS environment.

        :param str cluster_name: Name of the cluster
        """
        self.get_tenant_client_session()
        LOGGER.debug(f"Delete Cluster:{cluster_name}")
        if self.tenant_client.is_sysadmin():
            cluster_info = self.get_cluster_info(cluster_name)
            return self._delete_cluster(cluster_info['pks_cluster_name'])

        else:
            pks_cluster_name = self._append_user_id(cluster_name)
            return self._delete_cluster(pks_cluster_name)

    def _delete_cluster(self, cluster_name):
        """Delete the cluster with a given name in PKS environment.

        :param str cluster_name: Name of the cluster
        """
        result = {}

        cluster_api = ClusterApi(api_client=self.pks_client)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to delete "
                     f"the cluster with name: {cluster_name}")
        try:
            cluster_api.delete_cluster(cluster_name=cluster_name)
        except ApiException as err:
            LOGGER.debug(f"Deleting cluster {cluster_name} failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)

        # TODO() access self.pks_ctx and get hold of nst_info to cleanup dfw
        # rules
        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to delete"
                     f" the cluster: {cluster_name}")

        result = {}
        result['cluster_name'] = cluster_name
        result['task_status'] = 'in progress'
        return result

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def resize_cluster(self, **cluster_params):
        """Resize the cluster of a given name to given number of worker nodes.

        :param dict cluster_params: named parameters that are required to
        resize cluster (cluster_name, node_count)

        :return: response status

        :rtype: dict

        """
        self.get_tenant_client_session()
        cluster_name = cluster_params['cluster_name']
        LOGGER.debug(f"Resize Cluster:{cluster_name}")
        if self.tenant_client.is_sysadmin():
            cluster = self.get_cluster_info(cluster_name)
            cluster_params['cluster_name'] = cluster['pks_cluster_name']
            return self._resize_cluster(**cluster_params)
        else:
            pks_cluster_name = self._append_user_id(cluster_name)
            cluster_params['cluster_name'] = pks_cluster_name
            return self._resize_cluster(**cluster_params)

    def _resize_cluster(self, cluster_name, node_count, **kwargs):
        """Resize the cluster of a given name to given number of worker nodes.

        :param str cluster_name: Name of the cluster
        :param int node_count: New size of the worker nodes
        """
        result = {}
        cluster_api = ClusterApi(api_client=self.pks_client)
        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to resize "
                     f"the cluster with name: {cluster_name} to "
                     f"{node_count} worker nodes")

        resize_params = UpdateClusterParameters(
            kubernetes_worker_instances=node_count)
        try:
            cluster_api.update_cluster(cluster_name, body=resize_params)
        except ApiException as err:
            LOGGER.debug(f"Resizing cluster {cluster_name} failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to resize"
                     f" the cluster: {cluster_name}")

        result['cluster_name'] = cluster_name
        result['task_status'] = 'in progress'

        return result

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

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to create "
                     f"the compute profile: {cp_name} for ovdc {ovdc_rp_name}")
        try:
            profile_api.add_compute_profile(body=cp_request)
        except ApiException as err:
            LOGGER.debug(f"Creating compute-profile {cp_name} in PKS failed "
                         f"with error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"PKS: {self.pks_host_uri} created the compute profile: "
                     f"{cp_name} for ovdc {ovdc_rp_name}")
        return result

    @exception_handler
    def get_compute_profile(self, cp_name):
        """Get the details of compute profile.

        :param str cp_name: Name of the compute profile
        :return: Details of the compute profile as body of the result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        profile_api = ProfileApi(api_client=self.pks_client)

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to get the "
                     f"compute profile: {cp_name}")

        try:
            compute_profile = \
                profile_api.get_compute_profile(profile_name=cp_name)
        except ApiException as err:
            LOGGER.debug(f"Creating compute-profile {cp_name} in PKS failed "
                         f"with error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on "
                     f"compute-profile: {cp_name} with details: "
                     f"{compute_profile.to_dict()}")

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

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to get the "
                     f"list of compute profiles")
        try:
            cp_list = profile_api.list_compute_profiles()
        except ApiException as err:
            LOGGER.debug(f"Listing compute-profiles in PKS failed "
                         f"with error:\n {err}")
            raise PksServerError(err.status, err.body)

        list_of_cp_dicts = [cp.to_dict() for cp in cp_list]
        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on "
                     f"list of compute profiles: {list_of_cp_dicts}")

        result['body'] = list_of_cp_dicts
        return result

    @exception_handler
    def delete_compute_profile(self, cp_name):
        """Delete the compute profile with a given name.

        :param str cp_name: Name of the compute profile
        :return: result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        profile_api = ProfileApi(api_client=self.pks_client)

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to delete "
                     f"the compute profile: {cp_name}")

        try:
            profile_api.delete_compute_profile(profile_name=cp_name)
        except ApiException as err:
            LOGGER.debug(f"Deleting compute-profile {cp_name} in PKS failed "
                         f"with error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} that"
                     f" it deleted the compute profile: {cp_name}")

        return result

    def _append_user_id(self, name):
        user_id = self._get_session_userid()
        return f"{name}{USER_ID_SEPARATOR}{user_id}"

    def _remove_user_id(self, cluster_info):
        cluster_info['pks_cluster_name'] = cluster_info['name']
        name_info = cluster_info['name'].split(USER_ID_SEPARATOR)
        cluster_info['name'] = name_info[0]

    def _strip_user_id(self, cluster_info):
        # NOTE: Current implementation works only if the method
        # argument is a dict item. Any change in the requirement needs
        # this logic to be revisited

        is_user_id_stripped = False

        if type(cluster_info) is not dict:
            return is_user_id_stripped

        user_id = self._get_session_userid()

        # Process every value from the cluster information
        # Return true if any stripping happened
        for key, val in cluster_info.items():
            if type(val) is str and user_id in val:
                cluster_info.update(
                    {key: val.replace(f'{USER_ID_SEPARATOR}{user_id}', '')})
                is_user_id_stripped = True

        return is_user_id_stripped

    def _get_session_userid(self):
        session = self.get_tenant_client_session()
        return extract_id(session.get('userId'))

    def _filter_list_by_cluster_name(self, cluster_list, cluster_name):
        return [cluster for cluster in cluster_list
                if cluster['name'] == cluster_name]

    def _exclude_pks_properties(self, cluster_info):
        for entry in EXCLUDE_KEYS:
            cluster_info.pop(entry, None)

    def __getattr__(self, name):
        """Handle unknown operations.

        Example: This broker does
        not support individual node operations.
        """
        def unsupported_method(*args):
            raise CseServerError(f"Unsupported operation {name}")
        return unsupported_method
