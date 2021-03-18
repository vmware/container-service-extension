# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.cse_client.cse_client import CseClient
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501


class TemplatesApi(CseClient):
    def __init__(self, client: vcd_client.Client):
        super().__init__(client)
        self._uri = f"{self._uri}/{shared_constants.CSE_URL_FRAGMENT}"
        self._templates_uri = f"{self._uri}/templates"

    def list_templates(self):
        response = self.do_request(
            uri=self._templates_uri,
            method=shared_constants.RequestMethod.GET,
            accept_type='application/json')
        return self.process_response(response)
