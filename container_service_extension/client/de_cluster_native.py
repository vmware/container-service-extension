# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os

import pyvcloud.vcd.exceptions as vcd_exceptions
import semantic_version
import yaml

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.cse_client.api_35.native_cluster_api import NativeClusterApi  # noqa: E501
import container_service_extension.client.utils as client_utils
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.exception.exceptions as cse_exceptions
import container_service_extension.logging.logger as logger
import container_service_extension.rde.common.entity_service as def_entity_svc
import container_service_extension.rde.constants as rde_constants
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0
import container_service_extension.rde.schema_service as def_schema_svc


class DEClusterNative:
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param
        cluster resize where cluster kind specified as CLI param

    """

    def __init__(self, client):
        logger_wire = logger.NULL_LOGGER
        if os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING):
            logger_wire = logger.CLIENT_WIRE_LOGGER
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                client=client, logger_debug=logger.CLIENT_LOGGER,
                logger_wire=logger_wire)
        self._native_cluster_api = NativeClusterApi(client)
        self._client = client
        schema_service = def_schema_svc.DefSchemaService(self._cloudapi_client)
        self._server_rde_version = \
            schema_service.get_latest_registered_schema_version()

    def create_cluster(self, cluster_entity: rde_1_0_0.NativeEntity):
        """Create a new Kubernetes cluster.

        :param models.NativeEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    def resize_cluster(self, cluster_entity: rde_1_0_0.NativeEntity):
        """Resize the existing Kubernetes cluster.

        :param models.NativeEntity cluster_entity: native cluster entity
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
        filters = client_utils.construct_filters(
            self._server_rde_version, org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = \
            entity_svc.get_native_rde_by_name_and_rde_version(
                cluster_name, self._server_rde_version, filters=filters)  # noqa: E501
        logger.CLIENT_LOGGER.debug(f"Defined entity info from server:{def_entity}")  # noqa: E501
        if not def_entity:
            logger.CLIENT_LOGGER.error(f"Cannot find native cluster with name {cluster_name}")  # noqa: E501
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        # TODO() relevant output
        if def_entity:
            return yaml.dump(def_entity.entity.to_dict())

    def get_cluster_info_by_id(self, cluster_id, **kwargs):
        """Get cluster information by cluster ID.

        :param str cluster_id: ID of the cluster
        :return: cluster information in yaml format
        :rtype: str
        """
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_entity(cluster_id)
        logger.CLIENT_LOGGER.debug(f"Defined entity info from server: {def_entity}")  # noqa: E501
        return yaml.dump(def_entity.entity.to_dict())

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
            cluster_id = self.get_cluster_id_by_name(cluster_name, org, vdc)
        return self.delete_cluster_by_id(cluster_id)

    def delete_cluster_by_id(self, cluster_id, **kwargs):
        """Delete the existing Kubernetes cluster by id.

        :param str cluster_id: native cluster entity id
        :return: string containing the task for delete operation
        :rtype: str
        """
        cluster_entity = \
            self._native_cluster_api.delete_cluster_by_cluster_id(cluster_id)
        task_href = cluster_entity.entity.status.task_href
        return client_utils.construct_task_console_message(task_href)  # noqa: E501

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
        filters = client_utils.construct_filters(
            self._server_rde_version, org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_rde_by_name_and_rde_version(
            cluster_name, self._server_rde_version, filters=filters)
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
            self._native_cluster_api.delete_nfs_node_by_node_name(cluster_id,
                                                                  node_name)
        task_href = cluster_entity.entity.status.task_href
        return client_utils.construct_task_console_message(task_href)

    def get_cluster_config(self, cluster_name, cluster_id=None,
                           org=None, vdc=None):
        """Get cluster config for the given cluster name.

        :param str cluster_name: name of the cluster
        :param str cluster_id: id of the cluster
        :param str vdc: name of vdc
        :param str org: name of org

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        if not cluster_id:
            cluster_id = self.get_cluster_id_by_name(cluster_name, org, vdc)
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
        filters = client_utils.construct_filters(
            self._server_rde_version, org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_rde_by_name_and_rde_version(
            cluster_name, self._server_rde_version, filters=filters)
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
        filters = client_utils.construct_filters(
            self._server_rde_version, org=org_name, vdc=ovdc_name)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        current_entity = entity_svc.get_native_rde_by_name_and_rde_version(
            cluster_name, self._server_rde_version, filters=filters)
        # NOTE: This function is only valid when the CSE server is running
        # with RDE 1.0.0
        if current_entity:
            current_entity.entity.spec.k8_distribution.template_name = template_name  # noqa: E501
            current_entity.entity.spec.k8_distribution.template_revision = template_revision  # noqa: E501
            return self.upgrade_cluster_by_cluster_id(current_entity.id, cluster_def_entity=current_entity.to_dict())  # noqa: E501
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def upgrade_cluster_by_cluster_id(self, cluster_id, cluster_def_entity, **kwargs):  # noqa: E501
        """Get the upgrade plan for give cluster id.

        :param str cluster_id: unique id of the cluster
        :param dict cluster_def_entity: defined entity
        :return: string containing upgrade cluster task href
        :rtype: str
        """
        # TODO: check if we really need to decode-encode-decode-encode
        cluster_upgrade_definition = common_models.DefEntity(**cluster_def_entity)  # noqa: E501
        cluster_def_entity = \
            self._native_cluster_api.upgrade_cluster_by_cluster_id(
                cluster_id, cluster_upgrade_definition)
        task_href = cluster_def_entity.entity.status.task_href
        return client_utils.construct_task_console_message(task_href)

    def _get_cluster_name_from_cluster_apply_specification(self, input_spec: dict):  # noqa: E501
        """Derive cluster name from cluster apply specificaiton.

        :param dict input_spec: Input specification
        :return: cluster name
        :rtype: str
        """
        # RDE version > 1.0.0 will have the cluster name under metadata.name
        metadata: dict = input_spec.get('metadata')
        if semantic_version.Version(self._server_rde_version) <= \
                semantic_version.Version(rde_constants.RDEVersion.RDE_1_0_0):
            return metadata.get('cluster_name')
        return metadata.get('name')

    def apply(self, cluster_apply_spec: dict, cluster_id: str = None, **kwargs):  # noqa: E501
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: dictionary containing the apply operation task
        :rtype: dict
        """
        cluster_name = \
            self._get_cluster_name_from_cluster_apply_specification(cluster_apply_spec)  # noqa: E501
        # cluster name should not be missing from the apply specification
        if not cluster_name:
            raise Exception('Cluster name missing in the cluster apply specification')  # noqa: E501
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        if cluster_id:
            # If cluster id doesn't exist, an exception will be raised
            def_entity = entity_svc.get_entity(cluster_id)
        else:
            def_entity = entity_svc.get_native_rde_by_name_and_rde_version(
                cluster_name, self._server_rde_version)
        if not def_entity:
            cluster_def_entity = self._native_cluster_api.create_cluster(
                cluster_apply_spec)
        else:
            cluster_id = def_entity.id
            cluster_def_entity = \
                self._native_cluster_api.update_cluster_by_cluster_id(
                    cluster_id, cluster_apply_spec)
        task_href = cluster_def_entity.entity.status.task_href
        return client_utils.construct_task_console_message(task_href)

    def get_cluster_id_by_name(self, cluster_name, org=None, vdc=None):
        filters = client_utils.construct_filters(
            self._server_rde_version, org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_rde_by_name_and_rde_version(
            cluster_name, self._server_rde_version, filters=filters)
        if not def_entity:
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        return def_entity.id

    def share_cluster(self, cluster_id, cluster_name, users: list,
                      access_level_id, org, vdc):
        """Share cluster with passed in users."""
        if not cluster_id:
            cluster_id = self.get_cluster_id_by_name(cluster_name, org, vdc)
        org_href = self._client.get_org_by_name(org).get('href')
        name_to_id: dict = client_utils.create_user_name_to_id_dict(
            self._client, users, org_href)

        # Parse user id info
        update_acl_entries = []
        for username, user_id in name_to_id.items():
            acl_entry = common_models.ClusterAclEntry(
                memberId=user_id,
                username=username,
                accessLevelId=access_level_id)
            update_acl_entries.append(acl_entry)

        # Only retain entries that are not updated
        for acl_entry in self._native_cluster_api.\
                list_native_cluster_acl_entries(cluster_id):
            username = acl_entry.username
            if name_to_id.get(username):
                # Check that access level is not reduced
                curr_access_level_id = acl_entry.accessLevelId
                if client_utils.access_level_reduced(
                        access_level_id, curr_access_level_id):
                    raise Exception(f'{username} currently has higher access '
                                    f'level: {curr_access_level_id}')
            else:
                update_acl_entries.append(acl_entry)

        update_acl_values = \
            [acl_entry.construct_filtered_dict(include=cli_constants.CLUSTER_ACL_UPDATE_REQUEST_FIELDS)  # noqa: E501
             for acl_entry in update_acl_entries]
        self._native_cluster_api.put_cluster_acl(cluster_id, update_acl_values)

    def unshare_cluster(self, cluster_id, cluster_name, users: list, org=None,
                        vdc=None):
        if not cluster_id:
            cluster_id = self.get_cluster_id_by_name(cluster_name, org, vdc)

        delete_users_set = set(users)
        updated_acl_entries = []
        for acl_entry in self._native_cluster_api.\
                list_native_cluster_acl_entries(cluster_id):
            if acl_entry.username not in delete_users_set:
                acl_dict = acl_entry.construct_filtered_dict(
                    include=cli_constants.CLUSTER_ACL_UPDATE_REQUEST_FIELDS)
                updated_acl_entries.append(acl_dict)
            else:
                delete_users_set.remove(acl_entry.username)

        if len(delete_users_set) > 0:
            raise Exception(f'Cluster {cluster_name or cluster_id} is not '
                            f'currently shared with: {list(delete_users_set)}')

        self._native_cluster_api.put_cluster_acl(cluster_id, updated_acl_entries)  # noqa: E501

    def list_share_entries(self, cluster_id, cluster_name, org=None, vdc=None):
        if not cluster_id:
            cluster_id = self.get_cluster_id_by_name(cluster_name, org, vdc)
        result_count = page_num = 0
        while True:
            page_num += 1
            response_body = self._native_cluster_api.get_single_page_cluster_acl(  # noqa: E501
                cluster_id=cluster_id,
                page=page_num,
                page_size=cli_constants.CLI_ENTRIES_PER_PAGE)
            result_total = response_body[shared_constants.PaginationKey.RESULT_TOTAL]  # noqa: E501
            acl_values = response_body[shared_constants.PaginationKey.VALUES]
            if not acl_values:
                break
            result_count += len(acl_values)
            yield acl_values, result_count < result_total
