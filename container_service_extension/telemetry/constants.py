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

    INSTALL_SERVER = ('install server', 'SERVER', 'INSTALL', 'CSE_SERVICE_INSTALL')  # noqa: E501
    CLUSTER_LIST = ('cluster list', 'CLUSTER', 'LIST', 'CSE_CLUSTER_LIST')
    CLUSTER_CREATE = ('cluster create', 'CLUSTER', 'CREATE', 'CSE_CLUSTER_CREATE')  # noqa: E501


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
    WERE_TEMPLATES_SKIPPED = 'were_templates_skipped'
    WERE_TEMPLATES_FORCE_UPDATED = 'were_templates_force_updated'
    WAS_TEMP_VAPP_RETAINED = 'was_temp_vapp_retained'
    WAS_SSH_KEY_SPECIFIED = 'was_ssh_key_specified'
    CLUSTER_ID = 'cluster_id'
    TEMPLATE_NAME = 'template_name'
    TEMPLATE_REVISION = 'template_revision'
    K8S_DISTRIBUTION = 'k8s_distribution'
    K8S_VERSION = 'k8s_version'
    OS = 'os'
    CNI = 'cni'
    CNI_VERSION = 'cni_version'
    NUMBER_OF_MASTER_NODES = 'number_of_master_nodes'
    NUMBER_OF_WORKER_NODES = 'number_of_worker_nodes'
    CPU = 'cpu'
    MEMORY = 'memory'
    WAS_STORAGE_PROFILE_SPECIFIED = 'was_storage_profile_specified'
    ADDED_NFS_NODE = 'added_nfs_node'
    WAS_ROLLBACK_DISABLED = 'was_rollback_disabled'


@unique
class PayloadTable(str, Enum):
    USER_ACTIONS = 'CSE_USER_ACTIONS'
