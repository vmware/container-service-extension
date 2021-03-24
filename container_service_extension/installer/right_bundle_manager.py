# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Claus

import pyvcloud.vcd.client as vcd_client

import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
from container_service_extension.lib.cloudapi.constants import CloudApiResource
from container_service_extension.lib.cloudapi.constants import CloudApiVersion
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.logging.logger import SERVER_CLOUDAPI_WIRE_LOGGER  # noqa: E501


class RightBundleManager():
    def __init__(self, sysadmin_client: vcd_client.Client,
                 log_wire=False, logger_debug=NULL_LOGGER):
        vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
        self.logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER \
            if log_wire else NULL_LOGGER
        self.logger_debug = logger_debug
        self.cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
            sysadmin_client,
            logger_debug=self.logger_debug,
            logger_wire=self.logger_wire)

    def get_right_bundle_by_name(self, right_bundle_name):
        """Get Right bundle by name.

        :param: right_bundle_name: string
        :returns: right bundle json object
        """
        filters = {'name': right_bundle_name}
        filter_string = utils.construct_filter_string(filters)
        query_string = ""
        if filter_string:
            query_string = f"filter={filter_string}"
        response_body = self.cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.RIGHT_BUNDLES}?{query_string}")  # noqa: E501
        right_bundles = response_body['values']
        if right_bundles and len(right_bundles) > 0:
            return right_bundles[0]

    def publish_cse_right_bundle_to_tenants(self, right_bundle_id,
                                            org_ids):
        """Publish the right-bundle to tenants.

        Accepts the right-bundle-id as an argument, and publishes to the
        organization indicated by org-id
        :param: right_bundle_id: id of the right bundle, string
        :param: id of the org, string
        :returns: HTTP response of the request
        """
        relative_url = \
            f"{CloudApiResource.RIGHT_BUNDLES}/{right_bundle_id}" \
            "/tenants/publish"
        payload = {
            "values": [
                {"id": self.cloudapi_client.get_org_urn_from_id(org_id)}
                for org_id in org_ids
            ]
        }

        return self.cloudapi_client.do_request(
            method=shared_constants.RequestMethod.POST,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=relative_url,
            payload=payload)

    def get_rights_for_right_bundle(self, right_bundle_name):
        """Get Rights for a right bundle.

        Queries VCD for the list of rights associated with a right bundle.
        :param: right_bundle_name: name of the right bundle, string
        :returns: right bundle info json object, the "values" key for this json
        object will have list of rights
        """
        right_bundle_info = self.get_right_bundle_by_name(right_bundle_name)
        right_bundle_id = right_bundle_info['id']
        relative_url = f"{CloudApiResource.RIGHT_BUNDLES}/{right_bundle_id}/rights"  # noqa: E501

        rights = self.cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=relative_url)

        return rights
