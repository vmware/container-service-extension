# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.configuration import Configuration  # noqa: E501
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster  # noqa: E501
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_VERSION
from container_service_extension.def_.utils import DEF_VMWARE_VENDOR
import container_service_extension.logger as logger


class TKGClusterApi:
    """Embedded Kubernetes into vSphere."""

    def __init__(self, client):
        self._client = client
        self.tkg_client = self._get_tkg_client()
        self._tkg_client_api = TkgClusterApi(api_client=self.tkg_client)

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

    def get_tkg_cluster(self, cluster_id):
        """Sample method to use tkg_client.

        To be modified or removed as per the needs of CSE-CLI

        :param id: Id of the cluster
        :return: Tkg cluster
        :rtype: dict
        """
        # Returns tuple of response_data, response_status, response_headers
        response = self._tkg_client_api.get_tkg_cluster(cluster_id)
        cluster: TkgCluster = response[0]
        return cluster.to_dict()

    def list_tkg_clusters(self, vdc=None, org=None):
        """List all the TKG clusters.

        :param str vdc: name of vdc to filter by
        :param str org: name of the org to filter by
        :return: list of TKG cluster information.
        :rtype: List[dict]
        """
        filters = []
        if org:
            # TODO(Org filter not working)
            # filters.append((cli_constants.TKGClusterEntityFilterKey.ORG_NAME.value, org))  # noqa: E501
            pass
        if vdc:
            filters.append((cli_constants.TKGClusterEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = None
        if filters:
            filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])  # noqa: E501
        # additional_data in the following statement represents the information
        # associated with the defined entity
        (entities, status, headers, additional_data) = \
            self._tkg_client_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}",  # noqa: E501
                _return_http_data_only=False,
                object_filter=filter_string)
        clusters = []
        for i in range(len(entities)):
            # NOTE: additional_data will contain corresponding defined entity
            # details
            entity: TkgCluster = entities[i]
            entity_properties = additional_data[i]
            logger.CLIENT_LOGGER.debug(f"TKG Defined entity list from server: {entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: entity.metadata.name, # noqa: E501
                cli_constants.CLIOutputKey.VDC.value: entity.metadata.virtual_data_center_name, # noqa: E501
                # TODO(TKG): Missing org name in the response
                cli_constants.CLIOutputKey.ORG.value: entity_properties['org']['name'], # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: cli_constants.TKG_CLUSTER_RUNTIME, # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: entity.spec.distribution.version, # noqa: E501
                # TODO(TKG): status field doesn't have any attributes
                cli_constants.CLIOutputKey.STATUS.value: entity.status.phase,
                # TODO(Owner in CSE server response): Owner value is needed
                cli_constants.CLIOutputKey.OWNER.value: entity_properties['owner']['name'],  # noqa: E501
            }
            clusters.append(cluster)
        return clusters

    def get_tkg_clusters_by_name(self, name, vdc=None, org=None):
        filters = [(cli_constants.TKGClusterEntityFilterKey.CLUSTER_NAME.value, name)]  # noqa: E501
        if org:
            # TODO(Org filed for TKG): Add filter once schema is updated
            pass
        if vdc:
            filters.append((cli_constants.TKGClusterEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])
        response = \
            self._tkg_client_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}", # noqa: E501
                object_filter=filter_string)
        return response[0]

    def apply(self, cluster_config: dict):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: str
        """
        cluster_name = cluster_config.get('metadata', {}).get('cluster_name')
        tkg_entities = self.get_tkg_clusters_by_name(cluster_name)
        if len(tkg_entities) == 0:
            response = self._tkg_client_api.create_tkg_cluster(cluster_config)
        elif len(tkg_entities) == 1:
            response = self._tkg_client_api.update_tkg_cluster(cluster_config)
        else:
            msg = f"Multiple clusters found with name {cluster_name}. " \
                  "Failed to apply the Spec."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.CseDuplicateClusterError(msg)
        if not def_entity:
            response = self._client._do_request_prim(
                shared_constants.RequestMethod.POST,
                uri,
                self._client._session,
                contents=cluster_config,
                media_type='application/json',
                accept_type='application/json')
        else:
            cluster_id = def_entity.id
            uri = f"{self._uri}/cluster/{cluster_id}"
            response = self._client._do_request_prim(
                shared_constants.RequestMethod.PUT,
                uri,
                self._client._session,
                contents=cluster_config,
                media_type='application/json',
                accept_type='application/json')
        return yaml.dump(response_processor.process_response(response)['entity']) # noqa: E501
