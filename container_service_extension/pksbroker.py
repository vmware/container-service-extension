# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from http import HTTPStatus
import re

from pyvcloud.vcd.utils import extract_id
import yaml

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksConnectionError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.nsxt.cluster_network_isolater import \
    ClusterNetworkIsolater
from container_service_extension.nsxt.nsxt_client import NSXTClient
from container_service_extension.pks_cache import PKS_COMPUTE_PROFILE_KEY
from container_service_extension.pksclient.api.v1 import PlansApi
from container_service_extension.pksclient.api.v1.cluster_api \
    import ClusterApi as ClusterApiV1
from container_service_extension.pksclient.api.v1beta.cluster_api \
    import ClusterApi as ClusterApiV1Beta
from container_service_extension.pksclient.api.v1beta.profile_api \
    import ProfileApi
from container_service_extension.pksclient.client.v1.api_client \
    import ApiClient as ApiClientV1
from container_service_extension.pksclient.client.v1.rest\
    import ApiException as v1Exception
from container_service_extension.pksclient.client.v1beta.api_client \
    import ApiClient as ApiClientV1Beta
from container_service_extension.pksclient.client.v1beta.rest\
    import ApiException as v1BetaException
from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pksclient.models.v1.\
    update_cluster_parameters import UpdateClusterParameters
from container_service_extension.pksclient.models.v1beta.az import AZ
from container_service_extension.pksclient.models.v1beta.cluster_parameters \
    import ClusterParameters
from container_service_extension.pksclient.models.v1beta.cluster_request \
    import ClusterRequest
from container_service_extension.pksclient.models.v1beta.\
    compute_profile_parameters import ComputeProfileParameters
from container_service_extension.pksclient.models.v1beta.\
    compute_profile_request import ComputeProfileRequest
from container_service_extension.pyvcloud_utils import get_org_name_of_ovdc
from container_service_extension.server_constants import \
    CSE_PKS_DEPLOY_RIGHT_NAME
from container_service_extension.uaaclient.uaaclient import UaaClient
from container_service_extension.utils import exception_handler
from container_service_extension.utils import get_pks_cache
from container_service_extension.utils import OK


# Delimiter to append with user id context
USER_ID_SEPARATOR = "---"
# Properties that need to be excluded from cluster info before sending
# to the client for reasons: security, too big that runs thru lines
EXCLUDE_KEYS = ['authorization_mode', 'compute_profile', 'pks_cluster_name',
                'uuid', 'plan_name', 'compute_profile_name',
                'network_profile_name', 'nsxt_network_profile']

# TODO() Filtering of cluster results should be processed in
#  different layer.


class PKSBroker(AbstractBroker):
    """PKSBroker makes API calls to PKS server.

    It performs CRUD operations on Kubernetes clusters.
    """

    VERSION_V1 = 'v1'
    VERSION_V1BETA = 'v1beta1'

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
            f"https://{pks_ctx['host']}:{pks_ctx['port']}"
        self.uaac_uri = \
            f"https://{pks_ctx['host']}:{pks_ctx['uaac_port']}"
        self.proxy_uri = f"http://{pks_ctx['proxy']}:80" \
            if pks_ctx.get('proxy') else None
        self.compute_profile = pks_ctx.get(PKS_COMPUTE_PROFILE_KEY, None)
        self.nsxt_server = \
            get_pks_cache().get_nsxt_info(pks_ctx.get('vc'))
        if self.nsxt_server:
            self.nsxt_client = NSXTClient(
                host=self.nsxt_server.get('host'),
                username=self.nsxt_server.get('username'),
                password=self.nsxt_server.get('password'),
                http_proxy=self.nsxt_server.get('proxy'),
                https_proxy=self.nsxt_server.get('proxy'),
                verify_ssl=self.nsxt_server.get('verify'),
                log_requests=True,
                log_headers=True,
                log_body=True)
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
        token = self._get_token()
        self.client_v1 = self._get_pks_client(token, self.VERSION_V1)
        self.client_v1beta = self._get_pks_client(token, self.VERSION_V1BETA)
        self.client_session = None
        self.get_tenant_client_session()

    def _get_token(self):
        """Connect to UAA server, authenticate and get token.

        :return: token
        """
        try:
            uaaClient = UaaClient(self.uaac_uri, self.username, self.secret,
                                  proxy_uri=self.proxy_uri)
            return uaaClient.getToken()
        except Exception as err:
            raise PksConnectionError(f'Connection establishment to PKS host'
                                     f' {self.uaac_uri} failed: {err}')

    def _get_pks_config(self, token, version):
        """Construct PKS configuration.

        (PKS configuration is required to construct pksclient)

        :return: PKS configuration

        :rtype:
        container_service_extension.pksclient.configuration.Configuration
        """
        pks_config = Configuration()
        pks_config.proxy = self.proxy_uri
        pks_config.host = f"{self.pks_host_uri}/{version}"
        pks_config.access_token = token
        pks_config.username = self.username
        pks_config.verify_ssl = self.verify

        return pks_config

    def _get_pks_client(self, token, version):
        """Get PKS client.

        :return: PKS client

        :rtype: ApiClient
        """
        pks_config = self._get_pks_config(token, version)
        if version == self.VERSION_V1:
            client = ApiClientV1(configuration=pks_config)
        else:
            client = ApiClientV1Beta(configuration=pks_config)
        return client


    def list_plans(self):
        """Get list of available PKS plans in the system.

        :return: a list of pks-plans if available.

        :rtype: list
        """
        plan_api = PlansApi(api_client=self.client_v1)
        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} "
                     f"to list all available plans")
        try:
            plans = plan_api.list_plans()
        except v1Exception as err:
            LOGGER.debug(f"Listing PKS plans failed with error:\n {err}")
            raise PksServerError(err.status, err.body)
        pks_plans_list = []
        for plan in plans:
            pks_plans_list.append(plan.to_dict())
        return pks_plans_list

    def list_clusters(self, **kwargs):
        """Get list of clusters in PKS environment.

        System administrator gets all the clusters for the given service
        account. Other users get only those clusters which they own.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        cluster_list = self._list_clusters()
        if self.tenant_client.is_sysadmin():
            for cluster in cluster_list:
                self._restore_original_name(cluster)
        else:
            cluster_list = [cluster_dict for cluster_dict in cluster_list
                            if self._is_user_cluster_owner(cluster_dict)]

            # 'is_admin_request' is a flag that is used to restrict access to
            # user context and other secured information on pks cluster
            # information.
            if not kwargs.get('is_admin_request'):
                for cluster in cluster_list:
                    self._filter_pks_properties(cluster)
        return cluster_list

    def _list_clusters(self):
        """Get list of clusters in PKS environment.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        cluster_api = ClusterApiV1(api_client=self.client_v1)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} "
                     f"to list all clusters")
        try:
            clusters = cluster_api.list_clusters()
        except v1Exception as err:
            LOGGER.debug(f"Listing PKS clusters failed with error:\n {err}")
            raise PksServerError(err.status, err.body)

        list_of_cluster_dicts = []
        for cluster in clusters:
            # TODO() Below is a temporary fix to retrieve compute_profile_name.
            #  Expensive _get_cluster_info() call must be removed once PKS team
            #  moves list_clusters to v1beta endpoint.
            v1_beta_cluster = self._get_cluster_info(cluster_name=cluster.name)
            # cluster_dict = {
            #     'name': cluster.name,
            #     'plan_name': cluster.plan_name,
            #     'uuid': cluster.uuid,
            #     'status': cluster.last_action_state,
            #     'last_action': cluster.last_action,
            #     'k8_master_ips': cluster.kubernetes_master_ips,
            #     'compute_profile_name': cluster.compute_profile_name,
            #     'worker_count':
            #     cluster.parameters.kubernetes_worker_instances
            # }
            # list_of_cluster_dicts.append(cluster_dict)
            list_of_cluster_dicts.append(v1_beta_cluster)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on the"
                     f" list of clusters: {list_of_cluster_dicts}")
        return list_of_cluster_dicts

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def create_cluster(self, **cluster_spec):
        """Create cluster in PKS environment.

        To retain the user context, user-id of the logged-in user is appended
        to the original cluster name before the actual cluster creation.

        :param dict cluster_spec: named parameters necessary to create
        cluster (cluster_name, node_count, pks_plan, pks_ext_host, compute-
        profile_name)

        :return: Details of the cluster

        :rtype: dict
        """
        cluster_spec['cluster_name'] = \
            self._append_user_id(cluster_spec['cluster_name'])
        cluster_info = self._create_cluster(**cluster_spec)
        self._restore_original_name(cluster_info)
        if not self.tenant_client.is_sysadmin():
            self._filter_pks_properties(cluster_info)
        return cluster_info

    def _create_cluster(self, cluster_name, node_count, pks_plan, pks_ext_host,
                        compute_profile=None, **kwargs):
        """Create cluster in PKS environment.

        Creates Distributed Firewall rules in NSX-T to isolate the cluster
        network from other clusters.

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
        if not self.nsxt_server:
            raise CseServerError(
                "NSX-T server details not found for PKS server selected for "
                f"cluster : {cluster_name}. Aborting creation of cluster.")

        compute_profile = compute_profile \
            if compute_profile else self.compute_profile
        cluster_api = ClusterApiV1Beta(api_client=self.client_v1beta)
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
        except v1BetaException as err:
            LOGGER.debug(f"Creating cluster {cluster_name} in PKS failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)

        cluster_dict = cluster.to_dict()
        # Flattening the dictionary
        cluster_params_dict = cluster_dict.pop('parameters')
        cluster_dict.update(cluster_params_dict)

        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to create"
                     f" cluster: {cluster_name}")

        # TODO() : Rollback cluster if any error is encountered in this section
        # isolate cluster via NSX-T DFW
        try:
            cluster_id = cluster_dict.get('uuid')
            if cluster_id:
                LOGGER.debug(f"Isolating network of cluster {cluster_name}.")
                cluster_network_isolater = ClusterNetworkIsolater(
                    self.nsxt_client)
                cluster_network_isolater.isolate_cluster(cluster_name,
                                                         cluster_id)
            else:
                raise CseServerError("Failed to isolate network of cluster "
                                     f"{cluster_name}. Cluster ID not found.")
        except Exception as err:
            raise CseServerError("Failed to isolate network of cluster "
                                 f"{cluster_name} : Aborting creation of "
                                 "cluster.") from err

        return cluster_dict

    def get_cluster_info(self, cluster_name, **kwargs):
        """Get the details of a cluster with a given name in PKS environment.

        System administrator gets the given cluster information regardless of
        who is the owner of the cluster. Other users get info only on
        the cluster they own.

        :param str cluster_name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        if self.tenant_client.is_sysadmin():
            filtered_cluster_list = \
                self._filter_list_by_cluster_name(
                    self.list_clusters(is_admin_request=True),
                    cluster_name)
            LOGGER.debug(f"filtered Cluster List:{filtered_cluster_list}")
            # TODO() Sys admin may encounter multiple clusters with the same
            #  name; in that case choosing the first one could be wrong.
            #  Needs revisit
            if len(filtered_cluster_list) > 0:
                cluster_info = filtered_cluster_list[0]
            else:
                raise PksServerError(HTTPStatus.NOT_FOUND,
                                     f"cluster {cluster_name} not found")
        else:
            cluster_info = \
                self._get_cluster_info(self._append_user_id(cluster_name))
            self._restore_original_name(cluster_info)
            if not kwargs.get('is_admin_request'):
                self._filter_pks_properties(cluster_info)
        return cluster_info

    def _get_cluster_info(self, cluster_name):
        """Get the details of a cluster with a given name in PKS environment.

        :param str cluster_name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        cluster_api = ClusterApiV1Beta(api_client=self.client_v1beta)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to get "
                     f"details of cluster with name: {cluster_name}")
        try:
            cluster = cluster_api.get_cluster(cluster_name=cluster_name)
        except v1BetaException as err:
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

        System administrator gets the given cluster config regardless of
        who is the owner of the cluster. Other users get config only on
        the cluster they own.

        :param str cluster_name: Name of the cluster
        :return: Configuration of the cluster.

        :rtype: str
        """
        if self.tenant_client.is_sysadmin():
            cluster = self.get_cluster_info(cluster_name,
                                            is_admin_request=True)
            config_info = self._get_cluster_config(cluster['pks_cluster_name'])
        else:
            pks_cluster_name = self._append_user_id(cluster_name)
            config_info = self._get_cluster_config(pks_cluster_name)

        return self.filter_traces_of_user_context(config_info)

    def _get_cluster_config(self, cluster_name):
        """Get the configuration of the cluster with the given name in PKS.

        :param str cluster_name: Name of the cluster
        :return: Configuration of the cluster.

        :rtype: str
        """
        cluster_api = ClusterApiV1(api_client=self.client_v1)

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

        System administrator can delete the given cluster regardless of
        who is the owner of the cluster. Other users can only delete
        the cluster they own.

        :param str cluster_name: Name of the cluster
        """
        self.get_tenant_client_session()

        if self.tenant_client.is_sysadmin():
            cluster_info = self.get_cluster_info(
                cluster_name, is_admin_request=True)
            pks_cluster_name = cluster_info['pks_cluster_name']
        else:
            pks_cluster_name = self._append_user_id(cluster_name)

        result = self._delete_cluster(pks_cluster_name)
        self._restore_original_name(result)
        self._filter_pks_properties(result)
        return result

    def _delete_cluster(self, cluster_name):
        """Delete the cluster with a given name in PKS environment.

        Also deletes associated NSX-T Distributed Firewall rules that kept the
        cluster network isolated from other clusters.

        :param str cluster_name: Name of the cluster
        """
        result = {}

        cluster_api = ClusterApiV1(api_client=self.client_v1)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to delete "
                     f"the cluster with name: {cluster_name}")
        try:
            cluster_api.delete_cluster(cluster_name=cluster_name)
        except v1Exception as err:
            LOGGER.debug(f"Deleting cluster {cluster_name} failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to delete"
                     f" the cluster: {cluster_name}")

        # remove cluster network isolation
        try:
            LOGGER.debug("Removing network isolation of cluster "
                         f"{cluster_name}.")
            cluster_network_isolater = ClusterNetworkIsolater(self.nsxt_client)
            cluster_network_isolater.remove_cluster_isolation(cluster_name)
        except Exception:
            # NSX-T oprations are idempotent so they should not cause erros
            # if say NSGroup is missing. But for any other exception, simply
            # them and ignore.
            pass

        result['name'] = cluster_name
        result['task_status'] = 'in progress'
        return result

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def resize_cluster(self, **cluster_spec):
        """Resize the cluster of a given name to given number of worker nodes.

        System administrator can resize the given cluster regardless of
        who is the owner of the cluster. Other users can only resize
        the cluster they own.

        :param dict cluster_spec: named parameters that are required to
        resize cluster (cluster_name, node_count)

        :return: response status

        :rtype: dict

        """
        cluster_name = cluster_spec['cluster_name']

        if self.tenant_client.is_sysadmin():
            cluster = self.get_cluster_info(cluster_name,
                                            is_admin_request=True)
            cluster_spec['cluster_name'] = cluster['pks_cluster_name']
        else:
            pks_cluster_name = self._append_user_id(cluster_name)
            cluster_spec['cluster_name'] = pks_cluster_name

        result = self._resize_cluster(**cluster_spec)
        self._restore_original_name(result)
        self._filter_pks_properties(result)
        return result

    def _resize_cluster(self, cluster_name, node_count, **kwargs):
        """Resize the cluster of a given name to given number of worker nodes.

        :param str cluster_name: Name of the cluster
        :param int node_count: New size of the worker nodes
        """
        result = {}
        cluster_api = ClusterApiV1(api_client=self.client_v1)
        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to resize "
                     f"the cluster with name: {cluster_name} to "
                     f"{node_count} worker nodes")

        resize_params = UpdateClusterParameters(
            kubernetes_worker_instances=node_count)
        try:
            cluster_api.update_cluster(cluster_name, body=resize_params)
        except v1Exception as err:
            LOGGER.debug(f"Resizing cluster {cluster_name} failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to resize"
                     f" the cluster: {cluster_name}")

        result['name'] = cluster_name
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
        profile_api = ProfileApi(api_client=self.client_v1beta)

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

        az = AZ(name=az_name, cpi=cpi, cloud_properties=cloud_properties)
        cp_params = ComputeProfileParameters(azs=[az])
        cp_request = ComputeProfileRequest(name=cp_name,
                                           description=description,
                                           parameters=cp_params)

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to create "
                     f"the compute profile: {cp_name} for ovdc {ovdc_rp_name}")
        try:
            profile_api.add_compute_profile(body=cp_request)
        except v1BetaException as err:
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
        profile_api = ProfileApi(api_client=self.client_v1beta)

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to get the "
                     f"compute profile: {cp_name}")

        try:
            compute_profile = \
                profile_api.get_compute_profile(profile_name=cp_name)
        except v1BetaException as err:
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
        profile_api = ProfileApi(api_client=self.client_v1beta)

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to get the "
                     f"list of compute profiles")
        try:
            cp_list = profile_api.list_compute_profiles()
        except v1BetaException as err:
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
        profile_api = ProfileApi(api_client=self.client_v1beta)

        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to delete "
                     f"the compute profile: {cp_name}")

        try:
            profile_api.delete_compute_profile(profile_name=cp_name)
        except v1BetaException as err:
            LOGGER.debug(f"Deleting compute-profile {cp_name} in PKS failed "
                         f"with error:\n {err}")
            raise PksServerError(err.status, err.body)

        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} that"
                     f" it deleted the compute profile: {cp_name}")

        return result

    def _append_user_id(self, name):
        user_id = self._get_vcd_userid()
        return f"{name}{USER_ID_SEPARATOR}{user_id}"

    def _restore_original_name(self, cluster_info):
        # From the given cluster information, transforms the
        # PKS cluster name to its original name as named by the
        # vCD user, and include that name in the cluster information

        cluster_info['pks_cluster_name'] = cluster_info['name']
        original_name_info = cluster_info['name'].split(USER_ID_SEPARATOR)
        cluster_info['name'] = original_name_info[0]

    def _is_user_cluster_owner(self, cluster_info):
        # Returns True if the logged-in user is the owner of the given cluster.
        # Also, restores the actual name of the cluster, if it is owned by
        # the logged-in user and add it to the cluster information.

        is_user_cluster_owner = False
        user_id = self._get_vcd_userid()
        if user_id in cluster_info['name']:
            self._restore_original_name(cluster_info)
            is_user_cluster_owner = True

        return is_user_cluster_owner

    def _get_vcd_userid(self):
        return extract_id(self.client_session.get('userId'))

    # TODO() Should be moved to filtering layer
    def _filter_list_by_cluster_name(self, cluster_list, cluster_name):
        # Return those clusters which have the given cluster name
        return [cluster for cluster in cluster_list
                if cluster['name'] == cluster_name]

    # TODO() Should be moved to filtering layer
    def _filter_pks_properties(self, cluster_info):
        # Remove selective properties from the given cluster
        # information.
        for entry in EXCLUDE_KEYS:
            cluster_info.pop(entry, None)

    # TODO() Should be moved to filtering layer
    @staticmethod
    def filter_traces_of_user_context(cluster_info):
        """Remove traces of user-id pattern from the given string.

        :param str cluster_info: text information that may have user context

        :return: cluster info with user context removed
        :rtype: str
        """
        return re.sub(rf"{USER_ID_SEPARATOR}\S+", '', cluster_info)

    def __getattr__(self, name):
        """Handle unknown operations.

        Example: This broker does
        not support individual node operations.
        """
        def unsupported_method(*args):
            raise CseServerError(f"Unsupported operation {name}")
        return unsupported_method

    @staticmethod
    def generate_cluster_subset_with_given_keys(cluster, cluster_property_keys):
        pks_cluster = {k: cluster.get(k) for k in
                       cluster_property_keys}
        # Extract vdc name from compute-profile-name
        # Example: vdc name in the below compute profile is: vdc-PKS1
        # compute-profile: cp--f3272127-9b7f-4f90-8849-0ee70a28be56--vdc-PKS1
        compute_profile_name = cluster.get('compute_profile_name', '')
        vdc_id = compute_profile_name.split('--')[1] \
            if compute_profile_name else ''
        pks_cluster['vdc'] = compute_profile_name.split('--')[-1] \
            if compute_profile_name else ''
        pks_cluster['status'] = \
            cluster.get('last_action', '').lower() + ' ' + \
            cluster.get('last_action_state', '').lower()
        if vdc_id:
            pks_cluster['org_name'] = \
                get_org_name_of_ovdc(vdc_id)
        return pks_cluster
