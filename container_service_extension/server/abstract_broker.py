# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

import container_service_extension.security.context.operation_context as ctx


class AbstractBroker(abc.ABC):
    def __init__(self, op_ctx: ctx.OperationContext):
        self.context: ctx.OperationContext = op_ctx

    @abc.abstractmethod
    def create_cluster(self, **kwargs):
        """Create cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def delete_cluster(self, **kwargs):
        """Delete the given cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def get_cluster_info(self, **kwargs):
        """Get the information about the cluster.

        :return: response object

        :rtype: dict

        """

    @abc.abstractmethod
    def get_cluster_config(self, **kwargs):
        """Get the configuration for the cluster.

        :return: Configuration of cluster

        :rtype: dict

        """

    @abc.abstractmethod
    def list_clusters(self, **kwargs):
        """Get the list of clusters.

        :return: response object

        :rtype: list

        """
        pass

    @abc.abstractmethod
    def resize_cluster(self, **kwargs):
        """Scale the cluster.

        :return: response object

        :rtype: dict
        """
        pass
