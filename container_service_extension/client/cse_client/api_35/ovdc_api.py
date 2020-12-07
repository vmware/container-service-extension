# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
from container_service_extension.client.response_processor import process_response  # noqa: E501
import container_service_extension.def_.models as def_models
import container_service_extension.shared_constants as shared_constants


class OvdcApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}/" \
                    f"{shared_constants.CSE_3_0_URL_FRAGMENT}"
        self._ovdcs_uri = f"{self._uri}/ovdcs"
        self._ovdc_uri = f"{self._uri}/ovdc"
        self._request_page_size = 5

    def get_all_ovdcs(self):
        """Iterate over all the get ovdc response page by page.

        :returns: Yields the list of values in the page and a boolean
            indicating if there are more results.
        :rtype: Generator[(List[dict], int), None, None]
        """
        url = f"{self._ovdcs_uri}?pageSize={self._request_page_size}"
        return self.iterate_results(url)

    def get_ovdc(self, ovdc_id):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        response = self._client._do_request_prim(
            shared_constants.RequestMethod.GET,
            uri,
            self._client._session,
            accept_type='application/json')
        return def_models.Ovdc(**process_response(response))

    def update_ovdc(self, ovdc_id, ovdc_obj: def_models.Ovdc):
        uri = f"{self._ovdc_uri}/{ovdc_id}"
        resp = self._client._do_request_prim(
            shared_constants.RequestMethod.PUT,
            uri,
            self._client._session,
            contents=asdict(ovdc_obj),
            media_type='application/json',
            accept_type='application/json')
        return process_response(resp)
