# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import os
from typing import List

import pyvcloud.vcd.exceptions as vcd_exceptions

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.native_cluster_api import NativeClusterApi  # noqa: E501
from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.configuration import Configuration  # noqa: E501
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster  # noqa: E501
import container_service_extension.client.utils as client_utils
import container_service_extension.def_.entity_service as def_entity_svc
from container_service_extension.def_.utils import ClusterEntityKind
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

    def list_tkg_clusters(self):
        tkg_cluster_api = TkgClusterApi(api_client=self.tkg_client)
        response = tkg_cluster_api.list_tkg_clusters(
            f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}")  # noqa: E501
        entities: List[TkgCluster] = response[0]
        clusters = []
        for entity in entities:
            cluster = {
                'Name': entity.metadata.name,
                'Kind': 'TanzuKubernetesCluster',
                'VDC': entity.metadata.virtual_data_center_name,
                'K8s Version': entity.spec.distribution.version
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
        entity_list = entity_svc.list_entities(filters=filters)  # noqa: E501
        clusters = []

        for def_entity in entity_list:
            logger.CLIENT_LOGGER.debug(f"Defined entity list from server:{def_entity}")  # noqa: E501
            is_tkg_cluster = def_entity.entityType == cli_constants.TKG_ENTITY_TYPE_ID # noqa: E501
            vdc_name = def_entity.entity.metadata.VirtualDataCenterName \
                if is_tkg_cluster else def_entity.entity.metadata.ovdc_name

            # TODO check if the values returned matches the required k8_runtime
            k8_runtime = cli_constants.TKG_CLUSTER_RUNTIME \
                if is_tkg_cluster else def_entity.entity.kind
            org_name = "" if is_tkg_cluster else def_entity.entity.metadata.org_name # noqa: E501

            # TODO find the correct parameter to fill for Owner
            owner = " "

            k8_version = f"TKG {def_entity.entity.spec.distribution.version}" \
                if is_tkg_cluster else def_entity.entity.status.kubernetes # noqa: E501

            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: def_entity.name,
                cli_constants.CLIOutputKey.VDC.value: vdc_name,
                cli_constants.CLIOutputKey.ORG.value: org_name,
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: k8_runtime,
                cli_constants.CLIOutputKey.K8S_VERSION.value: k8_version,
                cli_constants.CLIOutputKey.STATUS.value: def_entity.entity.status.phase, # noqa: E501
                cli_constants.CLIOutputKey.OWNER.value: owner
            }
            clusters.append(cluster)
        return clusters

    def get_cluster_info(self, cluster_name, org=None, vdc=None, **kwargs):
        """Get cluster information using DEF API.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster information
        :rtype: dict
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entities = entity_svc.get_entities_by_name(entity_name=cluster_name, filters=filters)  # noqa: E501
        if len(def_entities) > 1:
            raise cse_exceptions.CseDuplicateClusterError(DUPLICATE_CLUSTER_ERROR_MSG)  # noqa: E501
        if len(def_entities) == 0:
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        def_entity = def_entities[0]
        CLIENT_LOGGER.debug(f"Defined entity info from server:{def_entity.entity}")  # noqa: E501
        # TODO() relevant output
        return asdict(def_entity)

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF cluster by name.

        :param str cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: requests.models.Response response
        :rtype: dict
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entities = entity_svc.get_entities_by_name(entity_name=cluster_name, filters=filters)  # noqa: E501
        if len(def_entities) > 1:
            raise cse_exceptions.CseDuplicateClusterError(DUPLICATE_CLUSTER_ERROR_MSG)  # noqa: E501
        if len(def_entities) == 0:
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        def_entity = def_entities[0]
        if def_entity.entity.kind == ClusterEntityKind.NATIVE.value:
            return self._nativeCluster.delete_cluster_by_id(def_entity.id)
        # TODO() TKG cluster delete

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        """Get the upgrade plan for the given cluster name.

        :param cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: requests.models.Response response
        :rtype: dict
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entities = entity_svc.get_entities_by_name(entity_name=cluster_name, filters=filters)  # noqa: E501
        if len(def_entities) > 1:
            raise cse_exceptions.CseDuplicateClusterError(DUPLICATE_CLUSTER_ERROR_MSG)  # noqa: E501
        if len(def_entities) == 0:
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        def_entity = def_entities[0]
        if def_entity.entity.kind == ClusterEntityKind.NATIVE.value:
            return self._nativeCluster.get_upgrade_plan_by_cluster_id(def_entity.id)  # noqa: E501
        else:
            raise vcd_exceptions.OperationNotSupportedException(f"upgrade-plan is not supported for k8-runtime:{def_entity.entity.kind}")  # noqa: E501
