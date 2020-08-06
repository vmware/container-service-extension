# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import yaml

import container_service_extension.client.constants as cli_constants
from container_service_extension.client.tkgclient import TkgClusterApi
from container_service_extension.client.tkgclient.api_client import ApiClient
from container_service_extension.client.tkgclient.configuration import Configuration  # noqa: E501
from container_service_extension.client.tkgclient.models.tkg_cluster import TkgCluster  # noqa: E501
import container_service_extension.client.tkgclient.rest as tkg_rest
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_NSS
from container_service_extension.def_.utils import DEF_TKG_ENTITY_TYPE_VERSION
from container_service_extension.def_.utils import DEF_VMWARE_VENDOR
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils


class TKGClusterApi:
    """Embedded Kubernetes into vSphere."""

    def __init__(self, client):
        self._client = client
        tkg_config = Configuration()
        tkg_config.host = f"{self._client.get_cloudapi_uri()}/1.0.0/"
        tkg_config.verify_ssl = self._client._verify_ssl_certs

        self._tkg_client = ApiClient(configuration=tkg_config)
        jwt_token = self._client.get_access_token()
        if jwt_token:
            self._tkg_client.set_default_header("Authorization", f"Bearer {jwt_token}")  # noqa: E501
        else:
            legacy_token = self._client.get_xvcloud_authorization_token()
            self._tkg_client.set_default_header("x-vcloud-authorization", legacy_token)  # noqa: E501
        api_version = self._client.get_api_version()
        self._tkg_client.set_default_header("Accept", f"application/json;version={api_version}")  # noqa: E501
        org_logged_in = vcd_utils.get_org(self._client)
        org_id = org_logged_in.href.split('/')[-1]
        self._tkg_client.set_default_header("x-vmware-vcloud-tenant-context", org_id)  # noqa: E501
        self._tkg_client_api = TkgClusterApi(api_client=self._tkg_client)

    def get_tkg_cluster(self, cluster_id):
        """Sample method to use tkg_client.

        To be modified or removed as per the needs of CSE-CLI

        :param cluster_id: Id of the cluster
        :return: Tkg cluster
        :rtype: dict
        """
        # Returns tuple of response_data, response_status, response_headers,
        #   tkg_def_entities
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
            # TODO(TKGcluster): Owner filter not working
            # filters.append((cli_constants.TKGClusterEntityFilterKey.ORG_NAME.value, org))  # noqa: E501
            pass
        if vdc:
            filters.append((cli_constants.TKGClusterEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = None
        if filters:
            filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])
        # tkg_def_entities in the following statement represents the
        # information associated with the defined entity
        (entities, status, headers, tkg_def_entities) = \
            self._tkg_client_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}",  # noqa: E501
                _return_http_data_only=False,
                object_filter=filter_string)
        clusters = []
        for i in range(len(entities)):
            # NOTE: tkg_def_entities will contain corresponding defined entity
            # details
            entity: TkgCluster = entities[i]
            entity_properties = tkg_def_entities[i]
            logger.CLIENT_LOGGER.debug(f"TKG Defined entity list from server: {entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: entity.metadata.name, # noqa: E501
                cli_constants.CLIOutputKey.VDC.value: entity.metadata.virtual_data_center_name, # noqa: E501
                cli_constants.CLIOutputKey.ORG.value: entity_properties['org']['name'], # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: cli_constants.TKG_CLUSTER_RUNTIME, # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: entity.spec.distribution.version, # noqa: E501
                cli_constants.CLIOutputKey.STATUS.value: entity.status.phase if entity.status else 'N/A',  # noqa: E501
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
        entities = []
        tkg_def_entities = []
        if response:
            entities = response[0]
            tkg_def_entities = response[3]
        return entities, tkg_def_entities

    def apply(self, cluster_config: dict):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: str
        """
        try:
            cluster_name = cluster_config.get('metadata', {}).get('name')
            vdc_name = cluster_config.get('metadata', {}).get('virtualDataCenterName')  # noqa: E501
            tkg_entities, tkg_def_entities = self.get_tkg_clusters_by_name(cluster_name, vdc=vdc_name)  # noqa: E501
            if len(tkg_entities) == 0:
                response, status, headers, tkg_def_entities = \
                    self._tkg_client_api.create_tkg_cluster_with_http_info(tkg_cluster=cluster_config)  # noqa: E501
            elif len(tkg_entities) == 1:
                cluster_id = tkg_def_entities[0]['id']
                response, status, headers, tkg_def_entities = \
                    self._tkg_client_api.update_tkg_cluster_with_http_info(
                        tkg_cluster_id=cluster_id,
                        tkg_cluster=cluster_config)
            else:
                # More than 1 TKG cluster with the same name found.
                msg = f"Multiple clusters found with name {cluster_name}. " \
                      "Failed to apply the Spec."
                logger.CLIENT_LOGGER.error(msg)
                raise cse_exceptions.CseDuplicateClusterError(msg)
            # Retrieve the created TKG cluster details
            entity, tkg_def_entities = self.get_tkg_clusters_by_name(cluster_name)  # noqa: E501
            output_dict = entity[0].to_dict()
            # Get the task href from the header
            output_dict['task_href'] = headers.get('Location')
            return yaml.dump(output_dict)
        except tkg_rest.ApiException as e:
            msg = f"Error applying cluster spec: {e.reason}"
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"Error while applying cluster spec: {e}")  # noqa: E501
            raise

    def delete_cluster_by_id(self, cluster_id):
        """Delete a cluster using the cluster id.

        :param str cluster_id:
        :return: string representing the cluster entity.
        """
        try:
            response, status, headers, tkg_def_entities = \
                self._tkg_client_api.delete_tkg_cluster_with_http_info(tkg_cluster_id=cluster_id)  # noqa: E501
            tkg_cluster_dict = self.get_tkg_cluster(cluster_id)
            tkg_cluster_dict['task_href'] = headers.get('Location')
            return yaml.dump(tkg_cluster_dict)
        except tkg_rest.ApiException as e:
            msg = f"Error deleting cluster: {e.reason}"
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"Error deleting cluster: {e}")
            raise

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF native cluster by name.

        :param str cluster_name: native cluster name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: deleted cluster information
        :rtype: str
        :raises ClusterNotFoundError
        """
        try:
            entities, tkg_def_entities = \
                self.get_tkg_clusters_by_name(cluster_name, org=org, vdc=vdc)
            if len(entities) == 1:
                return self.delete_cluster_by_id(tkg_def_entities[0]['id'])
            elif len(entities) == 0:
                raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
            else:
                # More than 1 TKG cluster with the same name found.
                msg = f"Multiple clusters found with name {cluster_name}. " \
                      "Failed to apply the Spec."
                logger.CLIENT_LOGGER.error(msg)
                raise cse_exceptions.CseDuplicateClusterError(msg)
        except tkg_rest.ApiException as e:
            msg = f"Error deleting cluster: {e.reason}"
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"{e}")
            raise
