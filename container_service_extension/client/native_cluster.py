# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.exceptions as vcd_exceptions

from container_service_extension.client.def_entity_cluster import DefEntityCluster  # noqa: E501
import container_service_extension.client.response_processor as response_processor  # noqa: E501
from container_service_extension.def_ import models as def_models
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.utils as def_utils
import container_service_extension.shared_constants as shared_constants


class NativeCluster(DefEntityCluster):
    """Handle operations that are specific to cluster kind 'native'.

    Examples:
        cluster apply
        cluster create where cluster kind specified as CLI param
        cluster resize where cluster kind specified as CLI param

    """

    def __init__(self, client):
        super().__init__(client)
        self._uri = f"{self._client.get_api_uri()}/cse/{def_utils.V35_END_POINT_DISCRIMINATOR}"  # noqa: E501

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

    def apply(self, cluster_config):
        """Apply the configuration either to create or update the cluster.

        :param dict cluster_config: cluster configuration information
        :return: requests.models.Response response
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
            return response_processor.process_response(response)
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
        return response_processor.process_response(response)

    def __getattr__(self, name):
        msg = "Operation not supported; Under *** implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)
