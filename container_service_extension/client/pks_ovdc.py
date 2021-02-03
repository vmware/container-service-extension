# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils

from container_service_extension.client.cse_client.pks_ovdc_api import PksOvdcApi  # noqa: E501
import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.utils.pyvcloud_utils import get_vdc


class PksOvdc:
    def __init__(self, client):
        self.client = client
        self._uri = f"{self.client.get_api_uri()}/{shared_constants.PKS_URL_FRAGMENT}"  # noqa: E501
        self._pks_ovdc_api = PksOvdcApi(client)

    def list_ovdc(self, list_pks_plans=False):
        filters = {shared_constants.RequestKey.LIST_PKS_PLANS: list_pks_plans}
        for ovdc_list, has_more_results in self._pks_ovdc_api.get_all_ovdcs(filters=filters):  # noqa: E501
            yield ovdc_list, has_more_results

    def update_ovdc(self, enable, ovdc_name, org_name=None,
                    pks_plan=None, pks_cluster_domain=None):
        """Enable/Disable ovdc for k8s for the given container provider.

        :param bool enable: If set to True will enable the vdc for the
            paricular k8s_provider else if set to False, K8 support on
            the vdc will be disabled.
        :param str ovdc_name: Name of org VDC to update
        :param str org_name: Name of org that @ovdc_name belongs to
        :param str pks_plan: PKS plan
        :param str pks_cluster_domain: Suffix of the domain name, which will be
         used to construct FQDN of the clusters.

        :rtype: dict
        """
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))

        k8s_provider = server_constants.K8sProvider.PKS
        if not enable:
            k8s_provider = server_constants.K8sProvider.NONE
            pks_plan = None
            pks_cluster_domain = None

        return self._pks_ovdc_api.update_ovdc_by_ovdc_id(ovdc_id,
                                                         k8s_provider,
                                                         ovdc_name=ovdc_name,
                                                         org_name=org_name,
                                                         pks_plan=pks_plan,
                                                         pks_cluster_domain=pks_cluster_domain)  # noqa: E501

    def info_ovdc(self, ovdc_name, org_name):
        """Disable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the org VDC to be enabled
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        return self._pks_ovdc_api.get_ovdc(ovdc_id)
