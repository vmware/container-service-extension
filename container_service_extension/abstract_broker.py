# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc


class AbstractBroker(abc.ABC):
    @abc.abstractmethod
    def get_tenant_client_session(self):
        """Return <Session> XML object of a logged in vCD user.

        :return: the session of the tenant user.

        :rtype: lxml.objectify.ObjectifiedElement containing <Session> XML
            data.
        """
        pass
