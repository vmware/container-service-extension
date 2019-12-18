# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.constants import PayloadTable


def get_payload_for_user_action(cse_operation, status, message=None):
    """Get payload for the given CSE operation.

    :param CseOperation cse_operation: which CSE operation initiated by the
    user
    :param str status: success or failure status that indicates the outcome
    of cse_operation
    :param str message: custom message about the CSE operation

    :return: json data specific to cse operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: PayloadTable.USER_ACTIONS,
        PayloadKey.TARGET: cse_operation.target,
        PayloadKey.ACTION: cse_operation.action,
        PayloadKey.STATUS: status,
        PayloadKey.MESSAGE: message
    }


def get_payload_for_list_clusters(cse_operation, params):
    """Construct payload of list cluster operation.

    :param CseOperation cse_operation: CSE operation that is running
    :param params: parameters that the CSE operation uses

    :return: json analytics data for the CSE operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: cse_operation.analytics_table,
        PayloadKey.WAS_OVDC_SPECIFIED: True if params.get(RequestKey.OVDC_NAME) else False,  # noqa: E501
        PayloadKey.WAS_ORG_SPECIFIED: True if params.get(RequestKey.ORG_NAME) else False    # noqa: E501
    }


def get_payload_for_create_cluster(cse_operation, params):
    """Construct payload of cluster creation.

    :param CseOperation cse_operation: CSE operation that is running
    :param params: parameters that the CSE operation uses

    :return: json analytics data for the CSE operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: cse_operation.analytics_table,
        PayloadKey.CLUSTER_ID: params.get(PayloadKey.CLUSTER_ID),
        PayloadKey.TEMPLATE_NAME: params.get(RequestKey.TEMPLATE_NAME),
        PayloadKey.TEMPLATE_REVISION: params.get(RequestKey.TEMPLATE_REVISION),
        PayloadKey.K8S_DISTRIBUTION: params.get(LocalTemplateKey.KUBERNETES),
        PayloadKey.K8S_VERSION: params.get(LocalTemplateKey.KUBERNETES_VERSION),  # noqa: E501
        PayloadKey.CNI_VERSION: params.get(LocalTemplateKey.CNI_VERSION),
        PayloadKey.CNI: params.get(LocalTemplateKey.CNI),
        PayloadKey.OS: params.get(LocalTemplateKey.OS),
        PayloadKey.NUMBER_OF_MASTER_NODES: 1,
        PayloadKey.NUMBER_OF_WORKER_NODES: params.get(RequestKey.NUM_WORKERS),
        PayloadKey.CPU: params.get(LocalTemplateKey.CPU),
        PayloadKey.MEMORY: params.get(LocalTemplateKey.MEMORY),
        PayloadKey.WAS_STORAGE_PROFILE_SPECIFIED: True if params.get(RequestKey.STORAGE_PROFILE_NAME) else False,  # noqa: E501
        PayloadKey.WAS_SSH_KEY_SPECIFIED: True if params.get(RequestKey.SSH_KEY) else False,  # noqa: E501
        PayloadKey.ADDED_NFS_NODE: params.get(RequestKey.ENABLE_NFS),
        PayloadKey.WAS_ROLLBACK_DISABLED: not params.get(RequestKey.ROLLBACK),
        PayloadKey.WAS_OVDC_SPECIFIED: True if params.get(RequestKey.OVDC_NAME) else False,  # noqa: E501
        PayloadKey.WAS_ORG_SPECIFIED: True if params.get(RequestKey.ORG_NAME) else False  # noqa: E501
    }


def get_payload_for_install_server(cse_operation, params):
    """Construct payload of server install operation.

    :param CseOperation cse_operation: CSE operation that is running
    :param params: parameters that the CSE operation uses

    :return: json analytics data for the CSE operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: cse_operation.analytics_table,
        PayloadKey.WAS_DECRYPTION_SKIPPED: True if params.get(PayloadKey.WAS_DECRYPTION_SKIPPED) else False,  # noqa: E501
        PayloadKey.WAS_PASSWORD_PROVIDED: True if params.get(PayloadKey.WAS_PASSWORD_PROVIDED) else False,  # noqa: E501
        PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: True if params.get(PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED) else False,  # noqa: E501
        PayloadKey.WERE_TEMPLATES_SKIPPED: True if params.get(PayloadKey.WERE_TEMPLATES_SKIPPED) else False,  # noqa: E501
        PayloadKey.WERE_TEMPLATES_FORCE_UPDATED: True if params.get(PayloadKey.WERE_TEMPLATES_FORCE_UPDATED) else False,  # noqa: E501
        PayloadKey.WAS_TEMP_VAPP_RETAINED: True if params.get(PayloadKey.WAS_TEMP_VAPP_RETAINED) else False,  # noqa: E501
        PayloadKey.WAS_SSH_KEY_SPECIFIED: True if params.get(PayloadKey.WAS_SSH_KEY_SPECIFIED) else False  # noqa: E501
    }
