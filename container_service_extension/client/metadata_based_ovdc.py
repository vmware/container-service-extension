# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils
import pyvcloud.vcd.exceptions as vcd_exceptions

import container_service_extension.client.cse_client.api_33.ovdc_api as ovdc_api_v33  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.utils.pyvcloud_utils import get_vdc


class MetadataBasedOvdc:
    def __init__(self, client):
        self.client = client
        self._uri = f"{self.client.get_api_uri()}/{shared_constants.CSE_URL_FRAGMENT}"  # noqa: E501
        self._ovdc_api = ovdc_api_v33.OvdcApi(self.client)

    def list_ovdc(self):
        for ovdc_list, has_more_results in self._ovdc_api.get_all_ovdcs():  # noqa: E501
            yield ovdc_list, has_more_results

    # TODO(metadata based enablement for < v35): Revisit after decision
    # to support metadata way of enabling for native clusters
    def update_ovdc(self, ovdc_name, k8s_provider, **kwargs):
        """Enable/Disable ovdc for native workflow."""
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    def info_ovdc(self, ovdc_name, org_name):
        """Disable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the org VDC to be enabled
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        return self._ovdc_api.get_ovdc(ovdc_id)

    def update_ovdc_compute_policies(self, ovdc_name, org_name,
                                     compute_policy_name, action,
                                     remove_compute_policy_from_vms):
        """Update an ovdc's compute policies.

        :param str ovdc_name: Name of org VDC to update
        :param str org_name: Name of org that @ovdc_name belongs to
        :param str compute_policy_name: Name of compute policy to add or remove
        :param ComputePolicyAction action:

        :rtype: dict
        """
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        return self._ovdc_api.update_ovdc_compute_policies(ovdc_id,
                                                           compute_policy_name,
                                                           action,
                                                           force_remove=remove_compute_policy_from_vms)  # noqa: E501

    def list_ovdc_compute_policies(self, ovdc_name, org_name):
        """List an ovdc's compute policies.

        :param str ovdc_name: Name of org VDC to update
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        return self._ovdc_api.list_ovdc_compute_policies(ovdc_id)
