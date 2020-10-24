# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import os

import pyvcloud.vcd.exceptions as vcd_exceptions
import yaml

import container_service_extension.client.constants as cli_constants
import container_service_extension.client.response_processor as response_processor  # noqa: E501
import container_service_extension.client.utils as client_utils
from container_service_extension.def_ import models as def_models
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.shared_constants as shared_constants


class DENativeCluster:
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param
        cluster resize where cluster kind specified as CLI param

    """

    def __init__(self, client):
        self._client = client
        self._uri = f"{self._client.get_api_uri()}/{shared_constants.CSE_URL_FRAGMENT}/{shared_constants.CSE_3_0_URL_FRAGMENT}"  # noqa: E501
        logger_wire = logger.NULL_LOGGER
        if os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING):
            logger_wire = logger.CLIENT_WIRE_LOGGER
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                client=client, logger_debug=logger.CLIENT_LOGGER,
                logger_wire=logger_wire)
        from container_service_extension.client.cse_client.api_35.native_cluster_api import NativeClusterApi
        self._native_cluster_api = NativeClusterApi(self._client)

    def create_cluster(self, cluster_entity: def_models.ClusterEntity):
        """Create a new Kubernetes cluster.

        :param models.ClusterEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    def resize_cluster(self, cluster_entity: def_models.ClusterEntity):
        """Resize the existing Kubernetes cluster.

        :param models.ClusterEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    def get_cluster_info(self, cluster_name, cluster_id=None,
                         org=None, vdc=None, **kwargs):
        """Get cluster information using DEF API.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster information
        :rtype: dict
        """
        if cluster_id:
            return self.get_cluster_info_by_id(cluster_id)
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        logger.CLIENT_LOGGER.debug(f"Defined entity info from server:{def_entity}")  # noqa: E501
        if not def_entity:
            logger.CLIENT_LOGGER.error(f"Cannot find native cluster with name {cluster_name}")  # noqa: E501
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        # TODO() relevant output
        if def_entity:
            return yaml.dump(asdict(def_entity.entity))

    def get_cluster_info_by_id(self, cluster_id, **kwargs):
        """Get cluster information by cluster ID.

        :param str cluster_id: ID of the cluster
        :return: cluster information in yaml format
        :rtype: str
        """
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_entity(cluster_id)
        logger.CLIENT_LOGGER.debug(f"Defined entity info from server: {def_entity}")  # noqa: E501
        return yaml.dump(asdict(def_entity.entity))

    def delete_cluster(self, cluster_name, cluster_id=None,
                       org=None, vdc=None):
        """Delete DEF native cluster by name.

        :param str cluster_name: native cluster name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: string containing delete operation task href
        :rtype: str
        :raises ClusterNotFoundError
        """
        if not cluster_id:
            filters = client_utils.construct_filters(org=org, vdc=vdc)
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
            if not def_entity:
                raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
            cluster_id = def_entity.id
        return self.delete_cluster_by_id(cluster_id)

    def delete_cluster_by_id(self, cluster_id, **kwargs):
        """Delete the existing Kubernetes cluster by id.

        :param str cluster_id: native cluster entity id
        :return: string containing the task for delete operation
        :rtype: str
        """
        cluster_entity = \
            self._native_cluster_api.delete_cluster_by_cluster_id(cluster_id)
        return client_utils.construct_task_console_message(cluster_entity.entity.status.task_href)  # noqa: E501

    def delete_nfs_node(self, cluster_name, node_name, org=None, vdc=None):
        """Delete nfs node given the cluster name and node name.

        :param str cluster_name: native cluster name
        :param str node_name: nfs-node name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: string containing delete operation task href
        :rtype: str
        :raises ClusterNotFoundError
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if def_entity:
            return self.delete_nfs_by_cluster_id(def_entity.id, node_name)
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def delete_nfs_by_cluster_id(self, cluster_id, node_name):
        """Delete the nfs-node by name from the given cluster id.

        :param str cluster_id: native cluster entity id
        :param str node_name: nfs-node name
        :return: string containing the task for delete operation
        :rtype: str
        """
        cluster_entity = \
            self._native_cluster_api.delete_nfs_node_by_node_name(cluster_id, node_name)
        return client_utils.construct_task_console_message(cluster_entity.entity.status.task_href)  # noqa: E501

    def get_cluster_config(self, cluster_name, cluster_id=None,
                           org=None, vdc=None):
        """Get cluster config for the given cluster name.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        if not cluster_id:
            filters = client_utils.construct_filters(org=org, vdc=vdc)
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
            if not def_entity:
                raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
            cluster_id = def_entity.id
        return self.get_cluster_config_by_id(cluster_id)

    def get_cluster_config_by_id(self, cluster_id, **kwargs):
        """Get the cluster config for given cluster id.

        :param str cluster_id: native cluster entity id
        :return: decoded response content
        :rtype: dict
        """
        return self._native_cluster_api.get_cluster_config_by_cluster_id(cluster_id)  # noqa: E501

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        """Get the upgrade plan for given cluster.

        :param cluster_name: name of the cluster
        :param org: name of the org
        :param vdc: name of the vdc
        :return: upgrade plan info
        :rtype: dict
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if def_entity:
            return self.get_upgrade_plan_by_cluster_id(def_entity.id)
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def get_upgrade_plan_by_cluster_id(self, cluster_id, **kwargs):
        """Get the upgrade plan for give cluster id.

        :param cluster_id: unique id of the cluster
        :return: decoded response content
        :rtype: list
        """
        return self._native_cluster_api.get_upgrade_plan_by_cluster_id(cluster_id)  # noqa: E501

    def upgrade_cluster(self, cluster_name, template_name,
                        template_revision, org_name=None, ovdc_name=None):
        """Get the upgrade plan for given cluster.

        :param str cluster_name: name of the cluster
        :param str template_name: Name of the template the cluster should be
        upgraded to.
        :param str template_revision: Revision of the template the cluster
        should be upgraded to.
        :param org_name: name of the org
        :param ovdc_name: name of the vdc
        :return: string containing upgrade cluster task href
        :rtype: str
        """
        filters = client_utils.construct_filters(org=org_name, vdc=ovdc_name)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        current_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if current_entity:
            current_entity.entity.spec.k8_distribution.template_name = template_name  # noqa: E501
            current_entity.entity.spec.k8_distribution.template_revision = template_revision  # noqa: E501
            return self.upgrade_cluster_by_cluster_id(current_entity.id, cluster_def_entity=asdict(current_entity))  # noqa: E501
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def upgrade_cluster_by_cluster_id(self, cluster_id, cluster_def_entity, **kwargs):  # noqa: E501
        """Get the upgrade plan for give cluster id.

        :param str cluster_id: unique id of the cluster
        :param dict cluster_def_entity: defined entity
        :return: string containing upgrade cluster task href
        :rtype: str
        """
        # TODO: check if we really need to decode-encode-decode-encode
        cluster_upgrade_definition = def_models.DefEntity(**cluster_def_entity)
        cluster_def_entity = self._native_cluster_api.upgrade_cluster_by_cluster_id(cluster_id, cluster_upgrade_definition)
        return client_utils.construct_task_console_message(cluster_def_entity.entity.status.task_href)  # noqa: E501

    def apply(self, cluster_config, cluster_id=None, **kwargs):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: dictionary containing the apply operation task
        :rtype: dict
        """
        uri = f"{self._uri}/clusters"
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        cluster_spec = def_models.ClusterEntity(**cluster_config)
        cluster_name = cluster_spec.metadata.cluster_name
        if cluster_id:
            # If cluster id doesn't exist, an exception will be raised
            def_entity = entity_svc.get_entity(cluster_id)
        else:
            def_entity = entity_svc.get_native_entity_by_name(cluster_name)
        if not def_entity:
            cluster_entity = self._native_cluster_api.create_cluster(cluster_spec)  # noqa: E501
        else:
            cluster_id = def_entity.id
            cluster_entity = \
                self._native_cluster_api.update_cluster_by_cluster_id(cluster_id, cluster_spec)  # noqa: E501
        return client_utils.construct_task_console_message(cluster_entity.entity.status.task_href)  # noqa: E501
