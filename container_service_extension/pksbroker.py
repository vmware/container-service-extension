# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import re

from pyvcloud.vcd.utils import extract_id
import requests
import yaml

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
from container_service_extension.exceptions import ClusterNetworkIsolationError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import PksConnectionError
from container_service_extension.exceptions import PksDuplicateClusterError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.nsxt.cluster_network_isolater import \
    ClusterNetworkIsolater
from container_service_extension.nsxt.nsxt_client import NSXTClient
from container_service_extension.pks_cache import PKS_COMPUTE_PROFILE_KEY
from container_service_extension.pksclient.api.cluster_api import ClusterApi
from container_service_extension.pksclient.api.plans_api import PlansApi
from container_service_extension.pksclient.api.profile_api import ProfileApi
from container_service_extension.pksclient.api_client import ApiClient
from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pksclient.models.az import AZ
from container_service_extension.pksclient.models.cluster_parameters \
    import ClusterParameters
from container_service_extension.pksclient.models.cluster_request \
    import ClusterRequest
from container_service_extension.pksclient.models.compute_profile_parameters \
    import ComputeProfileParameters
from container_service_extension.pksclient.models.compute_profile_request \
    import ComputeProfileRequest
from container_service_extension.pksclient.models.update_cluster_parameters \
    import UpdateClusterParameters
from container_service_extension.pksclient.rest import ApiException
from container_service_extension.pyvcloud_utils import \
    get_org_name_from_ovdc_id
from container_service_extension.pyvcloud_utils import is_org_admin
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import \
    CSE_PKS_DEPLOY_RIGHT_NAME
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import KwargKey
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.shared_constants import RequestKey
from container_service_extension.uaaclient.uaaclient import UaaClient
import container_service_extension.utils as utils

# Delimiter to append with user id context
USER_ID_SEPARATOR = "---"
# Properties that need to be excluded from cluster info before sending
# to the client for reasons: security, too big that runs thru lines
SENSITIVE_PKS_KEYS = [
    'authorization_mode', 'available_upgrades', 'cluster_tags',
    'compute_profile', 'compute_profile_name', 'custom_ca_certs',
    'k8s_customization_parameters', 'kubernetes_profile_name',
    'kubernetes_setting_cluster_details', 'kubernetes_setting_plan_details',
    'network_profile_name', 'nsxt_network_details', 'nsxt_network_profile',
    'pks_cluster_name', 'plan_name', 'uuid']

# TODO: Filtering of cluster results should be processed in
#  different layer.


class PksBroker(AbstractBroker):
    """PksBroker makes API calls to PKS server.

    It performs CRUD operations on Kubernetes clusters.
    """

    VERSION_V1 = 'v1'

    def __init__(self, pks_ctx, tenant_auth_token, is_jwt_token):
        """Initialize PKS broker.

        :param dict pks_ctx: A dictionary with which should atleast have the
            following keys in it ['username', 'secret', 'host', 'port',
            'uaac_port'], 'proxy' and 'pks_compute_profile_name' are optional
            keys. Currently all callers of this method is using ovdc cache
            (subject to change) to initialize PKS broker.
        """
        self.tenant_client = None
        self.client_session = None
        self.tenant_user_name = None
        self.tenant_user_id = None
        self.tenant_org_name = None
        self.tenant_org_href = None
        # populates above attributes
        super().__init__(tenant_auth_token, is_jwt_token)

        if not pks_ctx:
            raise ValueError(
                "PKS context is required to establish connection to PKS")

        self.username = pks_ctx['username']
        self.secret = pks_ctx['secret']
        self.pks_host_uri = f"https://{pks_ctx['host']}:{pks_ctx['port']}"
        self.uaac_uri = f"https://{pks_ctx['host']}:{pks_ctx['uaac_port']}"
        self.proxy_uri = None
        if pks_ctx.get('proxy'):
            self.proxy_uri = f"http://{pks_ctx['proxy']}:80"
        self.compute_profile = pks_ctx.get(PKS_COMPUTE_PROFILE_KEY, None)
        self.nsxt_server = \
            utils.get_pks_cache().get_nsxt_info(pks_ctx.get('vc'))
        self.nsxt_client = None
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
        # TODO: Add support in pyvcloud to send metadata values with their
        # types intact.
        verify_ssl = pks_ctx.get('verify')
        self.verify = True
        if isinstance(verify_ssl, bool):
            self.verify = verify_ssl
        elif isinstance(verify_ssl, str):
            self.verify = utils.str_to_bool(verify_ssl)

        token = self._get_token()
        self.client = self._get_pks_client(token)

    def _get_token(self):
        """Connect to UAA server, authenticate and get token.

        :return: token
        """
        try:
            uaaClient = UaaClient(self.uaac_uri, self.username, self.secret,
                                  proxy_uri=self.proxy_uri)
            return uaaClient.getToken()
        except Exception as err:
            raise PksConnectionError(requests.codes.bad_gateway,
                                     f'Connection establishment to PKS host'
                                     f' {self.uaac_uri} failed: {err}')

    def _get_pks_config(self, token):
        """Construct PKS configuration.

        (PKS configuration is required to construct pksclient)

        :return: PKS configuration

        :rtype:
        container_service_extension.pksclient.configuration.Configuration
        """
        pks_config = Configuration()
        pks_config.proxy = self.proxy_uri
        pks_config.host = f"{self.pks_host_uri}/{self.VERSION_V1}"
        pks_config.access_token = token
        pks_config.username = self.username
        pks_config.verify_ssl = self.verify

        return pks_config

    def _get_pks_client(self, token):
        """Get PKS client.

        :return: PKS client

        :rtype: ApiClient
        """
        pks_config = self._get_pks_config(token)
        client = ApiClient(configuration=pks_config)
        return client

    def list_plans(self):
        """Get list of available PKS plans in the system.

        :return: a list of pks-plans if available.

        :rtype: list
        """
        plan_api = PlansApi(api_client=self.client)
        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} "
                     f"to list all available plans")
        try:
            pks_plans = plan_api.list_plans()
        except ApiException as err:
            LOGGER.debug(f"Listing PKS plans failed with error:\n {err}")
            raise PksServerError(err.status, err.body)

        result = []
        for pks_plan in pks_plans:
            result.append(pks_plan.to_dict())
        return result

    def list_clusters(self, **kwargs):
        """Get list of clusters in PKS environment.

        System administrator gets all the clusters for the given service
        account. Other users get only those clusters which they own.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        data = kwargs[KwargKey.DATA]
        cluster_list = self._list_clusters()

        # Required for all personae
        for cluster in cluster_list:
            self._restore_original_name(cluster)

        return self._filter_clusters(cluster_list, **data)

    def _list_clusters(self):
        """Get list of clusters in PKS environment.

        :return: a list of cluster-dictionaries

        :rtype: list
        """
        cluster_api = ClusterApiV1(api_client=self.client_v1)

        result = []
        try:
            cluster_api = ClusterApi(api_client=self.client)

            LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} "
                         f"to list all clusters")
            pks_clusters = cluster_api.list_clusters()

            LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} "
                         f"on the list of clusters: {pks_clusters}")

            for pks_cluster in pks_clusters:
                cluster_info = pks_cluster.to_dict()
                cluster_info[K8S_PROVIDER_KEY] = K8sProvider.PKS
                self._restore_original_name(cluster_info)
                # Flatten the nested 'parameters' dict
                cluster_params_dict = cluster_info.pop('parameters')
                cluster_info.update(cluster_params_dict)
                self.update_cluster_with_vcd_info(cluster_info)
                result.append(cluster_info)
        except ApiException as err:
            LOGGER.debug(f"Listing PKS clusters failed with error:\n {err}")
            raise PksServerError(err.status, err.body)

        return self._filter_clusters(result, **data)

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def create_cluster(self, **kwargs):
        """Create cluster in PKS environment.

        To retain the user context, user-id of the logged-in user is appended
        to the original cluster name before the actual cluster creation.

        :param **data:
            dict cluster_spec: named parameters necessary to create
            cluster (cluster_name, node_count, pks_plan, pks_ext_host, compute-
            profile_name)

        :return: Details of the cluster

        :rtype: dict
        """
        data = kwargs[KwargKey.DATA]
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.PKS_PLAN_NAME,
            RequestKey.PKS_EXT_HOST,
            RequestKey.ORG_NAME,
            RequestKey.OVDC_NAME
        ]
        req_utils.validate_payload(data, required)

        cluster_name = data[RequestKey.CLUSTER_NAME]
        qualified_cluster_name = self._append_user_id(cluster_name)
        data[RequestKey.CLUSTER_NAME] = qualified_cluster_name

        if not self.nsxt_server:
            raise CseServerError(
                "NSX-T server details not found for PKS server selected for "
                f"cluster : {cluster_name}. Aborting creation of cluster.")

        # this needs to be refactored
        # when num_workers==None, PKS creates however many the plan specifies
        cluster = self._create_cluster(
            cluster_name=data[RequestKey.CLUSTER_NAME],
            num_workers=data.get(RequestKey.NUM_WORKERS),
            pks_plan_name=data[RequestKey.PKS_PLAN_NAME],
            pks_ext_host=data[RequestKey.PKS_EXT_HOST])

        self._isolate_cluster(cluster_name, qualified_cluster_name,
                              cluster.get('uuid'))

        self._restore_original_name(cluster)
        if not self.tenant_client.is_sysadmin():
            self._filter_sensitive_pks_properties(cluster)

        return cluster

    # all parameters following '*args' are required and keyword-only
    def _create_cluster(self, *args,
                        cluster_name, num_workers, pks_plan_name,
                        pks_ext_host):
        """Create cluster in PKS environment.

        Creates Distributed Firewall rules in NSX-T to isolate the cluster
        network from other clusters.

        :param str cluster_name: Name of the cluster
        :param str plan: PKS plan. It should be one of the three plans
        that PKS supports.
        :param str external_host_name: User-preferred external hostname
         of the K8 cluster

        :return: Details of the cluster

        :rtype: dict
        """
        cluster_api = ClusterApi(api_client=self.client)
        cluster_params = \
            ClusterParameters(kubernetes_master_host=pks_ext_host,
                              kubernetes_worker_instances=num_workers)
        cluster_request = \
            ClusterRequest(name=cluster_name,
                           plan_name=pks_plan_name,
                           parameters=cluster_params,
                           compute_profile_name=self.compute_profile)

        try:
            LOGGER.debug(
                f"Sending request to PKS: {self.pks_host_uri} to create "
                f"cluster of name: {cluster_name}")

            cluster = cluster_api.add_cluster(cluster_request)

            LOGGER.debug(
                f"PKS: {self.pks_host_uri} accepted the request to create"
                f" cluster: {cluster_name}")
        except ApiException as err:
            LOGGER.debug(f"Creating cluster {cluster_name} in PKS failed with "
                         f"error:\n {err}")
            raise PksServerError(err.status, err.body)

        cluster_info = cluster.to_dict()
        # Flattening the dictionary
        cluster_params_dict = cluster_info.pop('parameters')
        cluster_info.update(cluster_params_dict)

        return cluster_info

    def get_cluster_info(self, **kwargs):
        """Get the details of a cluster with a given name in PKS environment.

        System administrator gets the given cluster information regardless of
        who is the owner of the cluster. Other users get info only on
        the cluster they own.

        :param **data dict
            :str cluster_name: Name of the cluster
        :return: Details of the cluster.

        :rtype: dict
        """
        data = kwargs[KwargKey.DATA]
        cluster_name = data[RequestKey.CLUSTER_NAME]
        # The structure of info returned by list_cluster and get_cluster is
        # identical, hence using list_cluster and filtering by name in memory
        # to retrieve info of the requested cluster.
        cluster_info_list = self._list_clusters(data)
        result = {}
        if self.tenant_client.is_sysadmin() \
                or is_org_admin(self.client_session) \
                or data.get('is_org_admin_search'):
            filtered_cluster_info_list = []
            for cluster_info in cluster_info_list:
                if cluster_info['name'] == cluster_name:
                    filtered_cluster_info_list.append(cluster_info)
            LOGGER.debug(
                f"Filtered list of clusters:{filtered_cluster_info_list}")
            if len(filtered_cluster_info_list) > 1:
                raise PksDuplicateClusterError(
                    requests.codes.bad_request,
                    f"Multiple clusters with name '{cluster_name}' exists.")
            if len(filtered_cluster_info_list) == 0:
                raise PksServerError(requests.codes.not_found,
                                     f"cluster {cluster_name} not found.")
            result = filtered_cluster_info_list[0]
        else:
            qualified_cluster_name = self._append_user_id(cluster_name)
            for cluster_info in cluster_info_list:
                if cluster_info['pks_cluster_name'] == qualified_cluster_name:
                    result = cluster_info
                    break
            if not result:
                raise PksServerError(requests.codes.not_found,
                                     f"cluster {cluster_name} not found.")

        return result

    def get_cluster_config(self, **kwargs):
        """Get the configuration of the cluster with the given name in PKS.

        System administrator gets the given cluster config regardless of
        who is the owner of the cluster. Other users get config only on
        the cluster they own.

        :return: Configuration of the cluster.

        :rtype: str
        """
        data = kwargs[KwargKey.DATA]
        cluster_name = data[RequestKey.CLUSTER_NAME]

        if self.tenant_client.is_sysadmin() or \
                is_org_admin(self.client_session):
            cluster_info = self.get_cluster_info(data=data)
            qualified_cluster_name = cluster_info['pks_cluster_name']
        else:
            qualified_cluster_name = self._append_user_id(cluster_name)

        self._check_cluster_isolation(cluster_name, qualified_cluster_name)

        cluster_api = ClusterApi(api_client=self.client)

        LOGGER.debug(f"Sending request to PKS: {self.pks_host_uri} to get"
                     f" kubectl configuration of cluster with name: "
                     f"{qualified_cluster_name}")
        config = cluster_api.create_user(cluster_name=qualified_cluster_name)
        LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on "
                     f"cluster: {qualified_cluster_name} with details: "
                     f"{config}")
        cluster_config = yaml.safe_dump(config, default_flow_style=False)

        return self.filter_traces_of_user_context(cluster_config)

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def delete_cluster(self, **kwargs):
        """Delete the cluster with a given name in PKS environment.

        System administrator can delete the given cluster regardless of
        who is the owner of the cluster. Other users can only delete
        the cluster they own.
        :param **data
            :param str cluster_name: Name of the cluster
        """
        data = kwargs[KwargKey.DATA]
        cluster_name = data[RequestKey.CLUSTER_NAME]

        if self.tenant_client.is_sysadmin() \
                or is_org_admin(self.client_session):
            cluster_info = self.get_cluster_info(data=data)
            qualified_cluster_name = cluster_info['pks_cluster_name']
        else:
            qualified_cluster_name = self._append_user_id(cluster_name)

        result = {}
        cluster_api = ClusterApi(api_client=self.client)

        try:
            LOGGER.debug(
                f"Sending request to PKS: {self.pks_host_uri} to delete "
                f"the cluster with name: {qualified_cluster_name}")
            cluster_api.delete_cluster(cluster_name=qualified_cluster_name)

            LOGGER.debug(
                f"PKS: {self.pks_host_uri} accepted the request to delete"
                f" the cluster: {qualified_cluster_name}")
        except ApiException as err:
            LOGGER.debug(f"Deleting cluster {qualified_cluster_name} failed"
                         f" with error:\n {err}")
            raise PksServerError(err.status, err.body)

        result['name'] = qualified_cluster_name
        result['task_status'] = 'in progress'

        # remove cluster network isolation
        LOGGER.debug("Removing network isolation of cluster "
                     f"{qualified_cluster_name}.")
        try:
            cluster_network_isolater = ClusterNetworkIsolater(self.nsxt_client)
            cluster_network_isolater.remove_cluster_isolation(
                qualified_cluster_name)
        except Exception as err:
            # NSX-T oprations are idempotent so they should not cause erros
            # if say NSGroup is missing. But for any other exception, simply
            # catch them and ignore.
            LOGGER.debug(f"Error {err} occured while deleting cluster "
                         "isolation rules for cluster "
                         f"{qualified_cluster_name}")

        return result

    @secure(required_rights=[CSE_PKS_DEPLOY_RIGHT_NAME])
    def resize_cluster(self, **kwargs):
        """Resize the cluster of a given name to given number of worker nodes.

        System administrator can resize the given cluster regardless of
        who is the owner of the cluster. Other users can only resize
        the cluster they own.


        :return: response status

        :rtype: dict

        """
        data = kwargs[KwargKey.DATA]
        cluster_name = data[RequestKey.CLUSTER_NAME]
        num_workers = data[RequestKey.NUM_WORKERS]

        if self.tenant_client.is_sysadmin() \
                or is_org_admin(self.client_session):
            cluster_info = self.get_cluster_info(data=data)
            qualified_cluster_name = cluster_info['pks_cluster_name']
        else:
            qualified_cluster_name = self._append_user_id(cluster_name)

        self._check_cluster_isolation(cluster_name, qualified_cluster_name)

        result = {}
        cluster_api = ClusterApi(api_client=self.client)
        LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to resize "
                     f"the cluster with name: {qualified_cluster_name} to "
                     f"{num_workers} worker nodes")
        resize_params = \
            UpdateClusterParameters(kubernetes_worker_instances=num_workers)
        try:
            cluster_api.update_cluster(qualified_cluster_name,
                                       body=resize_params)
        except ApiException as err:
            LOGGER.debug(f"Resizing cluster {qualified_cluster_name} failed"
                         f" with error:\n {err}")
            raise PksServerError(err.status, err.body)
        LOGGER.debug(f"PKS: {self.pks_host_uri} accepted the request to resize"
                     f" the cluster: {qualified_cluster_name}")

        result['name'] = qualified_cluster_name
        result['task_status'] = 'in progress'
        self._restore_original_name(result)
        if not self.tenant_client.is_sysadmin():
            self._filter_sensitive_pks_properties(result)
        return result

    def _check_cluster_isolation(self, cluster_name, qualified_cluster_name):
        cluster_network_isolater = ClusterNetworkIsolater(self.nsxt_client)
        if not cluster_network_isolater.is_cluster_isolated(
                qualified_cluster_name):
            raise ClusterNetworkIsolationError(
                f"Cluster '{cluster_name}' is in an unusable state. Please "
                "delete it and redeploy.")

    def _isolate_cluster(self, cluster_name, qualified_cluster_name,
                         cluster_id):
        if not cluster_id:
            raise ValueError(
                f"Invalid cluster_id for cluster : '{cluster_name}'")

        LOGGER.debug(f"Isolating network of cluster {qualified_cluster_name}.")
        try:
            cluster_network_isolater = ClusterNetworkIsolater(self.nsxt_client)
            cluster_network_isolater.isolate_cluster(qualified_cluster_name,
                                                     cluster_id)
        except Exception as err:
            raise ClusterNetworkIsolationError(
                f"Cluster : '{cluster_name}' is in an unusable state. Failed "
                "to isolate cluster network") from err

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
        result['status_code'] = requests.codes.ok
        profile_api = ProfileApi(api_client=self.client)

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
        cp_request = ComputeProfileRequest(
            name=cp_name, description=description, parameters=cp_params)

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

    def get_compute_profile(self, cp_name):
        """Get the details of compute profile.

        :param str cp_name: Name of the compute profile
        :return: Details of the compute profile as body of the result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = requests.codes.ok
        profile_api = ProfileApi(api_client=self.client)

        try:
            LOGGER.debug(f"Sending request to PKS:{self.pks_host_uri} to get "
                         f"the compute profile: {cp_name}")
            compute_profile = \
                profile_api.get_compute_profile(profile_name=cp_name)
            LOGGER.debug(f"Received response from PKS: {self.pks_host_uri} on "
                         f"compute-profile: {cp_name} with details: "
                         f"{compute_profile.to_dict()}")
        except ApiException as err:
            LOGGER.debug(f"Creating compute-profile {cp_name} in PKS failed "
                         f"with error:\n {err}")
            raise PksServerError(err.status, err.body)

        result['body'] = compute_profile.to_dict()
        return result

    def list_compute_profiles(self):
        """Get the list of compute profiles.

        :return: List of compute profile details as body of the result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = requests.codes.ok
        profile_api = ProfileApi(api_client=self.client)

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

    def delete_compute_profile(self, cp_name):
        """Delete the compute profile with a given name.

        :param str cp_name: Name of the compute profile
        :return: result

        :rtype: dict
        """
        result = {}
        result['body'] = []
        result['status_code'] = requests.codes.ok
        profile_api = ProfileApi(api_client=self.client)

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
        user_id = self._get_vcd_userid()
        return f"{name}{USER_ID_SEPARATOR}{user_id}"

    def _restore_original_name(self, cluster_info):
        # From the given cluster information, transforms the
        # PKS cluster name to its original name as named by the
        # vCD user, and include that name in the cluster information

        cluster_info['pks_cluster_name'] = cluster_info['name']
        original_name_info = cluster_info['name'].split(USER_ID_SEPARATOR)
        cluster_info['name'] = original_name_info[0]

    def _filter_clusters(self, cluster_list, **kwargs):
        """Filter the cluster list based on vdc, org by personae.

        Apply the filters in the following order of priority and return the
        result once the specific-persona-only filter is applied.

        1. Filter clusters based on vdc for all personae.
        2. Filter clusters based on org only for sysadmin.
        3. Filter clusters for org admin based on visibility.
        4. Filter clusters for tenant users based on ownership only.

        :param list cluster_list: list of clusters
        :return: filtered list of clusters

        :rtype: list
        TODO() These filters should be moved to either broker layer or
        delegated to dedicated filter class say: PksClusterFilter.
        """
        # Apply vdc filter, if provided to all personae.
        if kwargs.get(RequestKey.OVDC_NAME):
            cluster_list = \
                self._apply_vdc_filter(cluster_list,
                                       kwargs.get(RequestKey.OVDC_NAME))

        # Apply org filter, if provided, for sys admin.
        if self.tenant_client.is_sysadmin():
            org_name = kwargs.get(RequestKey.ORG_NAME)
            if org_name and org_name.lower() != SYSTEM_ORG_NAME.lower():
                cluster_list = self._apply_org_filter(cluster_list, org_name)
            return cluster_list

        # Filter the cluster list for org admin and others.
        if is_org_admin(self.client_session) or kwargs.get('is_org_admin_search'): # noqa: E501
            # TODO() - Service accounts for exclusive org does not
            #  require the following filtering.
            cluster_list = [cluster_info for cluster_info in cluster_list
                            if self._is_cluster_visible_to_org_admin(
                                cluster_info)]
        else:
            cluster_list = [cluster_info for cluster_info in cluster_list
                            if self._is_user_cluster_owner(cluster_info)]
        return cluster_list

    def _is_cluster_visible_to_org_admin(self, cluster_info):
        # Returns True if org-admin is the cluster owner, or
        # the cluster belongs to same org as org-admin's.
        return self._is_user_cluster_owner(cluster_info) or\
            self._does_cluster_belong_to_org(cluster_info,
                                             self.client_session.get('org'))

    def _is_user_cluster_owner(self, cluster_info):
        # Returns True if the logged-in user is the owner of the given cluster.
        # Also, restores the actual name of the cluster, if it is owned by
        # the logged-in user and add it to the cluster information.

        is_user_cluster_owner = False
        user_id = self._get_vcd_userid()
        if user_id in cluster_info['pks_cluster_name']:
            is_user_cluster_owner = True

        return is_user_cluster_owner

    def _get_vcd_userid(self):
        return extract_id(self.client_session.get('userId'))

    def _extract_vdc_name_from_pks_compute_profile_name(
            self, compute_profile_name):
        """Extract the vdc name from pks compute profile name.

        compute-profile:
            cp--f3272127-9b7f-4f90-8849-0ee70a28be56--vdc----PKS1
        Example: vdc name in the below compute profile is: vdc----PKS1

        :param str compute_profile_name: name of the pks compute profile

        :return: name of the vdc in vcd.

        :rtype: str
        """
        tokens = compute_profile_name.split('--')
        if len(tokens) > 2:
            vdc_name = '--'.join(tokens[2:])
        else:
            vdc_name = ''
        return vdc_name

    def _extract_vdc_id_from_pks_compute_profile_name(
            self, compute_profile_name):
        """Extract the vdc identifier from pks compute profile name.

        compute-profile:
            cp--f3272127-9b7f-4f90-8849-0ee70a28be56--vdc----PKS1
        Example: vdc id will be : f3272127-9b7f-4f90-8849-0ee70a28be56

        :param str compute_profile_name: name of the pks compute profile

        :return: UUID of the vdc in vcd.

        :rtype: str
        """
        return compute_profile_name.split('--')[1]

    def _does_cluster_belong_to_org(self, cluster_info, org_name):
        # Returns True if the cluster belongs to the given org
        # Else False (this also includes missing compute profile name)

        compute_profile_name = cluster_info.get('compute_profile_name')
        if compute_profile_name is None:
            LOGGER.debug(f"compute-profile-name of {cluster_info.get('name')}"
                         f" is not found")
            return False
        vdc_id = self._extract_vdc_id_from_pks_compute_profile_name(
            compute_profile_name)
        return org_name == get_org_name_from_ovdc_id(vdc_id)

    def _apply_vdc_filter(self, cluster_list, vdc_name):
        cluster_list = [cluster_info for cluster_info in cluster_list
                        if self._does_cluster_belong_to_vdc
                        (cluster_info, vdc_name)]
        return cluster_list

    def _apply_org_filter(self, cluster_list, org_name):
        cluster_list = [cluster_info for cluster_info in cluster_list
                        if self._does_cluster_belong_to_org
                        (cluster_info, org_name)]
        return cluster_list

    def _does_cluster_belong_to_vdc(self, cluster_info, vdc_name):
        # Returns True if the cluster backed by given vdc
        # Else False (this also includes missing compute profile name)
        compute_profile_name = cluster_info.get('compute_profile_name')
        if compute_profile_name is None:
            LOGGER.debug(f"compute-profile-name of {cluster_info.get('name')}"
                         f" is not found")
            return False
        vdc_of_cluster = self._extract_vdc_name_from_pks_compute_profile_name(
            compute_profile_name)
        return vdc_of_cluster == vdc_name

    # TODO() Should be moved to filtering layer
    def _filter_sensitive_pks_properties(self, cluster_info):
        # Remove selective properties from the given cluster
        # information.
        for sensitive_key in SENSITIVE_PKS_KEYS:
            cluster_info.pop(sensitive_key, None)

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

    def update_cluster_with_vcd_info(self, pks_cluster):
        compute_profile_name = pks_cluster.get('compute_profile_name', '')
        pks_cluster['vdc'] = ''
        if compute_profile_name:
            vdc_id = self._extract_vdc_id_from_pks_compute_profile_name(compute_profile_name)  # noqa: E501
            pks_cluster['org_name'] = get_org_name_from_ovdc_id(vdc_id)
            pks_cluster['vdc'] = self._extract_vdc_name_from_pks_compute_profile_name(compute_profile_name)  # noqa: E501

        pks_cluster['status'] = \
            pks_cluster.get('last_action', '').lower() + ' ' + \
            pks_cluster.get('last_action_state', '').lower()

        return pks_cluster
