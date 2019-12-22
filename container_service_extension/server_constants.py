# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

import requests

# CSE SERVICE; used for registering CSE to vCD as an api extension service.
CSE_SERVICE_NAME = 'cse'
CSE_SERVICE_NAMESPACE = 'cse'
EXCHANGE_TYPE = 'direct'
SYSTEM_ORG_NAME = 'system'

# CSE SERVICE; used for registering CSE to vCD as an api extension service.
CSE_SERVICE_NAME = 'cse'
CSE_SERVICE_NAMESPACE = 'cse'
EXCHANGE_TYPE = 'direct'
SYSTEM_ORG_NAME = 'system'

# DEPLOY RIGHTS; used by authorization framework to weed out unauthorized calls
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

# KUBERNETES PROVIDERS; used by server operations related to k8s providers
K8S_PROVIDER_KEY = 'k8s_provider'
PKS_PLANS_KEY = 'pks_plans'
PKS_CLUSTER_DOMAIN_KEY = 'pks_cluster_domain'
PKS_COMPUTE_PROFILE_KEY = 'pks_compute_profile_name'

# PKS API endpoint version
VERSION_V1 = 'v1'


@unique
class NodeType(str, Enum):
    MASTER = 'mstr'
    WORKER = 'node'
    NFS = 'nfsd'


@unique
class K8sProvider(str, Enum):
    """Types of Kubernetes providers.

    Having a str mixin allows us to do things like:
    'native' == K8sProvider.NATIVE
    f"Kubernetes provider is '{K8sProvider.NATIVE}'
    """

    NATIVE = 'native'
    PKS = 'ent-pks'
    NONE = 'none'


@unique
class ScriptFile(str, Enum):
    """Types of script for vApp template customizations in CSE."""

    # vapp template creation scripts
    CUST = 'cust.sh'
    INIT = 'init.sh'
    NFSD = 'nfsd.sh'

    # cluster initialization scripts
    MASTER = 'mstr.sh'
    NODE = 'node.sh'

    # cluster upgrade scripts
    DOCKER_UPGRADE = 'cluster-upgrade/docker-upgrade.sh'
    MASTER_CNI_APPLY = 'cluster-upgrade/master-cni-apply.sh'
    MASTER_K8S_UPGRADE = 'cluster-upgrade/master-k8s-upgrade.sh'
    WORKER_K8S_UPGRADE = 'cluster-upgrade/worker-k8s-upgrade.sh'


@unique
class LocalTemplateKey(str, Enum):
    """Enumerate the keys that define a template."""

    CATALOG_ITEM_NAME = 'catalog_item_name'
    COMPUTE_POLICY = 'compute_policy'
    CPU = 'cpu'
    DEPRECATED = 'deprecated'
    DESCRIPTION = 'description'
    MEMORY = 'mem'
    NAME = 'name'
    REVISION = 'revision'
    OS = 'os'
    DOCKER_VERSION = 'docker_version'
    KUBERNETES = 'kubernetes'
    KUBERNETES_VERSION = 'kubernetes_version'
    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    UPGRADE_FROM = 'upgrade_from'


@unique
class RemoteTemplateKey(str, Enum):
    """Enumerate the keys that define a template."""

    COMPUTE_POLICY = 'compute_policy'
    CPU = 'cpu'
    DEPRECATED = 'deprecated'
    DESCRIPTION = 'description'
    MEMORY = 'mem'
    NAME = 'name'
    REVISION = 'revision'
    SOURCE_OVA_HREF = 'source_ova'
    SOURCE_OVA_NAME = 'source_ova_name'
    SOURCE_OVA_SHA256 = 'sha256_ova'
    OS = 'os'
    DOCKER_VERSION = 'docker_version'
    KUBERNETES = 'kubernetes'
    KUBERNETES_VERSION = 'kubernetes_version'
    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    UPGRADE_FROM = 'upgrade_from'


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
    CLUSTER_UPGRADE_PLAN = ('get supported cluster upgrade paths')
    CLUSTER_UPGRADE = ('upgrade cluster software', requests.codes.accepted)
    NODE_CREATE = ('create node', requests.codes.accepted)
    NODE_DELETE = ('delete node', requests.codes.accepted)
    NODE_INFO = ('get info of node')
    OVDC_UPDATE = ('enable or disable ovdc for k8s', requests.codes.accepted)
    OVDC_INFO = ('get info of ovdc')
    OVDC_LIST = ('list ovdcs')
    OVDC_COMPUTE_POLICY_LIST = ('list ovdc compute policies')
    OVDC_COMPUTE_POLICY_UPDATE = ('update ovdc compute policies')
    SYSTEM_INFO = ('get info of system')
    SYSTEM_UPDATE = ('update system status')
    TEMPLATE_LIST = ('list all templates')


@unique
class ClusterMetadataKey(str, Enum):
    BACKWARD_COMPATIBILE_TEMPLATE_NAME = 'cse.template'
    CLUSTER_ID = 'cse.cluster.id'
    CSE_VERSION = 'cse.version'
    MASTER_IP = 'cse.master.ip'
    TEMPLATE_NAME = 'cse.template.name'
    TEMPLATE_REVISION = 'cse.template.revision'
    OS = "cse.os"
    DOCKER_VERSION = "cse.docker.version"
    KUBERNETES = "cse.kubernetes"
    KUBERNETES_VERSION = "cse.kubernetes.version"
    CNI = "cse.cni"
    CNI_VERSION = 'cse.cni.version'
