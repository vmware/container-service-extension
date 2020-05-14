# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from container_service_extension.cloudapi.cloudapi_client import CloudApiClient


class DefEntityService():
    """Manages lifecycle of entities.

    TODO Add API version check at the appropriate place. This class needs to
    be used if and only if vCD API version >= 35
    """

    def __init__(self, sysadmin_cloudapi_client: CloudApiClient):
        if not sysadmin_cloudapi_client.is_sys_admin:
            raise ValueError("Cloud API Client should be sysadmin.")


        self._cloudapi_client = sysadmin_cloudapi_client

