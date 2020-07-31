# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import os

import pyvcloud.vcd.exceptions as vcd_exceptions
import yaml

import container_service_extension.client.constants as cli_constants
import container_service_extension.client.response_processor as response_processor  # noqa: E501
import container_service_extension.client.utils as client_utils
from container_service_extension.def_ import models as def_models
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.shared_constants as shared_constants


class NativeClusterApi:
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param
        cluster resize where cluster kind specified as CLI param

    """

    def __init__(self, client):
        self._client = client
        self._uri = f"{self._client.get_api_uri()}/cse/{def_utils.V35_END_POINT_DISCRIMINATOR}"  # noqa: E501
        logger_wire = logger.NULL_LOGGER
        if os.getenv(cli_constants.ENV_CSE_CLIENT_WIRE_LOGGING):
            logger_wire = logger.CLIENT_WIRE_LOGGER
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(
                client=client, logger_debug=logger.CLIENT_LOGGER,
                logger_wire=logger_wire)

    def create_cluster(self, cluster_entity: def_models.ClusterEntity):
        """Create a new Kubernetes cluster.

        :param models.ClusterEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    def resize_cluster(self, cluster_entity: def_models.ClusterEntity):
        """Resize the existing Kubernetes cluster.

        :param models.ClusterEntity cluster_entity: native cluster entity
        :return: (json) A parsed json object describing the requested cluster.
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    def get_cluster_info(self, cluster_name, org=None, vdc=None, **kwargs):
        """Get cluster information using DEF API.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster information
        :rtype: dict
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        logger.CLIENT_LOGGER.debug(f"Defined entity info from server:{def_entity}")  # noqa: E501
        if not def_entity:
            raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501
        # TODO() relevant output
        if def_entity:
            return yaml.dump(asdict(def_entity.entity))

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF native cluster by name.

        :param str cluster_name: native cluster name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: deleted cluster information
        :rtype: str
        :raises ClusterNotFoundError
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if def_entity:
            return self.delete_cluster_by_id(def_entity.id)
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def delete_cluster_by_id(self, cluster_id):
        """Delete the existing Kubernetes cluster by id.

        :param str cluster_id: native cluster entity id
        :return: decoded response content
        :rtype: str
        """
        uri = f"{self._uri}/cluster/{cluster_id}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.DELETE,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return yaml.dump(response_processor.process_response(response))

    def get_cluster_config(self, cluster_name, org=None, vdc=None):
        """Get cluster config for the given cluster name.

        :param str cluster_name: name of the cluster
        :param str vdc: name of vdc
        :param str org: name of org

        :return: cluster information
        :rtype: str
        :raises ClusterNotFoundError, CseDuplicateClusterError
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if def_entity:
            return self.get_cluster_config_by_id(def_entity.id)
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def get_cluster_config_by_id(self, cluster_id):
        """Get the cluster config for given cluster id.

        :param str cluster_id: native cluster entity id
        :return: decoded response content
        :rtype: dict
        """
        uri = f"{self._uri}/cluster/{cluster_id}/config"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)

    def get_upgrade_plan(self, cluster_name, org=None, vdc=None):
        """Get the upgrade plan for given cluster.

        :param cluster_name: name of the cluster
        :param org: name of the org
        :param vdc: name of the vdc
        :return: upgrade plan info
        :rtype: dict
        """
        filters = client_utils.construct_filters(org=org, vdc=vdc)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        def_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if def_entity:
            return self.get_upgrade_plan_by_cluster_id(def_entity.id)
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def get_upgrade_plan_by_cluster_id(self, cluster_id):
        """Get the upgrade plan for give cluster id.

        :param cluster_id: unique id of the cluster
        :return: decoded response content
        :rtype: list
        """
        uri = f'{self._uri}/cluster/{cluster_id}/upgrade-plan'
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            accept_type='application/json')
        return response_processor.process_response(response)

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
        filters = client_utils.construct_filters(org=org_name, vdc=ovdc_name)
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        current_entity = entity_svc.get_native_entity_by_name(name=cluster_name, filters=filters)  # noqa: E501
        if current_entity:
            current_entity.entity.spec.k8_distribution.template_name = template_name  # noqa: E501
            current_entity.entity.spec.k8_distribution.template_revision = template_revision  # noqa: E501
            return self.upgrade_cluster_by_cluster_id(current_entity.id, cluster_entity=asdict(current_entity))  # noqa: E501
        raise cse_exceptions.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")  # noqa: E501

    def upgrade_cluster_by_cluster_id(self, cluster_id, cluster_entity):
        """Get the upgrade plan for give cluster id.

        :param str cluster_id: unique id of the cluster
        :param dict cluster_entity: defined entity
        :return: requests.models.Response response
        :rtype: dict
        """
        uri = f'{self._uri}/cluster/{cluster_id}/action/upgrade'
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.POST,
            uri,
            self._client._session,
            contents=cluster_entity['entity'],
            media_type='application/json',
            accept_type='application/json')
        return yaml.dump(response_processor.process_response(response)['entity']) # noqa: E501

    def apply(self, cluster_config):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: str
        """
        uri = f"{self._uri}/clusters"
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        cluster_spec = def_models.ClusterEntity(**cluster_config)
        cluster_name = cluster_spec.metadata.cluster_name
        def_entity = entity_svc.get_native_entity_by_name(cluster_name)
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
