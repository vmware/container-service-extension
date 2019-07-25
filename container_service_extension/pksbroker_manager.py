# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.org import Org

from container_service_extension.exceptions import PksClusterNotFoundError
from container_service_extension.exceptions import PksDuplicateClusterError
from container_service_extension.exceptions import PksServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.ovdc_utils as ovdc_utils
from container_service_extension.pksbroker import PKSBroker
from container_service_extension.pyvcloud_utils import connect_vcd_user_via_token # noqa: E501
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.utils import get_pks_cache


class PksBrokerManager(object):
    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec
        self.pks_cache = get_pks_cache()
        self.vcd_client, self.session = connect_vcd_user_via_token(
            tenant_auth_token=tenant_auth_token)

    def list_clusters(self):
        pks_clusters = []
        pks_ctx_list = self.create_pks_context_for_all_accounts_in_org()
        for pks_ctx in pks_ctx_list:
            pks_broker = PKSBroker(self.tenant_auth_token, self.req_spec,
                                   pks_ctx)
            # Get all cluster information to get vdc name from
            # compute-profile-name
            for cluster in pks_broker.list_clusters(is_admin_request=True):
                pks_cluster = \
                    pks_broker.generate_cluster_subset_with_given_keys(cluster)
                pks_clusters.append(pks_cluster)
        return pks_clusters

    def find_cluster_in_org(self, cluster_name, is_org_admin_search=False):
        """Invoke all PKS brokers in the org to find the cluster.

        'is_org_admin_search' is used here to prevent cluster creation with
        same cluster-name by users within org. If it is true,
        cluster list is filtered by the org name of the logged-in user.

        If cluster found:
            Return a tuple of (cluster and the broker instance used to find
            the cluster)
        Else:
            (None, None) if cluster not found.
        """
        pks_ctx_list = \
            self.create_pks_context_for_all_accounts_in_org()
        for pks_ctx in pks_ctx_list:
            pksbroker = PKSBroker(self.tenant_auth_token, self.req_spec,
                                  pks_ctx)
            try:
                return pksbroker.get_cluster_info(
                    cluster_name=cluster_name,
                    is_org_admin_search=is_org_admin_search), pksbroker
            except PksClusterNotFoundError as err:
                # If a cluster is not found, then broker_manager will
                # decide if it wants to raise an error or ignore it if was it
                # just scanning the broker to check if it can handle the
                # cluster request or not.
                LOGGER.debug(f"Get cluster info on {cluster_name}"
                             f"on PKS failed with error: {err}")
            except PksDuplicateClusterError as err:
                LOGGER.debug(f"Get cluster info on {cluster_name}"
                             f"on PKS failed with error: {err}")
                raise
            except PksServerError as err:
                LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                             f"on {pks_ctx['host']} with error: {err}")
        return None, None

    def create_pks_context_for_all_accounts_in_org(self):
        """Create PKS context for accounts in a given Org.

        If user is Sysadmin
            Creates PKS contexts for all PKS accounts defined in the entire
            system.
        else
            Creates PKS contexts for all PKS accounts assigned to the org.
            However if separate service accounts for each org hasn't been
            configued by admin via pks.yaml, then PKS accounts of the PKS
            server corresponding to the vCenters powering the individual
            orgVDC of the org will be picked up for creating the PKS contexts.

        :return: list of dict, where each dictionary is a PKS context

        :rtype: list
        """
        if not self.pks_cache:
            return []

        if self.vcd_client.is_sysadmin():
            all_pks_account_info = \
                self.pks_cache.get_all_pks_account_info_in_system()
            pks_ctx_list = [ovdc_utils.construct_pks_context(
                pks_account_info, credentials_required=True)
                for pks_account_info in all_pks_account_info]
            return pks_ctx_list

        org_resource = self.vcd_client.get_org()
        org_name = org_resource.get('name')
        if self.pks_cache.do_orgs_have_exclusive_pks_account():
            pks_account_infos = \
                self.pks_cache.get_exclusive_pks_accounts_info_for_org(
                    org_name)
            pks_ctx_list = [ovdc_utils.construct_pks_context
                            (pks_account_info, credentials_required=True)
                            for pks_account_info in pks_account_infos]
        else:
            org = Org(self.vcd_client, resource=org_resource)
            vdc_names = [vdc['name'] for vdc in org.list_vdcs()]
            # Constructing dict instead of list to avoid duplicates
            # TODO() figure out a way to add pks contexts to a set directly
            pks_ctx_dict = {}
            for vdc_name in vdc_names:
                # this is a full blown pks_account_info + pvdc_info +
                # compute_profile_name dictionary
                ctr_prov_ctx = ovdc_utils.get_ovdc_k8s_provider_metadata(
                    ovdc_name=vdc_name, org_name=org_name,
                    include_credentials=True)
                if ctr_prov_ctx[K8S_PROVIDER_KEY] == K8sProvider.PKS:
                    pks_ctx_dict[ctr_prov_ctx['vc']] = ctr_prov_ctx

            pks_ctx_list = list(pks_ctx_dict.values())

        return pks_ctx_list
