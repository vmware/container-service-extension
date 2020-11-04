# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.cse_client.templates_api import TemplatesApi  # noqa: E501


class Template:
    def __init__(self, client):
        self._templates_api = TemplatesApi(client)

    def get_templates(self):
        return self._templates_api.list_templates()
