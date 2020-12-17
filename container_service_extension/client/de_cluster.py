# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict
import json
import os

import requests
import yaml

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.de_cluster_native import DEClusterNative  # noqa: E501
from container_service_extension.client.de_cluster_tkg import DEClusterTKG
import container_service_extension.client.tkgclient.rest as tkg_rest
import container_service_extension.client.utils as client_utils
import container_service_extension.def_.entity_service as def_entity_svc
from container_service_extension.def_.utils import DEF_CSE_VENDOR
from container_service_extension.def_.utils import DEF_NATIVE_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_NATIVE_ENTITY_TYPE_VERSION # noqa: E501
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils

DUPLICATE_CLUSTER_ERROR_MSG = "Duplicate clusters found. Please use --k8-runtime for the unique identification"  # noqa: E501


class DECluster:
    """Handle operations common to DefNative and TKG kubernetes clusters.

    Also any operation where cluster kind is not supplied should be handled here.  # noqa: E501

    Example(s):
        cluster list is a collection which may have mix of DefNative and
        TKG clusters.

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
        self._tkgCluster = DEClusterTKG(client)

    def list_clusters(self, vdc=None, org=None, **kwargs):
        """Get collection of clusters using DEF API.

        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster list information
        :rtype: list(dict)
        """
        has_native_rights = True
        has_tkg_rights = True
        clusters = []
        try:
            clusters += self._tkgCluster.list_tkg_clusters(vdc=vdc, org=org)
        except tkg_rest.ApiException as e:
            if e.status not in [requests.codes.FORBIDDEN, requests.codes.UNAUTHORIZED]:  # noqa: E501
                server_message = json.loads(e.body).get('message') or e.reason
                msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{server_message}")  # noqa: E501
                logger.CLIENT_LOGGER.error(msg)
                raise Exception(msg)
            logger.CLIENT_LOGGER.debug(f"No rights present to fetch TKG clusters: {e}") # noqa: E501
            has_tkg_rights = False
        if not client_utils.is_cli_for_tkg_only():
            filters = client_utils.construct_filters(org=org, vdc=vdc)
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            native_entities = entity_svc.list_entities_by_entity_type(
                vendor=DEF_CSE_VENDOR,
                nss=DEF_NATIVE_ENTITY_TYPE_NSS,
                version=DEF_NATIVE_ENTITY_TYPE_VERSION,
                filters=filters)
            try:
                for def_entity in native_entities:
                    entity = def_entity.entity
                    logger.CLIENT_LOGGER.debug(f"Native Defined entity list from server: {def_entity}")  # noqa: E501
                    cluster = {
                        cli_constants.CLIOutputKey.CLUSTER_NAME.value: def_entity.name,  # noqa: E501
                        cli_constants.CLIOutputKey.VDC.value: entity.metadata.ovdc_name, # noqa: E501
                        cli_constants.CLIOutputKey.ORG.value: entity.metadata.org_name, # noqa: E501
                        cli_constants.CLIOutputKey.K8S_RUNTIME.value: entity.kind, # noqa: E501
                        cli_constants.CLIOutputKey.K8S_VERSION.value: entity.status.kubernetes, # noqa: E501
                        cli_constants.CLIOutputKey.STATUS.value: entity.status.phase, # noqa: E501
                        cli_constants.CLIOutputKey.OWNER.value: def_entity.owner.name  # noqa: E501
                    }
                    clusters.append(cluster)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code not in [requests.codes.FORBIDDEN, requests.codes.UNAUTHORIZED]:  # noqa: E501
                    logger.CLIENT_LOGGER.error(f"Failed to fetch native clusters: {str(e)}")  # noqa: E501
                    raise
                logger.CLIENT_LOGGER.debug(f"No rights present to fetch native clusters: {str(e)}")  # noqa: E501
                has_native_rights = False
        if not (has_tkg_rights or has_native_rights):
            raise Exception("Logged in user doesn't have Native cluster rights"
                            " or TKG rights. Please contact administrator.")
        return clusters

    def _get_tkg_native_clusters_by_name(self, cluster_name: str,
                                         org=None, vdc=None):
        """Get native and TKG clusters by name.

        Assumption: Native clusters cannot have name collision among them.
        But there can be multiple TKG clusters with the same name and 2 or
        more TKG clusters can also have the same name.

        :param str cluster_name: Cluster name to search for
        :param str org: Org to filter by
        :param str vdc: VDC to filter by
        :returns: tkg entity or native def entity with entity properties and
            boolean indicating cluster type
        :rtype: (cluster, dict,  bool)
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        has_native_rights = True
        has_tkg_rights = True
        native_def_entity = None
        additional_entity_properties = None
        # NOTE: The following can throw error if invoked by users who
        # doesn't have the necessary rights.
        try:
            native_def_entity = entity_svc.get_native_entity_by_name(
                name=cluster_name,
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
                self._tkgCluster.get_tkg_clusters_by_name(cluster_name,
                                                          vdc=vdc, org=org)
        except tkg_rest.ApiException as e:
            if e.status not in [requests.codes.FORBIDDEN, requests.codes.UNAUTHORIZED]:  # noqa: E501
                raise
            has_tkg_rights = False
        except cse_exceptions.ClusterNotFoundError:
            logger.CLIENT_LOGGER.debug(f"No TKG cluster with name {cluster_name}")  # noqa: E501
        if not (has_native_rights or has_tkg_rights):
            raise Exception("User cannot access native or TKG clusters."
                            " Please contact administrator")
        msg = "Multiple clusters with the same name found."
        if len(tkg_entity) > 0 and native_def_entity:
            # If org filter is not provided, ask the user to provide org
            # filter
            if not org:
                # handles the case where there is are TKG clusters and native
                # clusters with the same name in different organizations
                raise Exception(f"{msg} Please specify the org to use "
                                "using --org flag.")
            # handles the case where there is a TKG cluster and a native
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
        :param str vdc: name of vdc
        :param str org: name of org
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
            self._get_tkg_native_clusters_by_name(cluster_name,
                                                  org=org, vdc=vdc)
        if is_native_cluster:
            cluster_info = asdict(cluster.entity)
        else:
            # TKG cluster represents the defined_entity.entity
            cluster_info = client_utils.swagger_object_to_dict(cluster)
        logger.CLIENT_LOGGER.debug(
            f"Received defined entity of cluster {cluster_name} : {cluster_info}")  # noqa: E501
        return yaml.dump(cluster_info)

    def get_cluster_info_by_id(self, cluster_id, org=None):
        """Obtain cluster information using cluster ID.

        :param str cluster_id
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
        :param str vdc: name of vdc
        :param str org: name of org

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        if cluster_id:
            return self.get_cluster_config_by_id(cluster_id, org=org)
        cluster, entity_properties, is_native_cluster = \
            self._get_tkg_native_clusters_by_name(cluster_name,
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
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: deleted cluster info
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        if cluster_id:
            return self.delete_cluster_by_id(cluster_id)
        cluster, entity_properties, is_native_cluster = \
            self._get_tkg_native_clusters_by_name(cluster_name,
                                                  org=org, vdc=vdc)
        if is_native_cluster:
            return self._nativeCluster.delete_cluster_by_id(cluster.id)
        return self._tkgCluster.delete_cluster_by_id(cluster_id=entity_properties.get('id'))  # noqa: E501

    def delete_cluster_by_id(self, cluster_id, org=None):
        """Delete cluster using cluster id.

        :param str cluster_id: id of the cluster to be deleted
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
            self._get_tkg_native_clusters_by_name(cluster_name, org=org, vdc=vdc)  # noqa: E501
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
            self._get_tkg_native_clusters_by_name(cluster_name, org=org_name, vdc=ovdc_name)  # noqa: E501
        if is_native_cluster:
            cluster.entity.spec.k8_distribution.template_name = template_name
            cluster.entity.spec.k8_distribution.template_revision = template_revision  # noqa: E501
            cluster_dict = asdict(cluster)
            return self._nativeCluster.upgrade_cluster_by_cluster_id(cluster.id, cluster_def_entity=cluster_dict)  # noqa: E501
        self._tkgCluster.upgrade_cluster(cluster_name, template_name, template_revision)  # noqa: E501

    def share_cluster(self, cluster_id, cluster_name, users: list,
                      access_level_id, org=None, vdc=None):
        # Find cluster type
        if cluster_id:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            is_native_cluster = entity_svc.is_native_entity(cluster_id)
        else:
            cluster_ent, entity_properties, is_native_cluster = \
                self._get_tkg_native_clusters_by_name(cluster_name, org=org,
                                                      vdc=vdc)

        if is_native_cluster:
            self._nativeCluster.share_cluster(cluster_id, cluster_name, users,
                                              access_level_id, org, vdc)
        else:
            self._tkgCluster.share_cluster(cluster_id, cluster_name, users,
                                           access_level_id, org, vdc)

    def unshare_cluster(self, cluster_id, cluster_name, users: list, org=None,
                        vdc=None):
        if cluster_id:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            is_native_cluster = entity_svc.is_native_entity(cluster_id)
        else:
            _, _, is_native_cluster = \
                self._get_tkg_native_clusters_by_name(cluster_name, org=org,
                                                      vdc=vdc)

        if is_native_cluster:
            self._nativeCluster.unshare_cluster(cluster_id, cluster_name,
                                                users, org, vdc)
        else:
            self._tkgCluster.unshare_cluster(cluster_id, cluster_name, users,
                                             org, vdc)
