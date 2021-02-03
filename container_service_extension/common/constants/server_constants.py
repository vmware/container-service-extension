# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Constants used only in the CSE server."""

from dataclasses import dataclass
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
SUPPORTED_VCD_API_VERSIONS = ['33.0', '34.0', '35.0', '36.0']

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


# Encryption constants
PBKDF2_ITERATIONS = 100000
SALT_SIZE = 32
PBKDF2_OUTPUT_SIZE = 32

# Names of Message Consumer Thread and Watchdog Thread
MESSAGE_CONSUMER_THREAD = 'MessageConsumer'
WATCHDOG_THREAD = 'ConsumerWatchdog'


# Config file error messages
CONFIG_DECRYPTION_ERROR_MSG = \
    "Config file decryption failed: invalid decryption password"
VCENTER_LOGIN_ERROR_MSG = "vCenter login failed (check config file for "\
    "vCenter username/password)."

# Request Id format for logging
REQUEST_ID_FORMAT = 'Request Id: %(requestId)s | '


@unique
class OperationType(str, Enum):
    CLUSTER = 'cluster'
    NODE = 'node'
    OVDC = 'ovdc'
    SYSTEM = 'system'
    TEMPLATE = 'template'


@unique
class ThreadLocalData(str, Enum):
    USER_AGENT = 'User-Agent'
    REQUEST_ID = 'request_id'


@unique
class DefEntityOperation(str, Enum):
    CREATE = 'CREATE'
    DELETE = 'DELETE'
    UPDATE = 'UPDATE'
    UPGRADE = 'UPGRADE'
    UNKNOWN = 'UNKNOWN'


@unique
class DefEntityOperationStatus(str, Enum):
    IN_PROGRESS = 'IN_PROGRESS'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    UNKNOWN = 'UNKNOWN'


@unique
class FlattenedClusterSpecKey(Enum):
    WORKERS_COUNT = 'workers.count'
    NFS_COUNT = 'nfs.count'
    TEMPLATE_NAME = 'k8_distribution.template_name'
    TEMPLATE_REVISION = 'k8_distribution.template_revision'


VALID_UPDATE_FIELDS = [FlattenedClusterSpecKey.WORKERS_COUNT.value, FlattenedClusterSpecKey.NFS_COUNT.value,  # noqa: E501
                       FlattenedClusterSpecKey.TEMPLATE_NAME.value, FlattenedClusterSpecKey.TEMPLATE_REVISION.value]  # noqa: E501


CLUSTER_ENTITY = 'cluster_entity'


# User ID parsing
USER_PATH = '/user/'
ADMIN_USER_PATH = '/admin/user/'

# vApp Access control type
CHANGE_ACCESS = 'Change'


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
    def __init__(self, description, api_path_format, ideal_response_code=requests.codes.ok):  # noqa: E501
        self._description = description
        self._ideal_response_code = ideal_response_code
        self._api_path_format = api_path_format

    @property
    def ideal_response_code(self):
        return int(self._ideal_response_code)

    @property
    def api_path_format(self):
        return self._api_path_format

    CLUSTER_CONFIG = ('get config of cluster', '/cse/cluster/%s/config')
    CLUSTER_CREATE = ('create cluster', '/cse/clusters', requests.codes.accepted)  # noqa: E501
    CLUSTER_DELETE = ('delete cluster', '/cse/cluster/%s', requests.codes.accepted)  # noqa: E501
    CLUSTER_INFO = ('get info of cluster', '/cse/cluster/%s')
    CLUSTER_LIST = ('list clusters', '/cse/clusters')
    CLUSTER_RESIZE = ('resize cluster', '/cse/cluster/%s', requests.codes.accepted)  # noqa: E501
    CLUSTER_UPGRADE_PLAN = ('get supported cluster upgrade paths', '/cse/cluster/%s/upgrade-plan')  # noqa: E501
    CLUSTER_UPGRADE = ('upgrade cluster software', '/cse/cluster/%s/action/upgrade', requests.codes.accepted)  # noqa: E501
    NODE_CREATE = ('create node', '/cse/nodes', requests.codes.accepted)
    NODE_DELETE = ('delete node', '/cse/nodes/%s', requests.codes.accepted)
    NODE_INFO = ('get info of node', '/cse/nodes/%s')

    V35_CLUSTER_CONFIG = ('get config of DEF cluster', '/cse/3.0/cluster/%s/config')  # noqa: E501
    V35_CLUSTER_CREATE = ('create DEF cluster', '/cse/3.0/clusters', requests.codes.accepted)  # noqa: E501
    V35_CLUSTER_DELETE = ('delete DEF cluster', '/cse/3.0/cluster/%s', requests.codes.accepted)  # noqa: E501
    V35_CLUSTER_INFO = ('get info of DEF cluster', '/cse/3.0/cluster/%s')
    V35_CLUSTER_LIST = ('list DEF clusters', '/cse/3.0/clusters')
    V35_CLUSTER_RESIZE = ('resize DEF cluster', '/cse/3.0/cluster/%s', requests.codes.accepted)  # noqa: E501
    V35_CLUSTER_UPGRADE_PLAN = ('get supported DEF cluster upgrade paths', '/cse/3.0/cluster/%s/upgrade-plan')  # noqa: E501
    V35_CLUSTER_UPGRADE = ('upgrade DEF cluster software', '/cse/3.0/cluster/%s/action/upgrade', requests.codes.accepted)  # noqa: E501
    V35_CLUSTER_ACL_LIST = ('list cluster acl', '/cse/3.0/cluster/%s/acl')
    V35_CLUSTER_ACL_UPDATE = ('update cluster acl', '/cse/3.0/cluster/%s/acl', requests.codes.no_content)  # noqa: E501
    V35_NODE_CREATE = ('create DEF node', 'NOT IMPLEMENTED', requests.codes.accepted)  # noqa: E501
    V35_NODE_DELETE = ('delete DEF node', '/cse/3.0/cluster/%s/nfs/%s', requests.codes.accepted)  # noqa: E501
    V35_NODE_INFO = ('get info of DEF node', 'NOT IMPLEMENTED')

    V36_CLUSTER_UPDATE = ('update DEF cluster', '/cse/3.0/cluster/%s', requests.codes.accepted)  # noqa: E501

    OVDC_UPDATE = ('enable or disable ovdc for k8s', '/cse/ovdc/%s', requests.codes.accepted)  # noqa: E501
    OVDC_INFO = ('get info of ovdc', '/cse/ovdc/%s')
    OVDC_LIST = ('list ovdcs', '/cse/ovdcs')
    OVDC_COMPUTE_POLICY_LIST = ('list ovdc compute policies', '/cse/ovdc/%s/compute-policies')  # noqa: E501
    OVDC_COMPUTE_POLICY_UPDATE = ('update ovdc compute policies', '/cse/ovdc/%s/compute-policies')  # noqa: E501
    SYSTEM_INFO = ('get info of system', '/cse/system')
    SYSTEM_UPDATE = ('update system status', '/cse/system')
    TEMPLATE_LIST = ('list all templates', '/cse/templates')

    V35_OVDC_LIST = ('list ovdcs for v35', '/cse/3.0/ovdcs')
    V35_OVDC_INFO = ('get info of ovdc for v35', '/cse/3.0/ovdc/%s')
    V35_OVDC_UPDATE = ('enable or disable ovdc for a cluster kind for v35', '/cse/3.0/ovdc/%s', requests.codes.accepted)  # noqa: E501
    V35_TEMPLATE_LIST = ('list all v35 templates', '/cse/templates')

    PKS_CLUSTER_CONFIG = ('get config of PKS cluster', '/pks/clusters/%s/config')  # noqa: E501
    PKS_CLUSTER_CREATE = ('create PKS cluster', '/pks/clusters', requests.codes.accepted)  # noqa: E501
    PKS_CLUSTER_DELETE = ('delete PKS cluster', '/pks/cluster/%s', requests.codes.accepted)  # noqa: E501
    PKS_CLUSTER_INFO = ('get info of PKS cluster', '/pks/cluster/%s')
    PKS_CLUSTER_LIST = ('list PKS clusters', '/pks/clusters')
    PKS_CLUSTER_RESIZE = ('resize PKS cluster', '/pks/cluster/%s', requests.codes.accepted)  # noqa: E501
    PKS_OVDC_LIST = ('list all ovdcs', '/pks/ovdcs')
    PKS_OVDC_INFO = ('get info of the ovdc', '/pks/ovdc/%s')
    PKS_OVDC_UPDATE = ('enable or disable ovdc for pks', '/pks/ovdc/%s', requests.codes.accepted)  # noqa: E501


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


@unique
class AclGrantType(str, Enum):
    MembershipACLGrant = "MembershipAccessControlGrant"


@unique
class AclAccessLevelId(str, Enum):
    AccessLevelReadWrite = "urn:vcloud:accessLevel:ReadWrite"


@unique
class AclMemberId(str, Enum):
    SystemOrgId = "urn:vcloud:org:a93c9db9-7471-3192-8d09-a8f7eeda85f9"


@unique
class VappAccessKey(str, Enum):
    """Keys for VAPP access control."""

    IS_SHARED_TO_EVERYONE = 'isSharedToEveryone'
    ACCESS_SETTINGS = 'accessSettings'
    ACCESS_SETTING = 'accessSetting'


# CSE Service Role Name
CSE_SERVICE_ROLE_NAME = 'CSE Service Role'
CSE_SERVICE_ROLE_DESC = "CSE Service Role has all the rights necessary for \
        CSE to operate"
CSE_SERVICE_ROLE_RIGHTS = [
    "Access Control List: View",
    "Access Control List: Manage",
    "AMQP Settings: View",
    "Catalog: Add vApp from My Cloud",
    "Catalog: Create / Delete a Catalog",
    "Catalog: Edit Properties",
    "Catalog: Publish",
    "Catalog: Sharing",
    "Catalog: View ACL",
    "Catalog: View Private and Shared Catalogs",
    "Catalog: View Published Catalogs",
    "Content Library System Settings: View",
    "Custom entity: Create custom entity definitions",
    "Custom entity: Delete custom entity definitions",
    "Custom entity: Edit custom entity definitions",
    "Custom entity: View custom entity definitions",
    "Extension Services: View",
    "Extensions: View",
    "External Service: Manage",
    "External Service: View",
    "General: View Error Details",
    "Group / User: View",
    "Host: View",
    "Kerberos Settings: View",
    "Organization Network: View",
    "Organization vDC Compute Policy: Admin View",
    "Organization vDC Compute Policy: Manage",
    "Organization vDC Compute Policy: View",
    "Organization vDC Kubernetes Policy: Edit",
    "Organization vDC Network: Edit Properties",
    "Organization vDC Network: View Properties",
    "Organization vDC: Extended Edit",
    "Organization vDC: Extended View",
    "Organization vDC: View",
    "Organization: Perform Administrator Queries",
    "Organization: View",
    "Provider Network: View",
    "Provider vDC Compute Policy: Manage",
    "Provider vDC Compute Policy: View",
    "Provider vDC: View",
    "Right: Manage",
    "Right: View",
    "Rights Bundle: View",
    "Role: Create, Edit, Delete, or Copy",
    "Service Configuration: Manage",
    "Service Configuration: View",
    "System Settings: View",
    "Task: Resume, Abort, or Fail",
    "Task: Update",
    "Task: View Tasks",
    "Token: Manage",
    "UI Plugins: Define, Upload, Modify, Delete, Associate or Disassociate",
    "UI Plugins: View",
    "vApp Template / Media: Copy",
    "vApp Template / Media: Create / Upload",
    "vApp Template / Media: Edit",
    "vApp Template / Media: View",
    "vApp Template: Checkout",
    "vApp Template: Import",
    "vApp: Allow All Extra Config",
    "vApp: Allow Ethernet Coalescing Extra Config",
    "vApp: Allow Latency Extra Config",
    "vApp: Allow Matching Extra Config",
    "vApp: Allow NUMA Node Affinity Extra Config",
    "vApp: Create / Reconfigure",
    "vApp: Delete",
    "vApp: Edit Properties",
    "vApp: Edit VM CPU and Memory reservation settings in all VDC types",
    "vApp: Edit VM CPU",
    "vApp: Edit VM Compute Policy",
    "vApp: Edit VM Hard Disk",
    "vApp: Edit VM Memory",
    "vApp: Edit VM Network",
    "vApp: Edit VM Properties",
    "vApp: Manage VM Password Settings",
    "vApp: Power Operations",
    "vApp: Shadow VM View",
    "vApp: Upload",
    "vApp: Use Console",
    "vApp: VM Boot Options",
    "vApp: VM Check Compliance",
    "vApp: VM Migrate, Force Undeploy, Relocate, Consolidate",
    "vApp: View VM and VM's Disks Encryption Status",
    "vApp: View VM metrics",
    "vCenter: View",
    "vSphere Server: View",
    "vmware:tkgcluster: Administrator Full access",
    "vmware:tkgcluster: Administrator View",
    "vmware:tkgcluster: Full Access",
    "vmware:tkgcluster: Modify",
    "vmware:tkgcluster: View"
]


@dataclass
class DefEntityPhase:
    """Supports two ways of creation.

    1. DefEntityPhase(DefEntityOperation.CREATE, DefEntityOperationStatus.SUCCEEDED) # noqa: E501
    2. DefEntityPhase.from_phase('CREATE:SUCCEEDED')
    """

    operation: DefEntityOperation
    status: DefEntityOperationStatus

    def __str__(self):
        return f'{self.operation}:{self.status}'

    @classmethod
    def from_phase(cls, phase: str):
        """Return instance of DefEntityPhase.

        :param str phase: defined entity phase value. ex: "CREATE:SUCCEEDED"
        :return: DefEntityPhase
        :rtype: <class DefEntityPhase>
        """
        operation, status = phase.split(':')
        return cls(DefEntityOperation[operation], DefEntityOperationStatus[status])  # noqa: E501

    def is_operation_status_success(self) -> bool:
        try:
            return self.status == DefEntityOperationStatus.SUCCEEDED
        except Exception:
            return False

    def is_entity_busy(self) -> bool:
        return self.status == DefEntityOperationStatus.IN_PROGRESS
