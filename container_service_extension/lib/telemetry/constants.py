# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

# End point of Vmware telemetry staging server
# TODO() : This URL should reflect production server during release
VAC_URL = "https://vcsa.vmware.com/ph/api/hyper/send"

# Value of collector id that is required as part of HTTP request
# to post sample data to telemetry server
COLLECTOR_ID = "CSE.3_1"


@unique
class CseOperation(Enum):
    """Each CSE operation has a member with following values.

    1. target - CSE object associated with the operation ex: SERVER, CLUSTER
    2. action - What action is done on the target object
    3. telemetry_table - name of the table that will hold the supplemental
    data
    """

    def __init__(self, description, target, action, telemetry_table):
        self.description = description
        self._target = target
        self._action = action
        self._telemetry_table = telemetry_table

    @property
    def target(self):
        return self._target

    @property
    def action(self):
        return self._action

    @property
    def telemetry_table(self):
        return self._telemetry_table

    # CSE server CLI commands
    CLUSTER_CONVERT = ('cluster convert', 'CLUSTER', 'CONVERT', 'CSE_CLUSTER_CONVERT')  # noqa: E501
    CONFIG_CHECK = ('config check', 'CONFIG', 'CHECK', 'CSE_CONFIG_CHECK')
    SERVICE_INSTALL = ('install server', 'SERVER', 'INSTALL', 'CSE_SERVICE_INSTALL')  # noqa: E501
    SERVICE_UPGRADE = ('upgrade server', 'SERVER', 'UPGRADE', 'CSE_SERVICE_UPGRADE')  # noqa: E501
    SERVICE_RUN = ('run server', 'SERVER', 'RUN', 'CSE_SERVICE_RUN')
    TEMPLATE_INSTALL = ('template install', 'TEMPLATE', 'INSTALL', 'CSE_TEMPLATE_INSTALL')  # noqa: E501
    TEMPLATE_LIST = ('template list', 'TEMPLATE', 'LIST', 'CSE_TEMPLATE_LIST')  # noqa: E501

    # vcd-cli CSE client commands
    CLUSTER_CONFIG = ('cluster config', 'CLUSTER', 'CONFIG', 'CSE_CLUSTER_CONFIG')  # noqa: E501
    CLUSTER_CREATE = ('cluster create', 'CLUSTER', 'CREATE', 'CSE_CLUSTER_CREATE')  # noqa: E501
    CLUSTER_DELETE = ('cluster delete', 'CLUSTER', 'DELETE', 'CSE_CLUSTER_DELETE')  # noqa: E501
    CLUSTER_INFO = ('cluster info', 'CLUSTER', 'INFO', 'CSE_CLUSTER_INFO')
    CLUSTER_LIST = ('cluster list', 'CLUSTER', 'LIST', 'CSE_CLUSTER_LIST')
    CLUSTER_RESIZE = ('cluster resize', 'CLUSTER', 'RESIZE', 'CSE_CLUSTER_RESIZE')  # noqa: E501
    CLUSTER_UPGRADE = ('cluster upgrade', 'CLUSTER', 'UPGRADE', 'CSE_CLUSTER_UPGRADE')  # noqa: E501
    CLUSTER_UPGRADE_PLAN = ('cluster upgrade plan', 'CLUSTER', 'UPGRADE_PLAN', 'CSE_CLUSTER_UPGRADE_PLAN')  # noqa: E501
    NODE_CREATE = ('node create', 'NODE', 'CREATE', 'CSE_NODE_CREATE')
    NODE_DELETE = ('node delete', 'NODE', 'DELETE', 'CSE_NODE_DELETE')
    NODE_INFO = ('node info', 'NODE', 'INFO', 'CSE_NODE_INFO')
    OVDC_DISABLE = ('ovdc disable', 'OVDC', 'DISABLE', 'CSE_OVDC_DISABLE')
    OVDC_ENABLE = ('ovdc enable', 'OVDC', 'ENABLE', 'CSE_OVDC_ENABLE')
    OVDC_INFO = ('ovdc_info', 'OVDC', 'INFO', 'CSE_OVDC_INFO')
    OVDC_LIST = ('ovdc list', 'OVDC', 'LIST', 'CSE_OVDC_LIST')
    PKS_CLUSTER_CONFIG = ('pks-cluster config', 'PKS_CLUSTER', 'CONFIG', 'PKS_CLUSTER_CONFIG')  # noqa: E501
    PKS_CLUSTER_CREATE = ('pks-cluster create', 'PKS_CLUSTER', 'CREATE', 'PKS_CLUSTER_CREATE')  # noqa: E501
    PKS_CLUSTER_DELETE = ('pks-cluster delete', 'PKS_CLUSTER', 'DELETE', 'PKS_CLUSTER_DELETE')  # noqa: E501
    PKS_CLUSTER_INFO = ('pks-cluster info', 'PKS_CLUSTER', 'INFO', 'PKS_CLUSTER_INFO')  # noqa: E501
    PKS_CLUSTER_LIST = ('pks-cluster list', 'PKS_CLUSTER', 'LIST', 'PKS_CLUSTER_LIST')  # noqa: E501
    PKS_CLUSTER_RESIZE = ('cluster resize', 'PKS_CLUSTER', 'RESIZE', 'PKS_CLUSTER_RESIZE')  # noqa: E501

    V35_CLUSTER_LIST = ('DEF cluster list', 'CLUSTER', 'V35_LIST', 'CSE_V35_CLUSTER_LIST')  # noqa: E501
    V35_CLUSTER_INFO = ('DEF cluster info', 'CLUSTER', 'V35_INFO', 'CSE_V35_CLUSTER_INFO')  # noqa: E501
    V35_CLUSTER_CONFIG = ('DEF cluster config', 'CLUSTER', 'V35_CONFIG', 'CSE_V35_CLUSTER_CONFIG')   # noqa: E501
    V35_CLUSTER_APPLY = ('DEF cluster create', 'CLUSTER', 'V35_APPLY', 'CSE_V35_CLUSTER_APPLY')  # noqa: E501
    V35_CLUSTER_DELETE = ('DEF cluster delete', 'CLUSTER', 'V35_DELETE', 'CSE_V35_CLUSTER_DELETE')  # noqa: E501
    V35_CLUSTER_UPGRADE_PLAN = ('DEF cluster upgrade plan', 'CLUSTER', 'V35_UPGRADE_PLAN', 'CSE_V35_CLUSTER_UPGRADE_PLAN')  # noqa: E501
    V35_CLUSTER_UPGRADE = ('DEF cluster upgrade', 'CLUSTER', 'V35_UPGRADE', 'CSE_V35_CLUSTER_UPGRADE')  # noqa: E501
    V35_CLUSTER_ACL_LIST = ('cluster acl list', 'CLUSTER', 'V35_ACL_LIST', 'CSE_V35_CLUSTER_ACL_LIST')  # noqa: E501
    V35_CLUSTER_ACL_UPDATE = ('cluster acl update', 'CLUSTER', 'V35_ACL_UPDATE', 'CSE_V35_CLUSTER_ACL_UPDATE')  # noqa: E501
    V35_NODE_DELETE = ('DEF nfs node delete', 'NODE', 'V35_DELETE', 'CSE_V35_NODE_DELETE')  # noqa: E501

    V36_CLUSTER_CONFIG = ('DEF cluster config', 'CLUSTER', 'V36_CONFIG', 'CSE_V36_CLUSTER_CONFIG')   # noqa: E501
    V36_CLUSTER_INFO = ('DEF cluster info', 'CLUSTER', 'V36_INFO', 'CSE_V36_CLUSTER_INFO')  # noqa: E501
    V36_CLUSTER_LIST = ('DEF cluster list', 'CLUSTER', 'V36_LIST', 'CSE_V36_CLUSTER_LIST')  # noqa: E501
    V36_CLUSTER_APPLY = ('DEF cluster create', 'CLUSTER', 'V36_APPLY', 'CSE_V36_CLUSTER_APPLY')  # noqa: E501
    V36_CLUSTER_UPGRADE_PLAN = ('DEF cluster upgrade plan', 'CLUSTER', 'V36_UPGRADE_PLAN', 'CSE_V36_CLUSTER_UPGRADE_PLAN')  # noqa: E501
    V36_CLUSTER_UPGRADE = ('DEF cluster upgrade', 'CLUSTER', 'V36_UPGRADE', 'CSE_V36_CLUSTER_UPGRADE')  # noqa: E501
    V36_CLUSTER_UPDATE = ('DEF cluster update', 'CLUSTER', 'V36_APPLY', 'CSE_V36_CLUSTER_APPLY')  # noqa: E501
    V36_CLUSTER_DELETE = ('DEF cluster delete', 'CLUSTER', 'V36_DELETE', 'CSE_V36_CLUSTER_DELETE')  # noqa: E501
    V36_NODE_DELETE = ('DEF nfs node delete', 'NODE', 'V36_DELETE', 'CSE_V36_NODE_DELETE')  # noqa: E501
    V36_CLUSTER_ACL_LIST = ('cluster acl list', 'CLUSTER', 'V36_ACL_LIST', 'CSE_V36_CLUSTER_ACL_LIST')  # noqa: E501
    V36_CLUSTER_ACL_UPDATE = ('cluster acl update', 'CLUSTER', 'V36_ACL_UPDATE', 'CSE_V36_CLUSTER_ACL_UPDATE')  # noqa: E501

    # Following operations do not require telemetry details. Hence the VAC
    # table name field is empty
    OVDC_COMPUTE_POLICY_ADD = ('ovdc compute policy', 'COMPUTE_POLICY', 'ADD', '')  # noqa: E501
    OVDC_COMPUTE_POLICY_LIST = ('ovdc compute policy', 'COMPUTE_POLICY', 'LIST', '')  # noqa: E501
    OVDC_COMPUTE_POLICY_REMOVE = ('ovdc compute policy', 'COMPUTE_POLICY', 'REMOVE', '')  # noqa: E501
    SYSTEM_DISABLE = ('system disable', 'SYSTEM', 'DISABLE', '')
    SYSTEM_ENABLE = ('system enable', 'SYSTEM', 'ENABLE', '')
    SYSTEM_INFO = ('system info', 'SYSTEM', 'INFO', '')
    SYSTEM_STOP = ('system stop', 'SYSTEM', 'STOP', '')
    TEMPLATE_LIST_CLIENT_SIDE = ('template list (client side)', 'TEMPLATE', 'LIST (CLIENT SIDE)', '')  # noqa: E501


@unique
class OperationStatus(str, Enum):
    SUCCESS = 'SUCCESS',
    FAILED = 'FAILURE'


@unique
class PayloadKey(str, Enum):
    ACTION = 'action',
    ADDED_NFS_NODE = 'added_nfs_node'
    CLUSTER_ID = 'cluster_id'
    CLUSTER_KIND = 'cluster_kind'
    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    CPU = 'cpu'
    DISPLAY_OPTION = 'display_option'
    FILTER_KEYS = 'filter_keys'
    K8S_DISTRIBUTION = 'k8s_distribution'
    K8S_PROVIDER = 'k8s_provider'
    K8S_VERSION = 'k8s_version',
    MEMORY = 'memory'
    MESSAGE = 'message'
    NODE_NAME = 'node_name'
    NODE_TYPE = 'type_of_node'
    NUMBER_OF_MASTER_NODES = 'number_of_master_nodes'
    NUMBER_OF_NODES = 'number_of_nodes'
    NUMBER_OF_WORKER_NODES = 'number_of_worker_nodes'
    NUMBER_OF_NFS_NODES = 'number_of_nfs_nodes'
    OS = 'os'
    PKS_CLUSTER_ID = 'uuid'
    PKS_VERSION = 'pks_version'
    SOURCE_CSE_VERSION = 'source_cse_version'
    SOURCE_DESCRIPTION = 'source_description'
    SOURCE_ID = 'source_id'
    SOURCE_VCD_API_VERSION = 'source_vcd_api_version'
    STATUS = 'status'
    TARGET = 'target',
    TARGET_CSE_VERSION = 'target_cse_version'
    TARGET_VCD_API_VERSION = 'target_vcd_api_version'
    TEMPLATE_NAME = 'template_name'
    TEMPLATE_REVISION = 'template_revision'
    TYPE = '@type',
    VCD_CEIP_ID = 'vcd_ceip_id'
    WAS_DECRYPTION_SKIPPED = 'was_decryption_skipped'
    WAS_GC_WAIT_SKIPPED = 'was_gc_wait_skipped'
    WAS_INSTALLATION_CHECKED = 'was_installation_checked'
    WAS_INSTALLATION_CHECK_SKIPPED = 'was_installation_check_skipped'
    WAS_NEW_ADMIN_PASSWORD_PROVIDED = 'was_new_admin_password_provided'
    WAS_NFS_ENABLED = 'was_nfs_enabled'
    WAS_ORG_SPECIFIED = 'was_org_specified'
    WAS_OUTPUT_WRITTEN_TO_FILE = 'was_output_written_to_file'
    WAS_OVDC_SPECIFIED = 'was_ovdc_specified'
    WAS_PASSWORD_PROVIDED = 'was_password_provided'
    WAS_PKS_CLUSTER_DOMAIN_SPECIFIED = 'was_pks_cluster_domain_specified'
    WAS_PKS_CONFIG_FILE_GENERATED = 'was_pks_config_file_generated'
    WAS_PKS_CONFIG_FILE_PROVIDED = 'was_pks_config_file_provided'
    WAS_PKS_PLAN_SPECIFIED = 'was_pks_plan_specified'
    WAS_ROLLBACK_ENABLED = 'was_rollback_enabled'
    WAS_SSH_KEY_SPECIFIED = 'was_ssh_key_specified'
    WAS_STORAGE_PROFILE_SPECIFIED = 'was_storage_profile_specified'
    WAS_TEMP_VAPP_RETAINED = 'was_temp_vapp_retained'
    WERE_TEMPLATES_FORCE_UPDATED = 'were_templates_force_updated'
    WERE_TEMPLATES_SKIPPED = 'were_templates_skipped'
    QUERY = 'query_filter'
    ACCESS_SETTING = 'access_setting'
    PAGE = 'page'
    PAGE_SIZE = 'page_size'


@unique
class PayloadValue(str, Enum):
    WORKER = 'worker'


@unique
class PayloadTable(str, Enum):
    USER_ACTIONS = 'CSE_USER_ACTIONS'


@unique
class SourceMap(str, Enum):
    VCD_CLI = 'python'
    CURL = 'curl'
    EDGE = 'edg'
    CHROME = 'chrome'
    SAFARI = 'safari'
    TERRAFORM = 'terraform'
    POSTMAN = 'postman'
    UNKNOWN = 'unknown'

    @staticmethod
    def get_source_id(user_agent: str):
        if user_agent is None:
            return SourceMap.UNKNOWN.name
        for source_entry in SourceMap:
            if source_entry.value in user_agent.lower():
                return source_entry.name
        return SourceMap.UNKNOWN.name
