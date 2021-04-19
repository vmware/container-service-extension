# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import abc


class AbstractNativeEntity(abc.ABC):

    @classmethod
    @abc.abstractmethod
    def from_native_entity(cls, native_entity):
        pass

    @classmethod
    @abc.abstractmethod
    def from_cluster_data(cls, cluster: dict, kind: str, **kwargs):
        pass

    @classmethod
    @abc.abstractmethod
    def sample_native_entity(cls, k8_runtime=''):
        pass
