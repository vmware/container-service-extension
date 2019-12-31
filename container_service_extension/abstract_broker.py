# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

from pyvcloud.vcd.client import _WellKnownEndpoint

import container_service_extension.pyvcloud_utils as vcd_utils


class AbstractBroker(abc.ABC):

    def __init__(self, tenant_auth_token, is_jwt_token):
        self.tenant_client = None
        self.client_session = None
        self.tenant_user_name = None
        self.tenant_user_id = None
        self.tenant_org_name = None
        self.tenant_org_href = None

        self.tenant_client = vcd_utils.connect_vcd_user_via_token(
            tenant_auth_token=tenant_auth_token,
            is_jwt_token=is_jwt_token)
        self.client_session = self.tenant_client.get_vcloud_session()
        self.tenant_user_name = self.client_session.get('user')
        self.tenant_user_id = self.client_session.get('userId')
        self.tenant_org_name = self.client_session.get('org')
        self.tenant_org_href = \
            self.tenant_client._get_wk_endpoint(_WellKnownEndpoint.LOGGED_IN_ORG) # noqa: E501

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
