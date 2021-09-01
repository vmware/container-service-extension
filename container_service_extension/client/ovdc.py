# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.vcd_api_version import VCDApiVersion

from container_service_extension.client.metadata_based_ovdc import MetadataBasedOvdc  # noqa: E501
from container_service_extension.client.policy_based_ovdc import PolicyBasedOvdc  # noqa: E501


class Ovdc:
    """Returns the ovdc class as determined by API version."""

    def __new__(cls, client: vcd_client.Client):
        """Create the right ovdc class for the negotiated API version.

        For apiVersion < 35 return MetadataBasedOvdc class
        For apiVersoin >= 35 return PolicyBasedOvdc class

        :param pyvcloud.vcd.client client: vcd client
        :return: instance of version specific client side Ovdc class
        """
        api_version = client.get_api_version()
        if VCDApiVersion(api_version) < VCDApiVersion(vcd_client.ApiVersion.VERSION_35.value):  # noqa: E501
            return MetadataBasedOvdc(client)
        elif VCDApiVersion(api_version) >= VCDApiVersion(vcd_client.ApiVersion.VERSION_35.value):  # noqa: E501
            return PolicyBasedOvdc(client)
