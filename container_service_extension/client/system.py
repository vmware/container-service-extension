# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.client.cse_client.system_api import SystemApi


class System:
    def __init__(self, client):
        self._system_api = SystemApi(client)

    def get_info(self):
        return self._system_api.get_system_details()

    def update_service_status(self, action):
        return self._system_api.update_system(action)
