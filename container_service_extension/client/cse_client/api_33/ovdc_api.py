# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class OvdcApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}"
        self._org_vdcs_uri = f"{self._uri}/orgvdcs"
        self._ovdc_uri = f"{self._uri}/ovdc"

    def get_all_ovdcs(self):
        filters = {
            shared_constants.PaginationKey.PAGE_SIZE.value: self._request_page_size  # noqa: E501
        }
        return self.iterate_results(self._org_vdcs_uri, filters=filters)

    def get_ovdc(self, ovdc_id):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')

        return self.process_response(response)

    def update_ovdc_compute_policies(self, ovdc_id, compute_policy_name,
                                     compute_policy_action, force_remove=False):  # noqa: E501
        uri = f"{self._ovdc_uri}/{ovdc_id}/compute-policies"
        payload = {
            shared_constants.RequestKey.OVDC_ID: ovdc_id,  # also exists in url
            shared_constants.RequestKey.COMPUTE_POLICY_NAME: compute_policy_name,  # noqa: E501
            shared_constants.RequestKey.COMPUTE_POLICY_ACTION: compute_policy_action,  # noqa: E501
            shared_constants.RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS: force_remove  # noqa: E501
        }
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)

        return self.process_response(response)

    def list_ovdc_compute_policies(self, ovdc_id):
        uri = f'{self._ovdc_uri}/{ovdc_id}/compute-policies'
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')

        return self.process_response(response)
