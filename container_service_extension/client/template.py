# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.response_processor \
    import process_response
import container_service_extension.shared_constants as shared_constants


class Template:
    def __init__(self, client):
        self.client = client
        self._uri = f"{self.client.get_api_uri()}/{shared_constants.CSE_URL_FRAGMENT}"  # noqa: E501

    def get_templates(self):
        method = shared_constants.RequestMethod.GET
        uri = f"{self._uri}/templates"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)
