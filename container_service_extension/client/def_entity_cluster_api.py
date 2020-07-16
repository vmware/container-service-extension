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


class DefEntityClusterApi:
    """Handle operations common to DefNative and vsphere kubernetes clusters.

    Also any operation where cluster kind is not known should be handled here.

    Example(s):
        cluster list is a collection which may have mix of DefNative and
        vsphere kubenetes clusters.

        cluster info for a given cluster name needs lookup using DEF API. There
        is no up-front cluster kind (optional).
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

    def list_tkg_clusters(self):
        tkg_cluster_api = TkgClusterApi(api_client=self.tkg_client)
        response = tkg_cluster_api.list_tkg_clusters(
            f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}")  # noqa: E501
        entities: List[TkgCluster] = response[0]
        clusters = []
        for entity in entities:
            logger.CLIENT_LOGGER.debug(f"TKG Defined entity list from server: {entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: entity.metadata.name, # noqa: E501
                cli_constants.CLIOutputKey.VDC.value: entity.metadata.virtual_data_center_name, # noqa: E501
                # TODO(TKG): Missing org name in the response
                cli_constants.CLIOutputKey.ORG.value: " ", # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: "TanzuKubernetesCluster", # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: entity.spec.distribution.version, # noqa: E501
                # TODO(TKG): status field doesn't have any attributes
                cli_constants.CLIOutputKey.STATUS.value: " ",
                # TODO(Owner in CSE server response): Owner value is needed
                cli_constants.CLIOutputKey.OWNER.value: " ",
            }
            clusters.append(cluster)
        return clusters

    def get_clusters(self, vdc=None, org=None, **kwargs):
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

        clusters = self.list_tkg_clusters() or []
        for def_entity in native_entities:
            logger.CLIENT_LOGGER.debug(f"Native Defined entity list from server: {def_entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: def_entity.name,
                cli_constants.CLIOutputKey.VDC.value: def_entity.entity.metadata.ovdc_name, # noqa: E501
                cli_constants.CLIOutputKey.ORG.value: def_entity.entity.metadata.org_name, # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: def_entity.entity.kind, # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: def_entity.entity.status.kubernetes, # noqa: E501
                cli_constants.CLIOutputKey.STATUS.value: def_entity.entity.status.phase, # noqa: E501
                # TODO(Owner in CSE server response): Owner value is needed
                cli_constants.CLIOutputKey.OWNER.value: " "
            }
            clusters.append(cluster)
        return clusters

    def _get_all_clusters_by_name(self, cluster_name: str, org=None, vdc=None):
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
        # TODO add filters for TKG cluster
        tkg_cluster_api = TkgClusterApi(api_client=self.tkg_client)
        response = \
            tkg_cluster_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}", # noqa: E501
                object_filter=f"name=={cluster_name}")
        return response[0], native_def_entity

    def get_cluster_info(self, cluster_name, org=None, vdc=None, **kwargs):
        """Get cluster information using DEF API.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster information
        :rtype: str
        """
        tkg_entities, native_def_entity = \
            self._get_all_clusters_by_name(cluster_name, org=org, vdc=vdc)
        if (tkg_entities and native_def_entity) or (len(tkg_entities) > 1):
            msg = "Duplicated clusters found. Please use --k8-runtime for the unique identification" # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)

        if native_def_entity:
            cluster_info = asdict(native_def_entity.entity)
        elif len(tkg_entities) == 1:
            cluster_info = tkg_entities[0].to_dict()
        else:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)

        logger.CLIENT_LOGGER.debug(f"Defined entity output from server: {cluster_info}") # noqa: E501
        return yaml.dump(cluster_info)

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF cluster by name.

        :param str cluster_name: native cluster name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: requests.models.Response response
        :rtype: dict
        :raises ClusterNotFoundError
        """
        tkg_entities, native_def_entity = \
            self._get_all_clusters_by_name(cluster_name, org=org, vdc=vdc)
        if (tkg_entities and native_def_entity) or (len(tkg_entities) > 1):
            msg = "Duplicated clusters found. Please use --k8-runtime for the unique identification" # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)

        if native_def_entity:
            return self._nativeCluster.delete_cluster_by_id(native_def_entity.id) # noqa: E501
        elif len(tkg_entities) == 1:
            # TODO() TKG cluster delete
            raise NotImplementedError("Cluster delete for TKG clusters not yet implemented") # noqa: E501

        msg = f"Cluster '{cluster_name}' not found."
        logger.CLIENT_LOGGER.error(msg)
        raise cse_exceptions.ClusterNotFoundError(msg)
