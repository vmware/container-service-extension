# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class PksOvdcApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.PKS_URL_FRAGMENT}"
        self._org_vdcs_uri = f"{self._uri}/orgvdcs"
        self._ovdc_uri = f"{self._uri}/ovdc"

    def get_all_ovdcs(self, filters=None):
        if filters is None:
            filters = {}
        filters[shared_constants.PaginationKey.PAGE_SIZE.value] = self._request_page_size  # noqa: E501

        return self.iterate_results(self._org_vdcs_uri, filters=filters)

    def get_ovdc(self, ovdc_id):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')
        return self.process_response(response)

    def update_ovdc_by_ovdc_id(self, ovdc_id, k8s_provider, ovdc_name=None,
                               org_name=None, pks_plan=None, pks_cluster_domain=None):  # noqa: E501
        payload = {
            shared_constants.RequestKey.OVDC_ID: ovdc_id,
            shared_constants.RequestKey.OVDC_NAME: ovdc_name,
            shared_constants.RequestKey.ORG_NAME: org_name,
            shared_constants.RequestKey.K8S_PROVIDER: k8s_provider,
            shared_constants.RequestKey.PKS_PLAN_NAME: pks_plan,
            shared_constants.RequestKey.PKS_CLUSTER_DOMAIN: pks_cluster_domain
        }
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)
