# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException


class DefNativeCluster:
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param

    """

    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

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
        :param pks_ext_host: (str): Address from which to access the Kubernetes
        API for PKS.
        :param pks_plan: (str): Preconfigured PKS plan to use for deploying the
        cluster.
        :param org: (str): name of the organization in which the vdc to be
        used for cluster creation.

        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)

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
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)

    def apply(self, cluster_config_file_path):
        uri = f"{self._uri}/internal/clusters"
        msg = f"Operation not supported; Implementation in progress for {uri}"
        raise(OperationNotSupportedException(msg))

    def __getattr__(self, name):
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)
