# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import os
from typing import List

import yaml

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.native_cluster_api import NativeClusterApi  # noqa: E501
from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.configuration import Configuration  # noqa: E501
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster  # noqa: E501
import container_service_extension.client.utils as client_utils
import container_service_extension.def_.entity_service as def_entity_svc
from container_service_extension.def_.utils import DEF_CSE_VENDOR
from container_service_extension.def_.utils import DEF_NATIVE_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_NATIVE_ENTITY_TYPE_VERSION # noqa: E501
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_VERSION
from container_service_extension.def_.utils import DEF_VMWARE_VENDOR
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils

DUPLICATE_CLUSTER_ERROR_MSG = "Duplicated clusters found. Please use --k8-runtime for the unique identification"  # noqa: E501


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
        self.tkg_client = self._get_tkg_client()

    def _get_tkg_client(self):
        tkg_config = Configuration()
        tkg_config.host = f"{self._client.get_cloudapi_uri()}/1.0.0/"
        tkg_config.verify_ssl = self._client._verify_ssl_certs
        tkg_client = ApiClient(configuration=tkg_config)
        jwt_token = self._client.get_access_token()
        if jwt_token:
            tkg_client.set_default_header("Authorization", f"Bearer {jwt_token}")  # noqa: E501
        else:
            legacy_token = self._client.get_xvcloud_authorization_token()
            tkg_client.set_default_header("x-vcloud-authorization", legacy_token)  # noqa: E501
        api_version = self._client.get_api_version()
        tkg_client.set_default_header("Accept", f"application/json;version={api_version}")  # noqa: E501
        return tkg_client

    def get_tkg_cluster(self, id):
        """Sample method to use tkg_client.

        To be modified or removed as per the needs of CSE-CLI

        :param id: Id of the cluster
        :return: Tkg cluster
        :rtype: dict
        """
        tkg_cluster_api = TkgClusterApi(api_client=self.tkg_client)
        # Returns tuple of response_data, response_status, response_headers
        response = tkg_cluster_api.get_tkg_cluster(id)
        cluster: TkgCluster = response[0]
        return cluster.to_dict()

    def list_tkg_clusters(self, vdc=None, org=None):
        """List all the TKG clusters.

        :param str vdc: name of vdc to filter by
        :param str org: name of the org to filter by
        :return: list of TKG cluster information.
        :rtype: List[dict]
        """
        tkg_cluster_api = TkgClusterApi(api_client=self.tkg_client)
        filters = []
        if org:
            # TODO(TKG): Add org filter once TKG schema is updated
            pass
        if vdc:
            filters.append((cli_constants.TKGClusterEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = None
        if filters:
            filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])  # noqa: E501
        response = tkg_cluster_api.list_tkg_clusters(
            f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}",  # noqa: E501
            object_filter=filter_string)
        entities: List[TkgCluster] = response[0]
        clusters = []
        for entity in entities:
            logger.CLIENT_LOGGER.debug(f"TKG Defined entity list from server: {entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: entity.metadata.name, # noqa: E501
                cli_constants.CLIOutputKey.VDC.value: entity.metadata.virtual_data_center_name, # noqa: E501
                # TODO(TKG): Missing org name in the response
                cli_constants.CLIOutputKey.ORG.value: " ", # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: cli_constants.TKG_CLUSTER_RUNTIME, # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: entity.spec.distribution.version, # noqa: E501
                # TODO(TKG): status field doesn't have any attributes
                cli_constants.CLIOutputKey.STATUS.value: " ",
                # TODO(Owner in CSE server response): Owner value is needed
                cli_constants.CLIOutputKey.OWNER.value: " ",
            }
            clusters.append(cluster)
        return clusters

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

        clusters = self.list_tkg_clusters(vdc=vdc, org=org) or []
        for def_entity in native_entities:
            entity = def_entity.entity
            logger.CLIENT_LOGGER.debug(f"Native Defined entity list from server: {def_entity}")  # noqa: E501
            # owner_id = \
            # def_entity.ownerId if hasattr(def_entity, 'ownerId') else ' '
            # TODO(Owner in CSE server response): REST call to fetch owner_name
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: def_entity.name,
                cli_constants.CLIOutputKey.VDC.value: entity.metadata.ovdc_name, # noqa: E501
                cli_constants.CLIOutputKey.ORG.value: entity.metadata.org_name, # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: entity.kind, # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: entity.status.kubernetes, # noqa: E501
                cli_constants.CLIOutputKey.STATUS.value: entity.status.phase, # noqa: E501
                cli_constants.CLIOutputKey.OWNER.value: ' '
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
        # TODO add filters for TKG cluster
        tkg_cluster_api = TkgClusterApi(api_client=self.tkg_client)

        filters = [(cli_constants.TKGClusterEntityFilterKey.CLUSTER_NAME.value, cluster_name)]  # noqa: E501
        if org:
            # TODO(Org filed for TKG): Add filter once schema is updated
            pass
        if vdc:
            filters.append((cli_constants.TKGClusterEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])
        response = \
            tkg_cluster_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}", # noqa: E501
                object_filter=filter_string)
        tkg_entities = [tkg_entity.to_dict() for tkg_entity in response[0]]
        return tkg_entities, native_def_entity_dict

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

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF cluster by name.

        :param str cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: requests.models.Response response
        :rtype: dict
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
        :return: requests.models.Response response
        :rtype: dict
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
        # TODO() TKG cluster delete
        raise NotImplementedError(
            "Get Cluster upgrade-plan for TKG clusters not yet implemented")  # noqa: E501
