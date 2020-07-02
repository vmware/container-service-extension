# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client

from container_service_extension.client.legacy_ovdc import LegacyOvdc
from container_service_extension.client.ovdc_policy import PolicyBasedOvdc


class Ovdc:
    """Returns the ovdc class as determined by API version."""

    def __new__(cls, client: vcd_client):
        """Create the right ovdc class for the negotiated API version.

        For apiVersion < 35 return LegacyOvdc class
        For apiVersoin >= 35 return PolicyBasedOvdc class

        :param pyvcloud.vcd.client client: vcd client
        :return: instance of version specific client side cluster
        """
        api_version = client.get_api_version()
        if float(api_version) < float(vcd_client.ApiVersion.VERSION_35.value):
            return LegacyOvdc(client)
        elif float(api_version) >= float(vcd_client.ApiVersion.VERSION_35.value):  # noqa: E501
            return PolicyBasedOvdc(client)
