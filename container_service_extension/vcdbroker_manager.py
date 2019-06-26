# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseDuplicateClusterError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProviders
from container_service_extension.vcdbroker import VcdBroker


class VcdBrokerManager(object):
    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec

    def list_clusters(self):
        vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
        vcd_clusters = []
        for cluster in vcd_broker.list_clusters():
            cluster[K8S_PROVIDER_KEY] = K8sProviders.NATIVE
            vcd_clusters.append(cluster)
        return vcd_clusters

    def find_cluster_in_org(self, cluster_name, is_org_admin_search=False):
        """Invoke vCD broker to find the cluster in the org.

        'is_org_admin_search' is used here to prevent cluster creation with
        same cluster-name by users within org. If it is true,
        cluster list is filtered by the org name of the logged-in user.

        If cluster found:
            Return a tuple of (cluster and the broker instance used to find
            the cluster)
        Else:
            (None, None) if cluster not found.
        """
        vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
        try:
            return vcd_broker.get_cluster_info(cluster_name), vcd_broker
        except ClusterNotFoundError as err:
            # If a cluster is not found, then broker_manager will
            # decide if it wants to raise an error or ignore it if was it just
            # scanning the broker to check if it can handle the cluster request
            # or not.
            LOGGER.debug(f"Get cluster info on {cluster_name}"
                         f"on vCD failed with error: {err}")
        except CseDuplicateClusterError as err:
            LOGGER.debug(f"Get cluster info on {cluster_name}"
                         f"on vCD failed with error: {err}")
            raise
        except Exception as err:
            LOGGER.debug(f"Get cluster info on {cluster_name} failed "
                         f"on vCD with error: {err}")
        return None, None
