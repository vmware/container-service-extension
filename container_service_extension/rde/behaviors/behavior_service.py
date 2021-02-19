# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict

import container_service_extension.common.constants.shared_constants as cse_shared_constants  # noqa: E501
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.lib.cloudapi.constants import CloudApiResource
from container_service_extension.lib.cloudapi.constants import CloudApiVersion
from container_service_extension.rde.behaviors.behavior_model import Behavior
import container_service_extension.rde.utils as def_utils


class BehaviorService:
    def __init__(self, cloudapi_client: CloudApiClient):
        def_utils.raise_error_if_def_not_supported(cloudapi_client)
        self._cloudapi_client = cloudapi_client

    def create_behavior_on_interface(self, behavior: Behavior, interface_id):
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}",
            payload=asdict(behavior))
        return Behavior(**response_body)

    def update_behavior_on_interface(self, behavior: Behavior, interface_id):
        if not self._cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.PUT,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior.id}",
            payload=asdict(behavior))
        return Behavior(**response_body)

    def list_behaviors_on_interface(self, interface_id):
        page_num = 0
        while True:
            page_num += 1
            response_body = self._cloudapi_client.do_request(
                method=cse_shared_constants.RequestMethod.GET,
                cloudapi_version=CloudApiVersion.VERSION_1_0_0,
                resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                           f"/{interface_id}"
                                           f"/{CloudApiResource.BEHAVIORS}?"
                                           f"page={page_num}")
            if len(response_body['values']) > 0:
                for behavior in response_body['values']:
                    yield Behavior(**behavior)
            else:
                break

    def get_behavior_on_interface_by_id(self, behavior_id, interface_id):
        response_body = self._cloudapi_client.do_request(
            method=cse_shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.INTERFACES}"
                                       f"/{interface_id}"
                                       f"/{CloudApiResource.BEHAVIORS}"
                                       f"/{behavior_id}")
        return Behavior(**response_body)

    def get_behavior_on_interface_by_name(self, behavior_name, interface_id):
        behaviors = self.list_behaviors_on_interface(interface_id=interface_id)
        matched_behaviors = [behavior for behavior in behaviors
                             if behavior.name == behavior_name]
        return matched_behaviors[0]
