# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict

from pyvcloud.vcd import utils
import pyvcloud.vcd.exceptions as vcd_exceptions

from container_service_extension.client.response_processor import \
    process_response
import container_service_extension.def_.models as def_models
from container_service_extension.pyvcloud_utils import get_vdc
import container_service_extension.shared_constants as shared_constants


class PolicyBasedOvdc:
    def __init__(self, client):
        self.client = client
        self._uri = f"{self.client.get_api_uri()}/{shared_constants.CSE_URL_FRAGMENT}/{shared_constants.CSE_3_0_URL_FRAGMENT}"  # noqa: E501

    def list_ovdc(self):
        method = shared_constants.RequestMethod.GET
        uri = f'{self._uri}/ovdcs'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)

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
        method = shared_constants.RequestMethod.PUT
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}'

        # fetch existing k8s providers
        ovdc_response = self.client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self.client._session,
            accept_type='application/json')
        curr_ovdc = def_models.Ovdc(**process_response(ovdc_response))
        runtimes = curr_ovdc.k8s_runtime
        for k in k8s_runtime:
            if enable:
                if k in runtimes:
                    raise Exception(f"OVDC {ovdc_name} already enabled for {k8s_runtime}") # noqa: E501
                runtimes.append(k)
            else:
                if k not in runtimes:
                    raise Exception(f"OVDC {ovdc_name} already disabled for {k8s_runtime}") # noqa: E501
                runtimes.remove(k)
        update_request = def_models.Ovdc(
            k8s_runtime=runtimes,
            remove_cp_from_vms_on_disable=remove_cp_from_vms_on_disable)

        resp = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=asdict(update_request),
            media_type='application/json',
            accept_type='application/json')
        return process_response(resp)

    def info_ovdc(self, ovdc_name, org_name):
        """Disable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the org VDC to be enabled
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        method = shared_constants.RequestMethod.GET
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}'

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)

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
        method = shared_constants.RequestMethod.PUT
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}/compute-policies'

        data = {
            shared_constants.RequestKey.OVDC_ID: ovdc_id, # also exists in url
            shared_constants.RequestKey.COMPUTE_POLICY_NAME: compute_policy_name,  # noqa: E501
            shared_constants.RequestKey.COMPUTE_POLICY_ACTION: action,
            shared_constants.RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS: remove_compute_policy_from_vms # noqa: E501
        }

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    # TODO(compute-policy for v35): Revisit after decision on api v35 support
    def list_ovdc_compute_policies(self, ovdc_name, org_name):
        """List an ovdc's compute policies.

        :param str ovdc_name: Name of org VDC to update
        :param str org_name: Name of org that @ovdc_name belongs to

        :rtype: dict
        """
        msg = "Operation not supported; Under implementation"
        raise vcd_exceptions.OperationNotSupportedException(msg)
        method = shared_constants.RequestMethod.GET
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}/compute-policies'

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)
