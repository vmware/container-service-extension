# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.exceptions as vcd_exceptions

import container_service_extension.client.response_processor as response_processor  # noqa: E501
import container_service_extension.client.utils as client_utils
from container_service_extension.def_ import models as def_models
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as cse_exceptions
from container_service_extension.logger import CLIENT_LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.shared_constants as shared_constants


class NativeCluster:
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param
        cluster resize where cluster kind specified as CLI param

    """

    def __init__(self, client):
        self._client = client
        self._uri = f"{self._client.get_api_uri()}/cse/{def_utils.V35_END_POINT_DISCRIMINATOR}"  # noqa: E501
        self._cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
            client=client, logger_debug=CLIENT_LOGGER)

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

    def delete_cluster(self, cluster_name, org=None, vdc=None):
        """Delete DEF native cluster by name.

        :param str cluster_name: native cluster name
        :param str org: name of the org
        :param str vdc: name of the vdc
        :return: requests.models.Response response
        :rtype: dict
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
        :return: requests.models.Response response
        :rtype: dict
        """
        uri = f"{self._uri}/cluster/{cluster_id}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.DELETE,
            uri,
            self._client._session,
            media_type='application/json',
            accept_type='application/json')
        return response_processor.process_response(response)

    def apply(self, cluster_config):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: requests.models.Response response
        :raises: exceptions.BadRequestError
        """
        uri = f"{self._uri}/clusters"
        method = shared_constants.RequestMethod.POST
        entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
        cluster_spec = def_models.ClusterEntity(**cluster_config)
        cluster_name = cluster_spec.metadata.cluster_name
        def_entity = entity_svc.get_native_entity_by_name(cluster_name)
        if not def_entity:
            response = self._client._do_request_prim(
                method,
                uri,
                self._client._session,
                contents=cluster_config,
                media_type='application/json',
                accept_type='application/json')
            return response_processor.process_response(response)
        else:
            # TODO(): Resize logic will be added here
            raise cse_exceptions.BadRequestError(
                f"Defined Entity for '{cluster_name}' already exists.",
                vcd_exceptions.ConflictException)
