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
        """Iterate over paginated response until all the results are obtained.

        :param str base_url: initial url
        :param dict filters: filters for making the API call
        :returns: Generator which yields values and a boolean indicating if
            more results are present
        :rtype: Generator[(List[dict], bool), None, None]
        """
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
            yield processed_response[shared_constants.PaginationKey.VALUES], bool(url) # noqa: E501
