# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc


class AbstractBroker(abc.ABC):
    @abc.abstractmethod
    def get_tenant_client_session(self):
        """Return <Session> XML object of a logged in vCD user.

        :return: the session of the tenant user.

        :rtype: lxml.objectify.ObjectifiedElement containing <Session> XML
            data.
        """
        pass

    @abc.abstractmethod
    def create_cluster(self, *args, **kwargs):
        """Create cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def create_nodes(self, *args, **kwargs):
        """Create nodes from the cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def delete_cluster(self, *args, **kwargs):
        """Delete the given cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def delete_nodes(self, *args, **kwargs):
        """Create nodes from the cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def get_cluster_config(self, name):
        """Get the configuration of cluster.

        :return: response object

        :rtype: dict

        """
        pass

    @abc.abstractmethod
    def get_cluster_info(self, name):
        """Get the information about the cluster.

        :return: response object

        :rtype: dict

        """

    @abc.abstractmethod
    def get_node_info(self, cluster_name, node_name):
        """Get information of node in the given cluster.

        :return: response object

        :rtype: dict

        """
        pass

    @abc.abstractmethod
    def list_clusters(self):
        """Get the list of clusters.

        :return: response object

        :rtype: dict
        """
        pass
