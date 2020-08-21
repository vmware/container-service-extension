# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

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
import container_service_extension.shared_constants as shared_constants


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
            self._tkg_client.set_default_header(cli_constants.TKGRequestHeaderKey.AUTHORIZATION,  # noqa: E501
                                                f"Bearer {jwt_token}")
        else:
            legacy_token = self._client.get_xvcloud_authorization_token()
            self._tkg_client.set_default_header(cli_constants.TKGRequestHeaderKey.X_VCLOUD_AUTHORIZATION,  # noqa: E501
                                                legacy_token)
        api_version = self._client.get_api_version()
        self._tkg_client.set_default_header(cli_constants.TKGRequestHeaderKey.ACCEPT,  # noqa: E501
                                            f"application/json;version={api_version}")  # noqa: E501
        org_logged_in = vcd_utils.get_org(self._client)
        org_id = org_logged_in.href.split('/')[-1]
        # TODO setting right tenant context for sysadmin users
        self._tkg_client.set_default_header(cli_constants.TKGRequestHeaderKey.X_VMWARE_VCLOUD_TENANT_CONTEXT,  # noqa: E501
                                            org_id)
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
            filters.append((cli_constants.TKGEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = None
        if filters:
            filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])
        # tkg_def_entities in the following statement represents the
        # information associated with the defined entity
        response = \
            self._tkg_client_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}",  # noqa: E501
                _return_http_data_only=False,
                _preload_content=False,
                object_filter=filter_string)
        def_entities = json.loads(response[0].data)['values']
        clusters = []
        for def_entity in def_entities:
            # NOTE: tkg_def_entities will contain corresponding defined entity
            # details
            entity = def_entity.get('entity', {})
            metadata = entity.get('metadata', {})
            spec = entity.get('spec', {})
            logger.CLIENT_LOGGER.debug(f"TKG Defined entity list from server: {def_entity}")  # noqa: E501
            cluster = {
                cli_constants.CLIOutputKey.CLUSTER_NAME.value: metadata.get('name', 'N/A'),  # noqa: E501
                cli_constants.CLIOutputKey.VDC.value: metadata.get('virtualDataCenterName', 'N/A'),  # noqa: E501
                cli_constants.CLIOutputKey.ORG.value: def_entity.get('org', {}).get('name', 'N/A'),  # noqa: E501
                cli_constants.CLIOutputKey.K8S_RUNTIME.value: cli_constants.TKG_CLUSTER_RUNTIME,  # noqa: E501
                cli_constants.CLIOutputKey.STATUS.value: entity.get('status', {}).get('phase', 'N/A'),  # noqa: E501
                cli_constants.CLIOutputKey.K8S_VERSION.value: spec.get('distribution', {}).get('version', 'N/A'),  # noqa: E501
                cli_constants.CLIOutputKey.OWNER.value: def_entity.get('owner', {}).get('name', 'N/A'),  # noqa: E501
            }
            clusters.append(cluster)
        return clusters

    def get_tkg_clusters_by_name(self, name, vdc=None, org=None):
        filters = [(cli_constants.TKGEntityFilterKey.CLUSTER_NAME.value, name)]
        if org:
            # TODO(Org filed for TKG): Add filter once schema is updated
            pass
        if vdc:
            filters.append((cli_constants.TKGEntityFilterKey.VDC_NAME.value, vdc))  # noqa: E501
        filter_string = ";".join([f"{f[0]}=={f[1]}" for f in filters])
        response = \
            self._tkg_client_api.list_tkg_clusters(
                f"{DEF_VMWARE_VENDOR}/{DEF_TKG_ENTITY_TYPE_NSS}/{DEF_TKG_ENTITY_TYPE_VERSION}", # noqa: E501
                _preload_content=False,
                object_filter=filter_string)
        tkg_def_entities = []
        if response:
            tkg_def_entities = json.loads(response[0].data)['values']
        return tkg_def_entities

    def get_cluster_info(self, cluster_name, org=None, vdc=None):
        """Get cluster information of a TKG cluster API.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError
        """
        tkg_entities = self.get_tkg_clusters_by_name(cluster_name, vdc=vdc, org=org)  # noqa: E501
        if len(tkg_entities) == 0:
            msg = f"Cluster '{cluster_name}' not found."
            logger.CLIENT_LOGGER.error(msg)
            raise cse_exceptions.ClusterNotFoundError(msg)
        cluster_entity = tkg_entities[0]['entity']
        logger.CLIENT_LOGGER.debug(
            f"Received defined entity of cluster {cluster_name} : {cluster_entity}")  # noqa: E501
        return yaml.dump(cluster_entity)

    def apply(self, cluster_config: dict):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: string containing the task href for the operation
        :rtype: str
        """
        try:
            cluster_name = cluster_config.get('metadata', {}).get('name')
            vdc_name = cluster_config.get('metadata', {}).get('virtualDataCenterName')  # noqa: E501
            tkg_def_entities = self.get_tkg_clusters_by_name(cluster_name, vdc=vdc_name)  # noqa: E501
            if len(tkg_def_entities) == 0:
                response = \
                    self._tkg_client_api.create_tkg_cluster_with_http_info(tkg_cluster=cluster_config)  # noqa: E501
            elif len(tkg_def_entities) == 1:
                cluster_id = tkg_def_entities[0]['id']
                response = \
                    self._tkg_client_api.update_tkg_cluster_with_http_info(
                        tkg_cluster_id=cluster_id,
                        tkg_cluster=cluster_config)
            else:
                # More than 1 TKG cluster with the same name found.
                msg = f"Multiple clusters found with name {cluster_name}. " \
                      "Failed to apply the Spec."
                logger.CLIENT_LOGGER.error(msg)
                raise cse_exceptions.CseDuplicateClusterError(msg)
            # Get the task href from the header
            headers = response[2]
            output = f"task_href: {headers.get('Location')}"
            return output
        except tkg_rest.ApiException as e:
            server_message = json.loads(e.body).get('message') or e.reason
            msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{server_message}")  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"Error while applying cluster spec: {e}")  # noqa: E501
            raise

    def delete_cluster_by_id(self, cluster_id):
        """Delete a cluster using the cluster id.

        :param str cluster_id:
        :return: string containing the task href of delete cluster operation
        """
        try:
            response = \
                self._tkg_client_api.delete_tkg_cluster_with_http_info(tkg_cluster_id=cluster_id)  # noqa: E501
            headers = response[2]
            return f"task_href: {headers.get('Location')}"
        except tkg_rest.ApiException as e:
            msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{e.reason}")  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"Error deleting cluster: {e}")
            raise

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete TKG cluster by name.

        :param str cluster_name: TKG cluster name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: string containing delete cluster task href
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        try:
            tkg_def_entities = \
                self.get_tkg_clusters_by_name(cluster_name, org=org, vdc=vdc)
            if len(tkg_def_entities) == 1:
                return self.delete_cluster_by_id(tkg_def_entities[0]['id'])
            elif len(tkg_def_entities) == 0:
                raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
            else:
                # More than 1 TKG cluster with the same name found.
                msg = f"Multiple clusters found with name {cluster_name}. " \
                      "Failed to delete the TKG cluster."
                logger.CLIENT_LOGGER.error(msg)
                raise cse_exceptions.CseDuplicateClusterError(msg)
        except tkg_rest.ApiException as e:
            server_message = json.loads(e.body).get('message') or e.reason
            msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{server_message}")  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"{e}")
            raise

    def get_cluster_config_by_id(self, cluster_id, org_urn):
        """Get TKG cluster config by cluster id.

        :param str cluster_id: ID of the cluster
        :param str org_urn: URN of the org
        :return the cluster config of the TKG cluster
        :rtype: str
        """
        try:
            # set org-id extracted from org-urn in the header
            org_id = vcd_utils.extract_id(org_urn)
            self._tkg_client.set_default_header(cli_constants.TKGRequestHeaderKey.X_VMWARE_VCLOUD_TENANT_CONTEXT,  # noqa: E501
                                                org_id)
            response, status, headers = \
                self._tkg_client_api.create_tkg_cluster_config_task(id=cluster_id)  # noqa: E501

            # Extract the task for creating the config from the Location header
            config_task_href = headers.get('Location')
            if not config_task_href:
                raise Exception(f"Failed to fetch kube-config for TKG cluster {cluster_id}")  # noqa: E501
            config_task = self._client.get_resource(config_task_href)
            self._client.get_task_monitor().wait_for_success(config_task)
            config_task = self._client.get_resource(config_task_href)
            return {shared_constants.RESPONSE_MESSAGE_KEY: config_task.Result.ResultContent.text}  # noqa: E501
        except tkg_rest.ApiException as e:
            server_message = json.loads(e.body).get('message') or e.reason
            msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{server_message}")  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"{e}")
            raise

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        """Get TKG cluster config by cluster name.

        :param str cluster_name: name of the cluster
        :param str org: name of the org
        :param str vdc: name of the vdc
        """
        try:
            tkg_def_entities = \
                self.get_tkg_clusters_by_name(cluster_name, org=org, vdc=vdc)
            if len(tkg_def_entities) == 1:
                return self.get_cluster_config_by_id(
                    tkg_def_entities[0]['id'],
                    org_urn=tkg_def_entities[0]['org']['id'])
            elif len(tkg_def_entities) == 0:
                raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
            else:
                # More than 1 TKG cluster with the same name found.
                msg = f"Multiple clusters found with name {cluster_name}. " \
                      "Failed to fetch kube-config."
                logger.CLIENT_LOGGER.error(msg)
                raise cse_exceptions.CseDuplicateClusterError(msg)
        except tkg_rest.ApiException as e:
            server_message = json.loads(e.body).get('message') or e.reason
            msg = cli_constants.TKG_RESPONSE_MESSAGES_BY_STATUS_CODE.get(e.status, f"{server_message}")  # noqa: E501
            logger.CLIENT_LOGGER.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.CLIENT_LOGGER.error(f"{e}")
            raise
