# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import os
from typing import List

import requests
import yaml

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.de_cluster_native import DEClusterNative  # noqa: E501
from container_service_extension.client.de_cluster_tkg_s import DEClusterTKGS
import container_service_extension.client.tkgclient.rest as tkg_rest
import container_service_extension.client.utils as client_utils
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE, PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.exception.exceptions as cse_exceptions
import container_service_extension.logging.logger as logger
import container_service_extension.rde.common.entity_service as def_entity_svc
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.schema_service as def_schema_svc


DUPLICATE_CLUSTER_ERROR_MSG = "Duplicate clusters found. Please use --k8-runtime for the unique identification"  # noqa: E501


class DECluster:
    """Handle operations common to DefNative and TKG-S kubernetes clusters.

    Also any operation where cluster kind is not supplied should be handled here.  # noqa: E501

    Example(s):
        cluster list is a collection which may have mix of DefNative and
        TKG-S clusters.

        cluster info for a given cluster name needs lookup using DEF API.
    """

    def __init__(self, client):
        logger_wire = logger.NULL_LOGGER
        if os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING):
            logger_wire = logger.CLIENT_WIRE_LOGGER
        self._client = client
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                client=client, logger_debug=logger.CLIENT_LOGGER,
                logger_wire=logger_wire)
        self._nativeCluster = DEClusterNative(client)
        self._tkgCluster = DEClusterTKGS(client)
        schema_svc = def_schema_svc.DefSchemaService(self._cloudapi_client)
        self._server_rde_version = \
            schema_svc.get_latest_registered_schema_version()

    def list_clusters(self, vdc=None, org=None, **kwargs):
        """Get collection of clusters using DEF API.

        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster list information
        :rtype: list(dict)
        """
        if client_utils.is_cli_for_tkg_s_only():
            try:
                for clusters, has_more_results in \
                        self._tkgCluster.list_tkg_s_clusters(vdc=vdc, org=org):
                    yield clusters, has_more_results
            except tkg_rest.ApiException as e:
                if e.status not in [requests.codes.FORBIDDEN, requests.codes.UNAUTHORIZED]:  # noqa: E501
                    server_message = json.loads(e.body).get('message') or e.reason  # noqa: E501
                    msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{server_message}")  # noqa: E501
                    logger.CLIENT_LOGGER.error(msg)
                    raise Exception(msg)
                msg = f"User not authorized to fetch TKG-S clusters: {e}"
                logger.CLIENT_LOGGER.debug(msg)
                raise e
        else:
            # display all clusters
            filters = client_utils.construct_filters(
                self._server_rde_version, org=org, vdc=vdc)
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            has_more_results = True
            page_number = CSE_PAGINATION_FIRST_PAGE_NUMBER
            page_size = CSE_PAGINATION_DEFAULT_PAGE_SIZE
            try:
                while has_more_results:
                    clusters_page_results = entity_svc.get_all_entities_per_page_by_interface(  # noqa: E501
                        vendor=common_models.K8Interface.VCD_INTERFACE.value.vendor,  # noqa: E501
                        nss=common_models.K8Interface.VCD_INTERFACE.value.nss,
                        version=common_models.K8Interface.VCD_INTERFACE.value.version,  # noqa: E501
                        filters=filters,
                        page_number=page_number,
                        page_size=page_size)
                    # Get the list of cluster defined entities
                    entities: List[common_models.GenericClusterEntity] = clusters_page_results[PaginationKey.VALUES]  # noqa: E501
                    clusters = []
                    for de in entities:
                        entity = de.entity
                        logger.CLIENT_LOGGER.debug(f"Native Defined entity list from server: {entity}")  # noqa: E501
                        cluster = {
                            cli_constants.CLIOutputKey.CLUSTER_NAME.value: de.name,  # noqa: E501
                            cli_constants.CLIOutputKey.ORG.value: de.org.name,  # noqa: E501
                            cli_constants.CLIOutputKey.OWNER.value: de.owner.name  # noqa: E501
                        }
                        if isinstance(entity, AbstractNativeEntity):
                            if hasattr(entity.metadata, 'ovdc_name'):
                                cluster[cli_constants.CLIOutputKey.VDC.value] = \
                                    entity.metadata.ovdc_name  # noqa: E501
                            elif hasattr(entity.metadata, 'virtual_data_center_name'):  # noqa: E501
                                cluster[cli_constants.CLIOutputKey.VDC.value] = \
                                    entity.metadata.virtual_data_center_name  # noqa: E501
                            cluster[cli_constants.CLIOutputKey.K8S_RUNTIME.value] = entity.kind  # noqa: E501
                            cluster[cli_constants.CLIOutputKey.K8S_VERSION.value] = entity.status.kubernetes  # noqa: E501
                            cluster[cli_constants.CLIOutputKey.STATUS.value] = entity.status.phase  # noqa: E501
                        elif isinstance(entity, common_models.TKGEntity):
                            cluster[cli_constants.CLIOutputKey.VDC.value] = \
                                entity.metadata.virtualDataCenterName
                            cluster[cli_constants.CLIOutputKey.K8S_RUNTIME.value] = entity.kind  # noqa: E501
                            cluster[cli_constants.CLIOutputKey.K8S_VERSION.value] = entity.spec.distribution.version  # noqa: E501
                            cluster[cli_constants.CLIOutputKey.STATUS.value] = \
                                entity.status.phase if entity.status else 'N/A'  # noqa: E501
                        clusters.append(cluster)
                    has_more_results = page_number * page_size < \
                        clusters_page_results[PaginationKey.RESULT_TOTAL]
                    yield clusters, has_more_results
                    page_number += 1
            except requests.exceptions.HTTPError as e:
                msg = f"Failed to fetch clusters: {e}"
                logger.CLIENT_LOGGER.debug(msg)
                raise e

    def _get_tkg_s_and_native_clusters_by_name(self, cluster_name: str,
                                               org=None, vdc=None):
        """Get native and TKG-S clusters by name.

        Assumption: Native clusters cannot have name collision among them.
        But there can be multiple TKG-S clusters with the same name and 2 or
        more TKG-S clusters can also have the same name.

        :param str cluster_name: Cluster name to search for
        :param str org: Org to filter by
        :param str vdc: VDC to filter by
        :returns: TKG-S entity or native def entity with entity properties and
            boolean indicating cluster type
        :rtype: (cluster, dict,  bool)
        """
        filters = client_utils.construct_filters(
            self._server_rde_version, org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        has_native_rights = True
        has_tkg_rights = True
        native_def_entity = None
        additional_entity_properties = None
        # NOTE: The following can throw error if invoked by users who
        # doesn't have the necessary rights.
        try:
            native_def_entity = \
                entity_svc.get_native_rde_by_name_and_rde_version(
                    cluster_name, self._server_rde_version,
                    filters=filters)
        except cse_exceptions.DefSchemaServiceError:
            # NOTE: 500 status code is returned which is not ideal
            # when user doesn't have native rights
            has_native_rights = False

        tkg_entity = []
        tkg_def_entity = []
        # NOTE: The following can throw error if invoked by users who
        # doesn't have the necessary rights.
        try:
            tkg_entity, tkg_def_entity = \
                self._tkgCluster.get_tkg_s_clusters_by_name(cluster_name,
                                                            vdc=vdc, org=org)
        except tkg_rest.ApiException as e:
            if e.status not in [requests.codes.FORBIDDEN, requests.codes.UNAUTHORIZED]:  # noqa: E501
                raise
            has_tkg_rights = False
        except cse_exceptions.ClusterNotFoundError:
            logger.CLIENT_LOGGER.debug(f"No TKG-S cluster with name {cluster_name}")  # noqa: E501
        if not (has_native_rights or has_tkg_rights):
            raise Exception("User cannot access native or TKG clusters."
                            " Please contact administrator")
        msg = "Multiple clusters with the same name found."
        if len(tkg_entity) > 0 and native_def_entity:
            # If org filter is not provided, ask the user to provide org
            # filter
            if not org:
                # handles the case where there are TKG-S clusters and native
                # clusters with the same name in different organizations
                raise Exception(f"{msg} Please specify the org to use "
                                "using --org flag.")
            # handles the case where there is a TKG-S cluster and a native
            # native cluster with the same name in the same organization
            raise Exception(f"{msg} Please specify the k8-runtime to use using"
                            " --k8-runtime flag.")
        if not native_def_entity and len(tkg_entity) == 0:
            # handles the case where no clusters are found
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        if native_def_entity:
            cluster = native_def_entity
            is_native_cluster = True
        else:
            additional_entity_properties = tkg_def_entity[0]
            cluster = tkg_entity[0]
            is_native_cluster = False

        return cluster, additional_entity_properties, is_native_cluster

    def get_cluster_info(self, cluster_name, cluster_id=None,
                         org=None, vdc=None, **kwargs):
        """Get cluster information using DEF API.

        :param str cluster_name: name of the cluster
        :param str cluster_id:
        :param str org: name of org
        :param str vdc: name of vdc
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        # TODO(Display Owner information): Owner information needs to be
        # displayed
        if cluster_id:
            return self.get_cluster_info_by_id(cluster_id, org=org)
        cluster, _, is_native_cluster = \
            self._get_tkg_s_and_native_clusters_by_name(cluster_name,
                                                        org=org, vdc=vdc)
        if is_native_cluster:
            cluster_info = cluster.entity.to_dict()
        else:
            # TKG-S cluster represents the defined_entity.entity
            cluster_info = client_utils.swagger_object_to_dict(cluster)
        logger.CLIENT_LOGGER.debug(
            f"Received defined entity of cluster {cluster_name} : {cluster_info}")  # noqa: E501
        return yaml.dump(cluster_info)

    def get_cluster_info_by_id(self, cluster_id, org=None):
        """Obtain cluster information using cluster ID.

        :param str cluster_id:
        :param str org:

        :return: yaml representation of the cluster information
        :rtype: str
        """
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        if entity_svc.is_native_entity(cluster_id):
            return self._nativeCluster.get_cluster_info_by_id(cluster_id=cluster_id)  # noqa: E501
        return self._tkgCluster.get_cluster_info_by_id(cluster_id, org=org)  # noqa: E501

    def get_cluster_config(self, cluster_name, cluster_id=None,
                           org=None, vdc=None):
        """Get cluster config.

        :param str cluster_name: name of the cluster
        :param str cluster_id:
        :param str org: name of org
        :param str vdc: name of vdc


        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        if cluster_id:
            return self.get_cluster_config_by_id(cluster_id, org=org)
        cluster, entity_properties, is_native_cluster = \
            self._get_tkg_s_and_native_clusters_by_name(cluster_name,
                                                        org=org, vdc=vdc)
        if is_native_cluster:
            return self._nativeCluster.get_cluster_config_by_id(cluster.id)
        return self._tkgCluster.get_cluster_config_by_id(cluster_id=entity_properties.get('id'))  # noqa: E501

    def get_cluster_config_by_id(self, cluster_id, org=None):
        """Fetch kube config of the cluster using cluster ID.

        :param str cluster_id:
        :param str org:
        """
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        if entity_svc.is_native_entity(cluster_id):
            return self._nativeCluster.get_cluster_config_by_id(cluster_id)
        return self._tkgCluster.get_cluster_config_by_id(cluster_id, org=org)

    def delete_cluster(self, cluster_name, cluster_id=None,
                       org=None, vdc=None):
        """Delete DEF cluster by name.

        :param str cluster_name: name of the cluster
        :param str cluster_id:
        :param str org: name of the org
        :param str vdc: name of the vdc

        :return: deleted cluster info
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        if cluster_id:
            return self.delete_cluster_by_id(cluster_id)
        cluster, entity_properties, is_native_cluster = \
            self._get_tkg_s_and_native_clusters_by_name(cluster_name,
                                                        org=org, vdc=vdc)
        if is_native_cluster:
            return self._nativeCluster.delete_cluster_by_id(cluster.id)
        return self._tkgCluster.delete_cluster_by_id(cluster_id=entity_properties.get('id'))  # noqa: E501

    def delete_cluster_by_id(self, cluster_id, org=None):
        """Delete cluster using cluster id.

        :param str cluster_id: id of the cluster to be deleted
        :param str org:

        :return: deleted cluster information
        :rtype: str

        :raises: ClusterNotFoundError
        """
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        if entity_svc.is_native_entity(cluster_id):
            return self._nativeCluster.delete_cluster_by_id(cluster_id)
        return self._tkgCluster.delete_cluster_by_id(cluster_id, org=org)

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        """Get the upgrade plan for the given cluster name.

        :param cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: upgrade plan(s)
        :rtype: list
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        cluster, _, is_native_cluster = \
            self._get_tkg_s_and_native_clusters_by_name(cluster_name, org=org, vdc=vdc)  # noqa: E501
        if is_native_cluster:
            return self._nativeCluster.get_upgrade_plan_by_cluster_id(cluster.id)  # noqa: E501
        self._tkgCluster.get_upgrade_plan(cluster_name, vdc=vdc, org=org)

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
        :return: task representing the upgrade operation
        :rtype: str
        """
        cluster, _, is_native_cluster = \
            self._get_tkg_s_and_native_clusters_by_name(cluster_name, org=org_name, vdc=ovdc_name)  # noqa: E501
        if is_native_cluster:
            cluster.entity.spec.k8_distribution.template_name = template_name
            cluster.entity.spec.k8_distribution.template_revision = template_revision  # noqa: E501
            cluster_dict = cluster.to_dict()
            return self._nativeCluster.upgrade_cluster_by_cluster_id(cluster.id, cluster_def_entity=cluster_dict)  # noqa: E501
        self._tkgCluster.upgrade_cluster(cluster_name, template_name, template_revision)  # noqa: E501

    def share_cluster(self, cluster_id, cluster_name, users: list,
                      access_level_id, org=None, vdc=None):
        # Find cluster type
        if cluster_id:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            is_native_cluster = entity_svc.is_native_entity(cluster_id)
        else:
            _, _, is_native_cluster = \
                self._get_tkg_s_and_native_clusters_by_name(
                    cluster_name, org=org, vdc=vdc
                )

        if is_native_cluster:
            self._nativeCluster.share_cluster(cluster_id, cluster_name, users,
                                              access_level_id, org, vdc)
        else:
            self._tkgCluster.share_cluster(cluster_id, cluster_name, users,
                                           access_level_id, org, vdc)

    def list_share_entries(self, cluster_id, cluster_name, org=None, vdc=None):
        # Find cluster type
        if cluster_id:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            is_native_cluster = entity_svc.is_native_entity(cluster_id)
        else:
            _, _, is_native_cluster = \
                self._get_tkg_s_and_native_clusters_by_name(
                    cluster_name, org=org, vdc=vdc
                )

        if is_native_cluster:
            return self._nativeCluster.list_share_entries(
                cluster_id, cluster_name, org, vdc)
        else:
            return self._tkgCluster.list_share_entries(
                cluster_id, cluster_name, org, vdc)

    def unshare_cluster(self, cluster_id, cluster_name, users: list, org=None,
                        vdc=None):
        if cluster_id:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            is_native_cluster = entity_svc.is_native_entity(cluster_id)
        else:
            _, _, is_native_cluster = \
                self._get_tkg_s_and_native_clusters_by_name(
                    cluster_name, org=org, vdc=vdc
                )

        if is_native_cluster:
            self._nativeCluster.unshare_cluster(cluster_id, cluster_name,
                                                users, org, vdc)
        else:
            self._tkgCluster.unshare_cluster(cluster_id, cluster_name, users,
                                             org, vdc)
