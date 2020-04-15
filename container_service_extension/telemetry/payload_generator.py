# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.constants import PayloadTable
from container_service_extension.telemetry.constants import PayloadValue
from container_service_extension.telemetry.telemetry_utils import uuid_hash


def get_payload_for_user_action(cse_operation, status, message=None):
    """Get telemetry payload for the given operation.

    :param CseOperation cse_operation: operation initiated by the user
    :param str status: success or failure status that indicates the outcome
        of cse_operation
    :param str message: custom message about the operation

    :return: json data specific to the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: PayloadTable.USER_ACTIONS,
        PayloadKey.TARGET: cse_operation.target,
        PayloadKey.ACTION: cse_operation.action,
        PayloadKey.STATUS: status,
        PayloadKey.MESSAGE: message
    }


def get_payload_for_cluster_convert(params):
    """Construct telemetry payload of cluster convert operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_CONVERT.telemetry_table,
        PayloadKey.WAS_DECRYPTION_SKIPPED: bool(params.get(PayloadKey.WAS_DECRYPTION_SKIPPED)),  # noqa: E501
        PayloadKey.WAS_GC_WAIT_SKIPPED: bool(params.get(PayloadKey.WAS_GC_WAIT_SKIPPED)),  # noqa: E501
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(PayloadKey.WAS_OVDC_SPECIFIED)),  # noqa: E501
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(PayloadKey.WAS_ORG_SPECIFIED)),  # noqa: E501
        PayloadKey.WAS_NEW_ADMIN_PASSWORD_PROVIDED: bool(params.get(PayloadKey.WAS_NEW_ADMIN_PASSWORD_PROVIDED))  # noqa: E501
    }


def get_payload_for_config_check(params):
    """Construct telemetry payload of config check operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CONFIG_CHECK.telemetry_table,
        PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(params.get(PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED)),  # noqa: E501
        PayloadKey.WAS_DECRYPTION_SKIPPED: bool(params.get(PayloadKey.WAS_DECRYPTION_SKIPPED)),  # noqa: E501
        PayloadKey.WAS_INSTALLATION_CHECKED: bool(params.get(PayloadKey.WAS_INSTALLATION_CHECKED))  # noqa: E501
    }


def get_payload_for_install_server(params):
    """Construct telemetry payload of server install operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.SERVICE_INSTALL.telemetry_table,
        PayloadKey.WAS_DECRYPTION_SKIPPED: bool(params.get(PayloadKey.WAS_DECRYPTION_SKIPPED)),  # noqa: E501
        PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(params.get(PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED)),  # noqa: E501
        PayloadKey.WERE_TEMPLATES_SKIPPED: bool(params.get(PayloadKey.WERE_TEMPLATES_SKIPPED)),  # noqa: E501
        PayloadKey.WERE_TEMPLATES_FORCE_UPDATED: bool(params.get(PayloadKey.WERE_TEMPLATES_FORCE_UPDATED)),  # noqa: E501
        PayloadKey.WAS_TEMP_VAPP_RETAINED: bool(params.get(PayloadKey.WAS_TEMP_VAPP_RETAINED)),  # noqa: E501
        PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(params.get(PayloadKey.WAS_SSH_KEY_SPECIFIED))  # noqa: E501
    }


def get_payload_for_run_server(params):
    """Construct telemetry payload of server run operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.SERVICE_RUN.telemetry_table,
        PayloadKey.WAS_DECRYPTION_SKIPPED: bool(params.get(PayloadKey.WAS_DECRYPTION_SKIPPED)),  # noqa: E501
        PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED: bool(params.get(PayloadKey.WAS_PKS_CONFIG_FILE_PROVIDED)),  # noqa: E501
        PayloadKey.WAS_INSTALLATION_CHECK_SKIPPED: bool(params.get(PayloadKey.WAS_INSTALLATION_CHECK_SKIPPED)),  # noqa: E501
    }


def get_payload_for_install_template(params):
    """Construct telemetry payload of template install operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.TEMPLATE_INSTALL.telemetry_table,
        PayloadKey.TEMPLATE_NAME: params.get(PayloadKey.TEMPLATE_NAME),
        PayloadKey.TEMPLATE_REVISION: params.get(PayloadKey.TEMPLATE_REVISION),
        PayloadKey.WAS_DECRYPTION_SKIPPED: bool(params.get(PayloadKey.WAS_DECRYPTION_SKIPPED)),  # noqa: E501
        PayloadKey.WERE_TEMPLATES_FORCE_UPDATED: bool(params.get(PayloadKey.WERE_TEMPLATES_FORCE_UPDATED)),  # noqa: E501
        PayloadKey.WAS_TEMP_VAPP_RETAINED: bool(params.get(PayloadKey.WAS_TEMP_VAPP_RETAINED)),  # noqa: E501
        PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(params.get(PayloadKey.WAS_SSH_KEY_SPECIFIED))  # noqa: E501
    }


def get_payload_for_template_list(params):
    """Construct telemetry payload of template list operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.TEMPLATE_LIST.telemetry_table,
        PayloadKey.WAS_DECRYPTION_SKIPPED: bool(params.get(PayloadKey.WAS_DECRYPTION_SKIPPED)),  # noqa: E501
        PayloadKey.DISPLAY_OPTION: params.get(PayloadKey.DISPLAY_OPTION)
    }


def get_payload_for_cluster_config(params):
    """Construct telemetry payload of cluster config.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_CONFIG.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.TEMPLATE_NAME: params.get(RequestKey.TEMPLATE_NAME),
        PayloadKey.TEMPLATE_REVISION: params.get(RequestKey.TEMPLATE_REVISION),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_create_cluster(params):
    """Construct telemetry payload of cluster creation.

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_CREATE.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
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
        PayloadKey.WAS_STORAGE_PROFILE_SPECIFIED: bool(params.get(RequestKey.STORAGE_PROFILE_NAME)),  # noqa: E501
        PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(params.get(RequestKey.SSH_KEY)),
        PayloadKey.ADDED_NFS_NODE: params.get(RequestKey.ENABLE_NFS),
        PayloadKey.WAS_ROLLBACK_ENABLED: bool(params.get(RequestKey.ROLLBACK)),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_cluster_delete(params):
    """Construct telemetry payload of cluster deletion.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_DELETE.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_cluster_info(params):
    """Construct telemetry payload of cluster info operation.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_INFO.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_list_clusters(params):
    """Construct telemetry payload of list cluster operation.

    :param params: parameters provided to the operation

    :return: json telemetry data the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_LIST.telemetry_table,
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_cluster_resize(params):
    """Construct telemetry payload of cluster resize.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_RESIZE.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.CPU: params.get(LocalTemplateKey.CPU),
        PayloadKey.MEMORY: params.get(LocalTemplateKey.MEMORY),
        PayloadKey.NUMBER_OF_WORKER_NODES: params.get(RequestKey.NUM_WORKERS),
        PayloadKey.TEMPLATE_NAME: params.get(RequestKey.TEMPLATE_NAME),
        PayloadKey.TEMPLATE_REVISION: params.get(RequestKey.TEMPLATE_REVISION),
        PayloadKey.WAS_ROLLBACK_ENABLED: bool(params.get(RequestKey.ROLLBACK)),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME)),
    }


def get_payload_for_cluster_upgrade(params):
    """Construct telemetry payload of cluster upgrade.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_UPGRADE.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.TEMPLATE_NAME: params.get(RequestKey.TEMPLATE_NAME),
        PayloadKey.TEMPLATE_REVISION: params.get(RequestKey.TEMPLATE_REVISION),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_cluster_upgrade_plan(params):
    """Construct telemetry payload of cluster upgrade plan.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.CLUSTER_UPGRADE_PLAN.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_node_create(params):
    """Construct telemetry payload of node create.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.NODE_CREATE.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.TEMPLATE_NAME: params.get(RequestKey.TEMPLATE_NAME),
        PayloadKey.TEMPLATE_REVISION: params.get(RequestKey.TEMPLATE_REVISION),
        PayloadKey.K8S_DISTRIBUTION: params.get(LocalTemplateKey.KUBERNETES),
        PayloadKey.K8S_VERSION: params.get(LocalTemplateKey.KUBERNETES_VERSION),  # noqa: E501
        PayloadKey.CNI_VERSION: params.get(LocalTemplateKey.CNI_VERSION),
        PayloadKey.CNI: params.get(LocalTemplateKey.CNI),
        PayloadKey.OS: params.get(LocalTemplateKey.OS),
        PayloadKey.NUMBER_OF_NODES: params.get(RequestKey.NUM_WORKERS),
        PayloadKey.NODE_TYPE: PayloadValue.WORKER,
        PayloadKey.CPU: params.get(LocalTemplateKey.CPU),
        PayloadKey.MEMORY: params.get(LocalTemplateKey.MEMORY),
        PayloadKey.WAS_STORAGE_PROFILE_SPECIFIED: bool(params.get(RequestKey.STORAGE_PROFILE_NAME)),  # noqa: E501
        PayloadKey.WAS_SSH_KEY_SPECIFIED: bool(params.get(RequestKey.SSH_KEY)),
        PayloadKey.WAS_NFS_ENABLED: bool(params.get(RequestKey.ENABLE_NFS)),
        PayloadKey.WAS_ROLLBACK_ENABLED: bool(params.get(RequestKey.ROLLBACK)),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_node_delete(params):
    """Construct telemetry payload of node delete.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.NODE_DELETE.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.NODE_NAME: params.get(RequestKey.NODE_NAME),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_node_info(params):
    """Construct telemetry payload of node info.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.NODE_INFO.telemetry_table,
        PayloadKey.CLUSTER_ID: uuid_hash(params.get(PayloadKey.CLUSTER_ID)),
        PayloadKey.NODE_NAME: params.get(RequestKey.NODE_NAME),
        PayloadKey.WAS_OVDC_SPECIFIED: bool(params.get(RequestKey.OVDC_NAME)),
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_ovdc_disable(params):
    """Construct telemetry payload of ovdc disable.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.OVDC_DISABLE.telemetry_table,
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_ovdc_enable(params):
    """Construct telemetry payload of ovdc enable.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.OVDC_ENABLE.telemetry_table,
        PayloadKey.K8S_PROVIDER: params.get(RequestKey.K8S_PROVIDER),
        PayloadKey.WAS_PKS_PLAN_SPECIFIED: bool(params.get(RequestKey.PKS_PLAN_NAME)),  # noqa: E501
        PayloadKey.WAS_PKS_CLUSTER_DOMAIN_SPECIFIED: bool(params.get(RequestKey.PKS_CLUSTER_DOMAIN)),  # noqa: E501
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))
    }


def get_payload_for_ovdc_info(params):
    """Construct telemetry payload of ovdc info.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.OVDC_INFO.telemetry_table,
        PayloadKey.WAS_ORG_SPECIFIED: bool(params.get(RequestKey.ORG_NAME))  # noqa: E501
    }


def get_payload_for_ovdc_list(params):
    """Construct telemetry payload of ovdc list.

    :param params: parameters provided to the operation

    :return: json telemetry data for the operation

    :type: dict
    """
    return {
        PayloadKey.TYPE: CseOperation.OVDC_LIST.telemetry_table,
        PayloadKey.WAS_PKS_PLAN_SPECIFIED: bool(params.get(RequestKey.LIST_PKS_PLANS))  # noqa: E501
    }
