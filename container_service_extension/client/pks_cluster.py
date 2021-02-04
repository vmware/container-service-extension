# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.cse_client.pks_cluster_api import PksClusterApi  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class PksCluster:
    def __init__(self, client):
        self._pks_cluster_api = PksClusterApi(client)

    def get_clusters(self, vdc=None, org=None):
        filters = {
            shared_constants.RequestKey.ORG_NAME: org,
            shared_constants.RequestKey.OVDC_NAME: vdc
        }
        return self._pks_cluster_api.list_clusters(filters=filters)

    def get_cluster_info(self, name, org=None, vdc=None):
        filters = {
            shared_constants.RequestKey.ORG_NAME: org,
            shared_constants.RequestKey.OVDC_NAME: vdc
        }
        return self._pks_cluster_api.get_cluster(name, filters=filters)

    def create_cluster(self,
                       vdc,
                       name,
                       node_count=None,
                       org=None):
        """Create a new Kubernetes cluster.

        :param vdc: (str): The name of the vdc in which the cluster will be
            created
        :param name: (str): The name of the cluster
        :param node_count: (str): Number of nodes
        :param org: (str): name of the organization in which the vdc to be
        used for cluster creation.

        :return: (json) A parsed json object describing the requested cluster.
        """
        return self._pks_cluster_api.create_cluster(name, vdc,
                                                    node_count=node_count,
                                                    org_name=org)

    def resize_cluster(self,
                       cluster_name,
                       node_count,
                       org=None,
                       vdc=None):
        return self._pks_cluster_api.update_cluster(cluster_name, node_count,
                                                    org_name=org,
                                                    ovdc_name=vdc)

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        return self._pks_cluster_api.delete_cluster(cluster_name,
                                                    org_name=org,
                                                    ovdc_name=vdc)

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        return self._pks_cluster_api.get_cluster_config(cluster_name,
                                                        org_name=org,
                                                        ovdc_name=vdc)
