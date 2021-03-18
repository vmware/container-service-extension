# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.rde.models.common_models as common_models


class OvdcApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{ shared_constants.CSE_URL_FRAGMENT}/" \
                    f"{shared_constants.CSE_3_0_URL_FRAGMENT}"
        self._org_vdcs_uri = f"{self._uri}/orgvdcs"
        self._ovdc_uri = f"{self._uri}/ovdc"
        self._request_page_size = 10

    def get_all_ovdcs(self):
        """Iterate over all the get ovdc response page by page.

        :returns: Yields the list of values in the page and a boolean
            indicating if there are more results.
        :rtype: Generator[(List[dict], int), None, None]
        """
        url = f"{self._org_vdcs_uri}?" \
              f"{shared_constants.PaginationKey.PAGE_SIZE.value}={self._request_page_size}"  # noqa: E501
        return self.iterate_results(url)

    def get_ovdc(self, ovdc_id):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')

        return common_models.Ovdc(**self.process_response(response))

    def update_ovdc(self, ovdc_id, ovdc_obj: common_models.Ovdc):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self.do_request(
            uri=uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=asdict(ovdc_obj))

        return self.process_response(response)
