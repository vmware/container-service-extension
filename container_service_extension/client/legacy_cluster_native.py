# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.client.cse_client.api_33.native_cluster_api as native_cluster_api_v33  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.logging.logger import CLIENT_LOGGER


class LegacyClusterNative:
    def __init__(self, client):
        self._native_cluster_api = \
            native_cluster_api_v33.NativeClusterApi(client)

    def list_clusters(self, vdc=None, org=None):
        filters = {
            shared_constants.RequestKey.ORG_NAME: org,
            shared_constants.RequestKey.OVDC_NAME: vdc}
        for clusters_rep, has_more_results in \
                self._native_cluster_api.get_all_clusters(filters=filters):
            clusters = []
            CLIENT_LOGGER.debug(clusters_rep)
            for c in clusters_rep:
                # TODO cluster api response keys need to be more well defined
                cluster = {
                    'Name': c.get('name', 'N/A'),
                    'Owner': c.get('owner_name', 'N/A'),
                    'VDC': c.get('vdc', 'N/A'),
                    'Org': c.get('org_name', 'N/A'),
                    'K8s Runtime': c.get('k8s_type', 'N/A'),
                    'K8s Version': c.get('k8s_version', 'N/A'),
                    'Status': c.get('status', 'N/A'),
                    'Provider': c.get('k8s_provider', 'N/A'),
                }
                clusters.append(cluster)
            yield clusters, has_more_results

    def get_cluster_info(self, name, org=None, vdc=None, **kwargs):
        filters = {shared_constants.RequestKey.ORG_NAME: org,
                   shared_constants.RequestKey.OVDC_NAME: vdc}
        return self._native_cluster_api.get_cluster(name, filters=filters)

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        filters = {shared_constants.RequestKey.ORG_NAME: org,
                   shared_constants.RequestKey.OVDC_NAME: vdc}
        return self._native_cluster_api.get_cluster_upgrade_plan(cluster_name,
                                                                 filters=filters)  # noqa: E501

    def upgrade_cluster(self, cluster_name, template_name, template_revision,
                        org_name=None, ovdc_name=None):
        return self._native_cluster_api.upgrade_cluster(cluster_name,
                                                        template_name,
                                                        template_revision,
                                                        org_name=org_name,
                                                        ovdc_name=ovdc_name)

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
        :param org: (str): name of the organization in which the vdc to be
        used for cluster creation.

        :return: (json) A parsed json object describing the requested cluster.
        """
        return self._native_cluster_api.create_cluster(name, vdc, network_name,
                                                       node_count=node_count,
                                                       org_name=org,
                                                       cpu=cpu,
                                                       memory=memory,
                                                       storage_profile=storage_profile,  # noqa: E501
                                                       ssh_key=ssh_key,
                                                       template_name=template_name,  # noqa: E501
                                                       template_revision=template_revision,  # noqa: E501
                                                       enable_nfs=enable_nfs,
                                                       rollback=rollback)

    def resize_cluster(self,
                       network_name,
                       cluster_name,
                       node_count,
                       org=None,
                       vdc=None,
                       rollback=True,
                       template_name=None,
                       template_revision=None,
                       cpu=None,
                       memory=None,
                       ssh_key=None):
        return self._native_cluster_api.update_cluster(cluster_name,
                                                       network_name,
                                                       node_count,
                                                       org_name=org,
                                                       ovdc_name=vdc,
                                                       template_name=template_name,  # noqa: E501
                                                       template_revision=template_revision,  # noqa: E501
                                                       cpu=cpu,
                                                       memory=memory,
                                                       ssh_key=ssh_key,
                                                       rollback=rollback)

    def delete_cluster(self, cluster_name, org=None, vdc=None, **kwargs):
        filters = {
            shared_constants.RequestKey.ORG_NAME: org,
            shared_constants.RequestKey.OVDC_NAME: vdc
        }
        return self._native_cluster_api.delete_cluster(cluster_name,
                                                       filters=filters)

    def get_cluster_config(self, cluster_name, org=None, vdc=None, **kwargs):
        filters = {shared_constants.RequestKey.ORG_NAME: org,
                   shared_constants.RequestKey.OVDC_NAME: vdc}
        return self._native_cluster_api.get_cluster_config(cluster_name,
                                                           filters=filters)

    def get_node_info(self, cluster_name, node_name, org=None, vdc=None):
        filters = {
            shared_constants.RequestKey.ORG_NAME: org,
            shared_constants.RequestKey.OVDC_NAME: vdc,
        }
        return self._native_cluster_api.get_node_info(cluster_name, node_name,
                                                      filters=filters)

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
        return self._native_cluster_api.add_node(cluster_name, network_name,
                                                 node_count=node_count,
                                                 org_name=org,
                                                 ovdc_name=vdc,
                                                 cpu=cpu,
                                                 memory=memory,
                                                 storage_profile=storage_profile,  # noqa: E501
                                                 ssh_key=ssh_key,
                                                 template_name=template_name,
                                                 template_revision=template_revision)  # noqa: E501

    def delete_nodes(self, cluster_name, nodes, org=None, vdc=None):
        """Delete nodes from a Kubernetes cluster.

        :param str org: Name of the organization that contains the cluster
        :param str vdc: The name of the vdc that contains the cluster
        :param str cluster_name: The name of the cluster
        :param list nodes: The list of nodes to delete

        :return: (json) A parsed json object describing the requested cluster
            operation.
        """
        return self._native_cluster_api.delete_nodes(cluster_name,
                                                     nodes,
                                                     org_name=org,
                                                     ovdc_name=vdc)
