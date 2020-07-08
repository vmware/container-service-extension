# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import pyvcloud.vcd.exceptions as vcd_exceptions

import container_service_extension.def_.entity_service as def_entity_svc
from container_service_extension.def_.utils import ClusterEntityFilterKey
import container_service_extension.exceptions as cse_exceptions
from container_service_extension.logger import CLIENT_LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils


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

    def __getattr__(self, name):
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)
