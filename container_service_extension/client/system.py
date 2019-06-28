# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.response_processor \
    import process_response
from container_service_extension.shared_constants import SERVER_ACTION_KEY


class System(object):
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def get_info(self):
        method = 'GET'
        uri = f"{self._uri}/system"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)

    def update_service_status(self, action):
        method = 'PUT'
        uri = f"{self._uri}/system"
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents={SERVER_ACTION_KEY: action},
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)
