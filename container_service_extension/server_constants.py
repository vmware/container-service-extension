# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

import requests
import semantic_version

# CSE SERVICE; default version strings for CSE api extension
UNKNOWN_CSE_VERSION = semantic_version.Version("0.0.0")
UNKNOWN_VCD_API_VERSION = "0.0"

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

# vCD API versions supported by CSE
SUPPORTED_VCD_API_VERSIONS = ['33.0', '34.0', '35.0']

# CSE global pvdc compute policy name
CSE_GLOBAL_PVDC_COMPUTE_POLICY_NAME = 'global'
CSE_GLOBAL_PVDC_COMPUTE_POLICY_DESCRIPTION = \
    'global PVDC compute policy for cse'

# CSE cluster Kubeconfig path
CSE_CLUSTER_KUBECONFIG_PATH = '/root/.kube/config'

# MQTT constants
ADMIN_EXT_SERVICE_PATH = 'admin/extension/service'
API_FILTER_PATH = 'apifilter'
API_FILTERS_PATH = 'apifilters'
EXTENSIONS_API_PATH = 'extensions/api'
MQTT_API_FILTER_PATTERN = '/api/mqttEndpoint/cse'  # Needs to start with '/'
MQTT_EXTENSION_VERSION = '1.0.0'
MQTT_EXTENSION_VENDOR = 'VMWare'
MQTT_EXTENSION_PRIORITY = 100
MQTT_MIN_API_VERSION = 35.0
MQTT_TOKEN_NAME = "mqttCseToken"
TOKEN_PATH = 'tokens'

# Name of single Message Consumer Thread, which passes jobs to a
# Thread Pool Executor
MESSAGE_CONSUMER_THREAD = 'MessageConsumer'

# Encryption constants
PBKDF2_ITERATIONS = 100000
SALT_SIZE = 32
PBKDF2_OUTPUT_SIZE = 32

# Names of Message Consumer Thread and Watchdog Thread
MESSAGE_CONSUMER_THREAD = 'MessageConsumer'
WATCHDOG_THREAD = 'ConsumerWatchdog'

# Request Id format for logging
REQUEST_ID_FORMAT = 'Request Id: %(requestId)s | '


@unique
class NodeType(str, Enum):
    CONTROL_PLANE = 'mstr'
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
class KwargKey(str, Enum):
    """Types of keyword arguments for cluster brokers."""

    DATA = 'data'
    TELEMETRY = 'telemetry'


@unique
class ScriptFile(str, Enum):
    """Types of script for vApp template customizations in CSE."""

    # vapp template creation scripts
    CUST = 'cust.sh'
    INIT = 'init.sh'
    NFSD = 'nfsd.sh'

    # cluster initialization scripts
    CONTROL_PLANE = 'mstr.sh'
    NODE = 'node.sh'

    # cluster upgrade scripts
    DOCKER_UPGRADE = 'cluster-upgrade/docker-upgrade.sh'
    CONTROL_PLANE_CNI_APPLY = 'cluster-upgrade/master-cni-apply.sh'
    CONTROL_PLANE_K8S_UPGRADE = 'cluster-upgrade/master-k8s-upgrade.sh'
    WORKER_K8S_UPGRADE = 'cluster-upgrade/worker-k8s-upgrade.sh'


@unique
class LocalTemplateKey(str, Enum):
    """Enumerate the keys that define a template."""

    CATALOG_ITEM_NAME = 'catalog_item_name'
    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    COMPUTE_POLICY = 'compute_policy'
    CPU = 'cpu'
    DEPRECATED = 'deprecated'
    DESCRIPTION = 'description'
    DOCKER_VERSION = 'docker_version'
    KIND = 'kind'
    KUBERNETES = 'kubernetes'
    KUBERNETES_VERSION = 'kubernetes_version'
    MEMORY = 'mem'
    NAME = 'name'
    OS = 'os'
    REVISION = 'revision'
    UPGRADE_FROM = 'upgrade_from'


@unique
class RemoteTemplateKey(str, Enum):
    """Enumerate the keys that define a template."""

    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    COMPUTE_POLICY = 'compute_policy'
    CPU = 'cpu'
    DEPRECATED = 'deprecated'
    DESCRIPTION = 'description'
    DOCKER_VERSION = 'docker_version'
    KIND = 'kind'
    KUBERNETES = 'kubernetes'
    KUBERNETES_VERSION = 'kubernetes_version'
    MEMORY = 'mem'
    NAME = 'name'
    OS = 'os'
    REVISION = 'revision'
    SOURCE_OVA_HREF = 'source_ova'
    SOURCE_OVA_NAME = 'source_ova_name'
    SOURCE_OVA_SHA256 = 'sha256_ova'
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

    V35_CLUSTER_CONFIG = ('get config of DEF cluster')
    V35_CLUSTER_CREATE = ('create DEF cluster', requests.codes.accepted)
    V35_CLUSTER_DELETE = ('delete DEF cluster', requests.codes.accepted)
    V35_CLUSTER_INFO = ('get info of DEF cluster')
    V35_CLUSTER_LIST = ('list DEF clusters')
    V35_CLUSTER_RESIZE = ('resize DEF cluster', requests.codes.accepted)
    V35_CLUSTER_UPGRADE_PLAN = ('get supported DEF cluster upgrade paths')
    V35_CLUSTER_UPGRADE = ('upgrade DEF cluster software', requests.codes.accepted)  # noqa: E501
    V35_NODE_CREATE = ('create DEF node', requests.codes.accepted)
    V35_NODE_DELETE = ('delete DEF node', requests.codes.accepted)
    V35_NODE_INFO = ('get info of DEF node')

    OVDC_UPDATE = ('enable or disable ovdc for k8s', requests.codes.accepted)
    OVDC_INFO = ('get info of ovdc')
    OVDC_LIST = ('list ovdcs')
    OVDC_COMPUTE_POLICY_LIST = ('list ovdc compute policies')
    OVDC_COMPUTE_POLICY_UPDATE = ('update ovdc compute policies')
    SYSTEM_INFO = ('get info of system')
    SYSTEM_UPDATE = ('update system status')
    TEMPLATE_LIST = ('list all templates')

    V35_OVDC_LIST = ('list ovdcs for v35')
    V35_OVDC_INFO = ('get info of ovdc for v35')
    V35_OVDC_UPDATE = ('enable or disable ovdc for a cluster kind for v35', requests.codes.accepted)  # noqa: E501
    V35_TEMPLATE_LIST = ('list all v35 templates')

    PKS_CLUSTER_CONFIG = ('get config of PKS cluster')
    PKS_CLUSTER_CREATE = ('create PKS cluster', requests.codes.accepted)
    PKS_CLUSTER_DELETE = ('delete PKS cluster', requests.codes.accepted)
    PKS_CLUSTER_INFO = ('get info of PKS cluster')
    PKS_CLUSTER_LIST = ('list PKS clusters')
    PKS_CLUSTER_RESIZE = ('resize PKS cluster', requests.codes.accepted)


@unique
class ClusterMetadataKey(str, Enum):
    BACKWARD_COMPATIBILE_TEMPLATE_NAME = 'cse.template'
    CLUSTER_ID = 'cse.cluster.id'
    CSE_VERSION = 'cse.version'
    CONTROL_PLANE_IP = 'cse.master.ip'
    TEMPLATE_NAME = 'cse.template.name'
    TEMPLATE_REVISION = 'cse.template.revision'
    OS = "cse.os"
    DOCKER_VERSION = "cse.docker.version"
    KUBERNETES = "cse.kubernetes"
    KUBERNETES_VERSION = "cse.kubernetes.version"
    CNI = "cse.cni"
    CNI_VERSION = 'cse.cni.version'


@unique
class TemplateBuildKey(str, Enum):
    TEMPLATE_NAME = 'template_name'
    TEMPLATE_REVISION = 'template_revision'
    SOURCE_OVA_NAME = 'source_ova_name'
    SOURCE_OVA_HREF = 'source_ova_href'
    SOURCE_OVA_SHA256 = 'source_ova_sha256'
    ORG_NAME = 'org_name'
    VDC_NAME = 'vdc_name'
    CATALOG_NAME = 'catalog_name'
    CATALOG_ITEM_NAME = 'catalog_item_name'
    CATALOG_ITEM_DESCRIPTION = 'catalog_item_description'
    TEMP_VAPP_NAME = 'temp_vapp_name'
    TEMP_VM_NAME = 'temp_vm_name'
    CPU = 'cpu'
    MEMORY = 'memory'
    NETWORK_NAME = 'network_name'
    IP_ALLOCATION_MODE = 'ip_allocation_mode'
    STORAGE_PROFILE = 'storage_profile'
    CSE_PLACEMENT_POLICY = 'cse_placement_policy'


@unique
class MQTTExtKey(str, Enum):
    API_FILTER_ID = 'api_filter_id'
    EXT_NAME = 'name'
    EXT_VERSION = 'version'
    EXT_VENDOR = 'vendor'
    EXT_PRIORITY = 'priority'
    EXT_ENABLED = 'enabled'
    EXT_AUTH_ENABLED = 'authorizationEnabled'
    EXT_DESCRIPTION = 'description'
    EXT_URN_ID = 'ext_urn_id'
    EXT_UUID = 'ext_uuid'
    EXT_LISTEN_TOPIC = 'listen_topic'
    EXT_RESPOND_TOPIC = 'respond_topic'


@unique
class MQTTExtTokenKey(str, Enum):
    TOKEN_NAME = 'name'
    TOKEN_TYPE = 'type'
    TOKEN_EXT_ID = 'extensionId'
    TOKEN = 'token'
    TOKEN_ID = 'token_id'


@unique
class ExtensionType(str, Enum):
    MQTT = 'MQTT'
    AMQP = 'AMQP'
    NONE = 'None'
