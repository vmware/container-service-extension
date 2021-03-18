# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class SystemApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}"
        self._system_uri = f"{self._uri}/system"

    def get_system_details(self):
        response = self.do_request(
            uri=self._system_uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')
        return self.process_response(response)

    def update_system(self, action):
        payload = {
            shared_constants.RequestKey.SERVER_ACTION: action
        }
        response = self.do_request(
            uri=self._system_uri,
            method=shared_constants.RequestMethod.PUT,
            accept_type='application/json',
            media_type='application/json',
            payload=payload)
        return self.process_response(response)
