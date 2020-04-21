# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

import container_service_extension.request_context as ctx


class AbstractBroker(abc.ABC):
    def __init__(self, request_context: ctx.RequestContext):
        self.context: ctx.RequestContext = request_context

    @abc.abstractmethod
    def create_cluster(self, data):
        """Create cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def delete_cluster(self, data):
        """Delete the given cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def get_cluster_info(self, data):
        """Get the information about the cluster.

        :return: response object

        :rtype: dict

        """

    @abc.abstractmethod
    def get_cluster_config(self, data):
        """Get the configuration for the cluster.

        :return: Configuration of cluster

        :rtype: dict

        """

    @abc.abstractmethod
    def list_clusters(self, data):
        """Get the list of clusters.

        :return: response object

        :rtype: list

        """
        pass

    @abc.abstractmethod
    def resize_cluster(self, data):
        """Scale the cluster.

        :return: response object

        :rtype: dict
        """
        pass
