# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from pyvcloud.vcd import utils
import pyvcloud.vcd.exceptions as vcd_exceptions

import container_service_extension.client.cse_client.api_35.ovdc_api as ovdc_api_v35  # noqa: E501
import container_service_extension.client.utils as client_utils
from container_service_extension.common.utils.pyvcloud_utils import get_vdc
import container_service_extension.rde.models.common_models as common_models


class PolicyBasedOvdc:
    def __init__(self, client):
        self.client = client
        self._ovdc_api = ovdc_api_v35.OvdcApi(self.client)

    def list_ovdc(self):
        for ovdc_list, has_more_results in self._ovdc_api.get_all_ovdcs():
            value_field_to_display_field = {
                'ovdc_name': 'Name',
                'ovdc_id': 'ID',
                'k8s_runtime': 'K8s Runtime'
            }
            yield client_utils.filter_columns(ovdc_list, value_field_to_display_field), has_more_results  # noqa: E501

    def update_ovdc(self, ovdc_name, k8s_runtime, enable=True, org_name=None,
                    remove_cp_from_vms_on_disable=False):
        """Enable/Disable ovdc for k8s for the given k8s provider.

        :param str ovdc_name: Name of org VDC to update
        :param List[str] k8s_runtime: k8s_runtime of the k8s provider to
        enable / disable for the ovdc
        :param bool enable: If set to True will enable the vdc for the
            paricular k8s_runtime else if set to False, K8 support on
            the vdc will be disabled.
        :param str org_name: Name of org that @ovdc_name belongs to
        :param bool remove_cp_from_vms_on_disable: If set to True and
            enable is False, then all the vms in the ovdc having policies for
            the k8s_runtime is deleted.

        :rtype: dict
        """
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        curr_ovdc = self._ovdc_api.get_ovdc(ovdc_id)
        runtimes = curr_ovdc.k8s_runtime
        for k in k8s_runtime:
            if enable:
                if k in runtimes:
                    raise Exception(f"OVDC {ovdc_name} already enabled for {k}") # noqa: E501
                runtimes.append(k)
            else:
                if k not in runtimes:
                    raise Exception(f"OVDC {ovdc_name} already disabled for {k}") # noqa: E501
                runtimes.remove(k)
        updated_ovdc = common_models.Ovdc(
            k8s_runtime=runtimes,
            org_name=org_name,
            remove_cp_from_vms_on_disable=remove_cp_from_vms_on_disable)
        return self._ovdc_api.update_ovdc(ovdc_id, updated_ovdc)

    def info_ovdc(self, ovdc_name, org_name):
        """Disable ovdc for given kubernetes runtime.

        :param str ovdc_name: Name of the org VDC to be enabled
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        raise NotImplementedError("OVDC info functionality is not supported "
                                  "for the installed CSE version.")

    # TODO(compute-policy for v35): Revisit after decision on api v35 support
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
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)

    # TODO(compute-policy for v35): Revisit after decision on api v35 support
    def list_ovdc_compute_policies(self, ovdc_name, org_name):
        """List an ovdc's compute policies.

        :param str ovdc_name: Name of org VDC to update
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)
