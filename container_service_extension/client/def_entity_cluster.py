# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from typing import List

import pyvcloud.vcd.exceptions as vcd_exceptions

import container_service_extension.def_.entity_service as def_entity_svc
from container_service_extension.def_.utils import ClusterEntityFilterKey
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_VERSION
from container_service_extension.def_.utils import DEF_VMWARE_VENDOR
import container_service_extension.exceptions as cse_exceptions
from container_service_extension.logger import CLIENT_LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils

from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.configuration import Configuration
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster


class DefEntityCluster:
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
        self._cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
            client=client, logger_debug=CLIENT_LOGGER)
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
            f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}")
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
        filters = {}
        if org:
            filters[ClusterEntityFilterKey.ORG_NAME.value] = org
        if vdc:
            filters[ClusterEntityFilterKey.OVDC_NAME.value] = vdc

        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        entity_list = entity_svc.list_entities(filters=filters)  # noqa: E501
        clusters = []
        # TODO() relevant output
        for def_entity in entity_list:
            CLIENT_LOGGER.debug(f"Defined entity list from server:{def_entity}")  # noqa: E501
            cluster = {
                'Name': def_entity.name,
                'Kind': def_entity.entity.kind,
                'VDC': def_entity.entity.metadata.ovdc_name,
                'Org': def_entity.entity.metadata.org_name,
                'K8s Version': def_entity.entity.status.kubernetes,
                'Status': def_entity.entity.status.phase,
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
        """
        filters = {}
        if org:
            filters[ClusterEntityFilterKey.ORG_NAME.value] = org
        if vdc:
            filters[ClusterEntityFilterKey.OVDC_NAME.value] = vdc
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_entity_by_name(entity_name=cluster_name, filters=filters)  # noqa: E501
        if def_entity:
            CLIENT_LOGGER.debug(f"Defined entity info from server:{def_entity}")  # noqa: E501
            # TODO() relevant output
            return {
                'Name': def_entity.name,
                'Kind': def_entity.entity.kind,
                'VDC': def_entity.entity.metadata.ovdc_name,
                'Org': def_entity.entity.metadata.org_name,
                'K8s Version': def_entity.entity.status.kubernetes,  # noqa: E501
                'Status': def_entity.entity.status.phase,
            }
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

