# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import OperationNotSupportedException

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
        # method = RequestMethod.GET
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)

    def get_cluster_info(self, name, org=None, vdc=None, **kwargs):
        """Get cluster information using DEF API.

        :param str vdc: name of vdc
        :param str org: name of org
        :param kwargs: *filter (dict): keys,values for DEF API query filter

        :return: cluster information
        :rtype: dict
        """
        # method = RequestMethod.GET
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)

    def __getattr__(self, name):
        msg = "Operation not supported; Under implementation"
        raise OperationNotSupportedException(msg)
