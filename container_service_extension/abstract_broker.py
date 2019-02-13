# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc

from pyvcloud.vcd.client import _WellKnownEndpoint

from container_service_extension.utils import connect_vcd_user_via_token
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import get_vcd_sys_admin_client


class AbstractBroker(abc.ABC):

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
        server_config = get_server_runtime_config()
        host = server_config['vcd']['host']
        verify = server_config['vcd']['verify']
        self.tenant_client, self.client_session = connect_vcd_user_via_token(
            vcd_uri=host,
            headers=self.headers,
            verify_ssl_certs=verify)
        self.tenant_info = {
            'user_name': self.client_session.get('user'),
            'user_id': self.client_session.get('userId'),
            'org_name': self.client_session.get('org'),
            'org_href': self.tenant_client._get_wk_endpoint(
                _WellKnownEndpoint.LOGGED_IN_ORG)
        }

    def _connect_sys_admin(self):
        self.sys_admin_client = get_vcd_sys_admin_client()

    def _disconnect_sys_admin(self):
        if self.sys_admin_client is not None:
            self.sys_admin_client.logout()
            self.sys_admin_client = None
