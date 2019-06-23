# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

from pyvcloud.vcd.client import _WellKnownEndpoint

from container_service_extension.pyvcloud_utils import \
    connect_vcd_user_via_token


class AbstractBroker(abc.ABC):

    def __init__(self, tenant_auth_token, request_spec):
        self.tenant_auth_token = tenant_auth_token
        self.req_spec = request_spec
        self.client_session = None
        self.tenant_info = None

    @abc.abstractmethod
    def create_cluster(self):
        """Create cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def delete_cluster(self):
        """Delete the given cluster.

        :return: response object

        :rtype: dict
        """
        pass

    @abc.abstractmethod
    def get_cluster_info(self):
        """Get the information about the cluster.

        :return: response object

        :rtype: dict

        """

    @abc.abstractmethod
    def get_cluster_config(self, cluster_name):
        """Get the configuration for the cluster.

        :param: str cluster_name: Name of the cluster.

        :return: Configuration of cluster

        :rtype: dict

        """

    @abc.abstractmethod
    def list_clusters(self):
        """Get the list of clusters.

        :return: response object

        :rtype: dict

        """
        pass

    @abc.abstractmethod
    def resize_cluster(self):
        """Scale the cluster.

        :return: response object

        :rtype: dict
        """
        pass

    def get_tenant_client_session(self):
        """Return <Session> XML object of a logged in vCD user.

        :return: the session of the tenant user.

        :rtype: lxml.objectify.ObjectifiedElement containing <Session> XML
            data.
        """
        if self.client_session is None:
            self._connect_tenant()
        return self.client_session

    def _connect_tenant(self):
        self.tenant_client, self.client_session = connect_vcd_user_via_token(
            tenant_auth_token=self.tenant_auth_token)
        self.tenant_info = {
            'user_name': self.client_session.get('user'),
            'user_id': self.client_session.get('userId'),
            'org_name': self.client_session.get('org'),
            'org_href': self.tenant_client._get_wk_endpoint(
                _WellKnownEndpoint.LOGGED_IN_ORG)
        }
