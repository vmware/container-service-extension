# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.response_processor import process_response  # noqa: E501
import container_service_extension.shared_constants as shared_constants


class CseClient:
    def __init__(self, client: vcd_client.Client):
        self._client = client
        self._uri = self._client.get_api_uri()
        self._request_page_size = 3

    def iterate_results(self, base_url, filters={}):
        url = base_url
        while url:
            response = self._client._do_request_prim(
                shared_constants.RequestMethod.GET,
                url,
                self._client._session,
                accept_type='application/json',
                params=filters)
            processed_response = process_response(response)
            url = processed_response.get(shared_constants.PaginationKey.NEXT_PAGE_URI)  # noqa: E501
            has_more_results = False
            if url:
                has_more_results = True
            yield processed_response[shared_constants.PaginationKey.VALUES], has_more_results # noqa: E501
