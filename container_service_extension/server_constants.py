# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

import requests


# CSE SERVICE
# used for registering CSE to vCD as an api extension service.
CSE_SERVICE_NAME = 'cse'
CSE_SERVICE_NAMESPACE = 'cse'
# used to set up and start AMQP exchange
EXCHANGE_TYPE = 'direct'
SYSTEM_ORG_NAME = 'System'

# DEPLOY RIGHTS
# used by authorization framework to weed out unauthorized calls.
CSE_NATIVE_DEPLOY_RIGHT_NAME = 'CSE NATIVE DEPLOY RIGHT'
CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION = 'Right necessary to deploy kubernetes ' \
    'cluster via vCD apis in CSE'
CSE_NATIVE_DEPLOY_RIGHT_CATEGORY = 'cseRight'
CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY = 'cseBundleKey'
CSE_PKS_DEPLOY_RIGHT_NAME = 'PKS DEPLOY RIGHT'
CSE_PKS_DEPLOY_RIGHT_DESCRIPTION = 'Right necessary to deploy kubernetes ' \
    'cluster via vSphere apis in PKS'
CSE_PKS_DEPLOY_RIGHT_CATEGORY = 'pksRight'
CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY = 'pksBundleKey'


# KUBERNETES PROVIDERS
K8S_PROVIDER_KEY = 'k8s_provider'


@unique
class K8sProviders(str, Enum):
    """Types of Kubernetes providers.

    Having a str mixin allows us to do things like:
    'native' == K8sProviders.NATIVE
    f"Kubernetes provider is '{K8sProviders.NATIVE}'
    """

    NATIVE = 'native'
    PKS = 'ent-pks'
    NONE = 'none'


@unique
class ScriptFile(str, Enum):
    """Types of script for vApp template customizations in CSE."""

    CUST = 'cust.sh'
    INIT = 'init.sh'
    MASTER = 'master.sh'
    NFSD = 'nfsd.sh'
    NODE = 'node.sh'


# CSE requests
@unique
class CseOperation(Enum):
    def __init__(self, description, ideal_response_code=requests.codes.ok):
        self._description = description
        self._ideal_response_code = ideal_response_code

    @property
    def ideal_response_code(self):
        return int(self._ideal_response_code)

    CLUSTER_CONFIG = ('get config of cluster')
    CLUSTER_CREATE = ('create cluster', requests.codes.accepted)
    CLUSTER_DELETE = ('delete cluster', requests.codes.accepted)
    CLUSTER_INFO = ('get info of cluster')
    CLUSTER_LIST = ('list clusters')
    CLUSTER_RESIZE = ('resize cluster', requests.codes.accepted)
    NODE_CREATE = ('create node', requests.codes.accepted)
    NODE_DELETE = ('delete node', requests.codes.accepted)
    NODE_INFO = ('get info of node')
    OVDC_ENABLE_DISABLE = \
        ('enable or disable ovdc for k8s', requests.codes.accepted)
    OVDC_INFO = ('get info of ovdc')
    OVDC_LIST = ('list ovdcs')
    SYSTEM_INFO = ('get info of system')
    SYSTEM_UPDATE = ('update system status')
    TEMPLATE_LIST = ('list all templates')
