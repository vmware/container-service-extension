# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import os

import yaml

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.native_cluster_api import NativeClusterApi  # noqa: E501
import container_service_extension.client.tkg_cluster_api as tkg_cluster_api
import container_service_extension.client.utils as client_utils
import container_service_extension.def_.entity_service as def_entity_svc
from container_service_extension.def_.utils import DEF_CSE_VENDOR
from container_service_extension.def_.utils import DEF_NATIVE_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_NATIVE_ENTITY_TYPE_VERSION # noqa: E501
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils

DUPLICATE_CLUSTER_ERROR_MSG = "Duplicate clusters found. Please use --k8-runtime for the unique identification"  # noqa: E501


class DefEntityClusterApi:
    """Handle operations common to DefNative and TKG kubernetes clusters.

    Also any operation where cluster kind is not supplied should be handled here.  # noqa: E501

    Example(s):
        cluster list is a collection which may have mix of DefNative and
        TKG clusters.

        cluster info for a given cluster name needs lookup using DEF API.
    """

    def __init__(self, client):
        self._client = client
        logger_wire = logger.NULL_LOGGER
        if os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING):
            logger_wire = logger.CLIENT_WIRE_LOGGER
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                client=client, logger_debug=logger.CLIENT_LOGGER,
                logger_wire=logger_wire)
        self._nativeCluster = NativeClusterApi(client)
        self._tkgCluster = tkg_cluster_api.TKGClusterApi(client)

    def list_clusters(self, vdc=None, org=None, **kwargs):
        """Get collection of clusters using DEF API.

        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster list information
        :rtype: list(dict)
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        native_entities = entity_svc.list_entities_by_entity_type(
            vendor=DEF_CSE_VENDOR,
            nss=DEF_NATIVE_ENTITY_TYPE_NSS,
            version=DEF_NATIVE_ENTITY_TYPE_VERSION,
            filters=filters)

        clusters = self._tkgCluster.list_tkg_clusters(vdc=vdc, org=org) or []
        for def_entity in native_entities:
            entity = def_entity.entity
            logger.CLIENT_LOGGER.debug(f"Native Defined entity list from server: {def_entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: def_entity.name,
                cli_constants.CLIOutputKey.VDC.value: entity.metadata.ovdc_name, # noqa: E501
                cli_constants.CLIOutputKey.ORG.value: entity.metadata.org_name, # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: entity.kind, # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: entity.status.kubernetes, # noqa: E501
                cli_constants.CLIOutputKey.STATUS.value: entity.status.phase, # noqa: E501
                cli_constants.CLIOutputKey.OWNER.value: def_entity.owner.name
            }
            clusters.append(cluster)
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
        :returns: tuple containing TKG cluster list and native cluster if
            present.
        :rtype: (list[TkgCluster], def_models.DefEntity)
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        native_def_entity = entity_svc.get_native_entity_by_name(
            name=cluster_name,
            filters=filters)
        native_def_entity_dict = {}
        if native_def_entity:
            native_def_entity_dict = asdict(native_def_entity)
        tkg_entities = self._tkgCluster.get_tkg_clusters_by_name(cluster_name,
                                                                 vdc=vdc,
                                                                 org=org)
        # convert the tkg entities to dictionary
        tkg_entity_dicts = [tkg_entity.to_dict() for tkg_entity in tkg_entities]
        return tkg_entity_dicts, native_def_entity_dict

    def get_cluster_info(self, cluster_name, org=None, vdc=None, **kwargs):
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
        tkg_entities, native_def_entity = \
            self._get_tkg_native_clusters_by_name(cluster_name,
                                                  org=org, vdc=vdc)
        if (tkg_entities and native_def_entity) or (len(tkg_entities) > 1):
            msg = f"Multiple clusters found with name {cluster_name}. " \
                  "Please use the flag --k8-runtime to uniquely identify the cluster." # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)
        elif not native_def_entity and len(tkg_entities) == 0:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        cluster_info = native_def_entity.get('entity') or tkg_entities[0]
        logger.CLIENT_LOGGER.debug(
            f"Received defined entity of cluster {cluster_name} : {cluster_info}")  # noqa: E501
        return yaml.dump(cluster_info)

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        """Get cluster config.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        tkg_entities, native_def_entity = \
            self._get_tkg_native_clusters_by_name(cluster_name,
                                                  org=org, vdc=vdc)
        if (tkg_entities and native_def_entity) or (len(tkg_entities) > 1):
            msg = f"Multiple clusters found with name {cluster_name}. " \
                "Please use the flag --k8-runtime to uniquely identify the cluster." # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)
        elif not native_def_entity and len(tkg_entities) == 0:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        elif native_def_entity:
            return self._nativeCluster.get_cluster_config_by_id(
                native_def_entity.get('id'))
        raise NotImplementedError(
            "Get Cluster Config for TKG clusters not yet implemented")  # noqa: E501

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF cluster by name.

        :param str cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: deleted cluster info
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        tkg_entities, native_entity = \
            self._get_tkg_native_clusters_by_name(cluster_name,
                                                  org=org, vdc=vdc)
        if (tkg_entities and native_entity) or (len(tkg_entities) > 1):
            msg = f"Multiple clusters found with name {cluster_name}. " \
                  "Please use the flag --k8-runtime to uniquely identify the cluster to delete."  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)
        elif not native_entity and len(tkg_entities) == 0:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        elif native_entity:
            return self._nativeCluster.delete_cluster_by_id(
                native_entity.get('id'))
        # TODO() TKG cluster delete
        raise NotImplementedError(
            "Cluster delete for TKG clusters not yet implemented")  # noqa: E501

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        """Get the upgrade plan for the given cluster name.

        :param cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: upgrade plan(s)
        :rtype: list
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        tkg_entities, native_entity = \
            self._get_tkg_native_clusters_by_name(cluster_name, org=org, vdc=vdc)  # noqa: E501
        if (tkg_entities and native_entity) or (len(tkg_entities) > 1):
            msg = f"Multiple clusters found with name {cluster_name}. " \
                  "Please use the flag --k8-runtime to uniquely identify the cluster to delete."  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)
        elif not native_entity and len(tkg_entities) == 0:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        elif native_entity:
            return self._nativeCluster.get_upgrade_plan_by_cluster_id(
                native_entity.get('id'))
        raise NotImplementedError(
            "Get Cluster upgrade-plan for TKG clusters not yet implemented")  # noqa: E501

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
        :return: requests.models.Response response
        :rtype: dict
        """
        tkg_entities, native_entity = \
            self._get_tkg_native_clusters_by_name(cluster_name, org=org_name, vdc=ovdc_name)  # noqa: E501
        if (tkg_entities and native_entity) or (len(tkg_entities) > 1):
            msg = f"Multiple clusters found with name {cluster_name}. " \
                "Please use the flag --k8-runtime to uniquely identify the cluster to delete."  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)
        elif not native_entity and len(tkg_entities) == 0:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        elif native_entity:
            native_entity['entity']['spec']['k8_distribution']['template_name'] = template_name  # noqa: E501
            native_entity['entity']['spec']['k8_distribution']['template_revision'] = template_revision  # noqa: E501
            return self._nativeCluster.upgrade_cluster_by_cluster_id(native_entity['id'], cluster_entity=native_entity)  # noqa: E501
        raise NotImplementedError(
            "Cluster upgrade for TKG clusters not yet implemented")  # noqa: E501
