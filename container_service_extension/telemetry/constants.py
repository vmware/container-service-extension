# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

# End point of Vmware telemetry staging server
# TODO() : This URL should reflect production server during release
VAC_URL = "https://vcsa.vmware.com/ph-stg/api/hyper/send/"

# Value of collector id that is required as part of HTTP request
# to post sample data to telemetry server
COLLECTOR_ID = "CSE.2_6"


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

    CONFIG_CHECK = ('config check', 'CONFIG', 'CHECK', 'CSE_CONFIG_CHECK')
    TEMPLATE_INSTALL = ('template install', 'TEMPLATE', 'INSTALL', 'CSE_TEMPLATE_INSTALL')  # noqa: E501
    TEMPLATE_LIST = ('template list', 'TEMPLATE', 'LIST', 'CSE_TEMPLATE_LIST')  # noqa: E501
    CLUSTER_CONVERT = ('cluster convert', 'CLUSTER', 'CONVERT', 'CSE_CLUSTER_CONVERT')  # noqa: E501
    SERVICE_INSTALL = ('install server', 'SERVER', 'INSTALL', 'CSE_SERVICE_INSTALL')  # noqa: E501
    SERVICE_RUN = ('run server', 'SERVER', 'RUN', 'CSE_SERVICE_RUN')
    CLUSTER_LIST = ('cluster list', 'CLUSTER', 'LIST', 'CSE_CLUSTER_LIST')
    CLUSTER_CREATE = ('cluster create', 'CLUSTER', 'CREATE', 'CSE_CLUSTER_CREATE')  # noqa: E501
    CLUSTER_INFO = ('cluster info', 'CLUSTER', 'INFO', 'CSE_CLUSTER_INFO')
    CLUSTER_RESIZE = ('cluster resize', 'CLUSTER', 'RESIZE', 'CSE_CLUSTER_RESIZE')  # noqa: E501
    CLUSTER_DELETE = ('cluster delete', 'CLUSTER', 'DELETE', 'CSE_CLUSTER_DELETE')  # noqa: E501
    CLUSTER_CONFIG = ('cluster config', 'CLUSTER', 'CONFIG', 'CSE_CLUSTER_CONFIG')  # noqa: E501
    CLUSTER_UPGRADE = ('cluster upgrade', 'CLUSTER', 'UPGRADE', 'CSE_CLUSTER_UPGRADE')  # noqa: E501
    CLUSTER_UPGRADE_PLAN = ('cluster upgrade plan', 'CLUSTER', 'UPGRADE_PLAN', 'CSE_CLUSTER_UPGRADE_PLAN')  # noqa: E501
    NODE_INFO = ('node info', 'NODE', 'INFO', 'CSE_NODE_INFO')
    NODE_CREATE = ('node create', 'NODE', 'CREATE', 'CSE_NODE_CREATE')
    NODE_DELETE = ('node delete', 'NODE', 'DELETE', 'CSE_NODE_DELETE')
    OVDC_ENABLE = ('ovdc enable', 'OVDC', 'ENABLE', 'CSE_OVDC_ENABLE')
    OVDC_DISABLE = ('ovdc disable', 'OVDC', 'DISABLE', 'CSE_OVDC_DISABLE')
    OVDC_LIST = ('ovdc list', 'OVDC', 'LIST', 'CSE_OVDC_LIST')
    OVDC_INFO = ('ovdc_info', 'OVDC', 'INFO', 'CSE_OVDC_INFO')

    # Following operations do not require telemetry details. Hence the payload
    # generator functions are empty.
    OVDC_COMPUTE_POLICY_LIST = ('ovdc compute policy', 'COMPUTE_POLICY', 'LIST', '')  # noqa: E501
    OVDC_COMPUTE_POLICY_ADD = ('ovdc compute policy', 'COMPUTE_POLICY', 'ADD', '')  # noqa: E501
    OVDC_COMPUTE_POLICY_REMOVE = ('ovdc compute policy', 'COMPUTE_POLICY', 'REMOVE', '')  # noqa: E501
    SYSTEM_INFO = ('system info', 'SYSTEM', 'INFO', '')
    SYSTEM_ENABLE = ('system enable', 'SYSTEM', 'ENABLE', '')
    SYSTEM_DISABLE = ('system disable', 'SYSTEM', 'DISABLE', '')
    SYSTEM_STOP = ('system stop', 'SYSTEM', 'STOP', '')
    SYSTEM_UNKNOWN = ('system unknown', 'SYSTEM', 'UNKNOWN', '')


@unique
class OperationStatus(str, Enum):
    SUCCESS = 'SUCCESS',
    FAILED = 'FAILURE'


@unique
class PayloadKey(str, Enum):
    TYPE = '@type',
    TARGET = 'target',
    ACTION = 'action',
    STATUS = 'status'
    MESSAGE = 'message'
    WAS_OVDC_SPECIFIED = 'was_ovdc_specified'
    WAS_ORG_SPECIFIED = 'was_org_specified'
    WAS_DECRYPTION_SKIPPED = 'was_decryption_skipped'
    WAS_PASSWORD_PROVIDED = 'was_password_provided'
    WAS_PKS_CONFIG_FILE_PROVIDED = 'was_pks_config_file_provided'
    WAS_INSTALLATION_CHECKED = 'was_installation_checked'
    WERE_TEMPLATES_SKIPPED = 'were_templates_skipped'
    WERE_TEMPLATES_FORCE_UPDATED = 'were_templates_force_updated'
    WAS_TEMP_VAPP_RETAINED = 'was_temp_vapp_retained'
    WAS_SSH_KEY_SPECIFIED = 'was_ssh_key_specified'
    CLUSTER_ID = 'cluster_id'
    NODE_NAME = 'node_name'
    TEMPLATE_NAME = 'template_name'
    TEMPLATE_REVISION = 'template_revision'
    K8S_DISTRIBUTION = 'k8s_distribution'
    K8S_VERSION = 'k8s_version',
    K8S_PROVIDER = 'k8s_provider'
    OS = 'os'
    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    NUMBER_OF_NODES = 'number_of_nodes'
    NUMBER_OF_MASTER_NODES = 'number_of_master_nodes'
    NUMBER_OF_WORKER_NODES = 'number_of_worker_nodes'
    NODE_TYPE = 'type_of_node'
    WAS_NFS_ENABLED = 'was_nfs_enabled'
    CPU = 'cpu'
    MEMORY = 'memory'
    WAS_STORAGE_PROFILE_SPECIFIED = 'was_storage_profile_specified'
    ADDED_NFS_NODE = 'added_nfs_node'
    WAS_ROLLBACK_ENABLED = 'was_rollback_enabled'
    WAS_PKS_PLAN_SPECIFIED = 'was_pks_plan_specified'
    WAS_PKS_CLUSTER_DOMAIN_SPECIFIED = 'was_pks_cluster_domain_specified'
    DISPLAY_OPTION = 'display_option'
    WAS_GC_WAIT_SKIPPED = 'was_gc_wait_skipped'
    WAS_NEW_ADMIN_PASSWORD_PROVIDED = 'was_new_admin_password_provided'
    WAS_OUTPUT_WRITTEN_TO_FILE = 'was_output_written_to_file'
    WAS_PKS_CONFIG_FILE_GENERATED = 'was_pks_config_file_generated'
    WAS_INSTALLATION_CHECK_SKIPPED = 'was_installation_check_skipped'


@unique
class PayloadValue(str, Enum):
    WORKER = 'worker'


@unique
class PayloadTable(str, Enum):
    USER_ACTIONS = 'CSE_USER_ACTIONS'
