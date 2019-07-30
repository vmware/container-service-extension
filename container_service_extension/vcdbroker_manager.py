# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import CseDuplicateClusterError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.shared_constants import RequestKey
from container_service_extension.vcdbroker import VcdBroker


class VcdBrokerManager:
    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec

    def list_clusters(self):
        vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
        vcd_clusters = []
        for cluster in vcd_broker.list_clusters():
            vcd_clusters.append(cluster)
        return vcd_clusters

    def find_cluster_in_org(self):
        """Invoke vCD broker to find the cluster in the org.

        If cluster found:
            Return a tuple of (cluster and the broker instance used to find
            the cluster)
        Else:
            (None, None) if cluster not found.
        """
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]
        vcd_broker = VcdBroker(self.tenant_auth_token, self.req_spec)
        try:
            return vcd_broker.get_cluster_info(), vcd_broker
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
