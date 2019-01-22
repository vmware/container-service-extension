# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc


class AbstractBroker(abc.ABC):
    @abc.abstractmethod
    def get_sys_admin_client(self):
        pass

    @abc.abstractmethod
    def get_tenant_client_session(self):
        pass
