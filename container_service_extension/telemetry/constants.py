# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

# End point of Vmware Analytics staging server
# TODO() : This URL should reflect production server during release
VAC_URL = "https://vcsa.vmware.com/ph-stg/api/hyper/send/"

# Value of collector id that is required as part of HTTP request
# to post sample data to analytics server
COLLECTOR_ID = "CSE.2_6"


@unique
class CseOperation(Enum):
    """Each CSE operation has a member with following values.

    1. target - CSE object associated with the operation ex: SERVER, CLUSTER
    2. action - What action is done on the target object
    3. analytics_table - name of the table that will hold the supplemental
    data
    """

    def __init__(self, description, target, action, analytics_table):
        self.description = description
        self._target = target
        self._action = action
        self._analytics_table = analytics_table

    @property
    def target(self):
        return self._target

    @property
    def action(self):
        return self._action

    @property
    def analytics_table(self):
        return self._analytics_table

    INSTALL_SERVER = ('install server', 'SERVER', 'INSTALL', 'SERVICE_INSTALL')
    CLUSTER_LIST = ('cluster list', 'CLUSTER', 'LIST', 'CLUSTER_LIST')
    CLUSTER_CREATE = ('cluster creat', 'CLUSTER', 'CREATE', 'CLUSTER_CREATE')


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
    WAS_OVDC_SPECIFIED = 'Was oVDC specified'
    WAS_ORG_SPECIFIED = 'Was Org specified'
    WAS_DECRYPTION_SKIPPED = 'Was decryption skipped'
    WAS_PASSWORD_PROVIDED = 'Was password provided'
    WAS_PKS_CONFIG_FILE_PROVIDED = 'Was PKS config file provided'
    WERE_TEMPLATES_SKIPPED = 'Were templates skipped'
    WERE_TEMPLATES_FORCE_UPDATED = 'Were templates force updated'
    WAS_TEMP_VAPP_RETAINED = 'Was temp vApp retained'
    WAS_SSH_KEY_SPECIFIED = 'Was SSH key specified'
    CLUSTER_ID = 'Cluster Id'
    TEMPLATE_NAME = 'Template Name'
    TEMPLATE_REVISION = 'Template revision'
    K8S_DISTRIBUTION = 'K8s distribution'
    K8S_VERSION = 'K8s version'
    OS = 'Os'
    CNI = 'CNI'
    CNI_VERSION = 'CNI version'
    NUMBER_OF_MASTER_NODES = 'Number of master nodes'
    NUMBER_OF_WORKER_NODES = 'Number of worker nodes'
    CPU = 'CPU'
    MEMORY = 'Memory'
    WAS_STORAGE_PROFILE_SPECIFIED = 'Was Storage Profile specified'
    ADDED_NFS_NODE = 'Added NFS node'
    WAS_ROLLBACK_DISABLED = 'Was Rollback disabled'


@unique
class PayloadTable(str, Enum):
    USER_ACTIONS = 'USER_ACTIONS'
