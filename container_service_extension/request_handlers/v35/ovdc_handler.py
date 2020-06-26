# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
import container_service_extension.logger as logger
import container_service_extension.models as cse_models
import container_service_extension.operation_context as ctx
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import CLUSTER_RUNTIME_PLACEMENT_POLICIES # noqa: E501
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.telemetry_handler import record_user_action_details  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
import container_service_extension.utils as utils


# TODO address telemetry problem: Cannot decide before calling the async
# method if the operation is enable or disable. Enabling an OVDC and DISABLING
# another OVDC can also be done in the same request.
# TODO add remove_policy_from_vms flag.
def ovdc_update(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc enable, disable operations.

    Add or remove the respective cluster placement policies to enable or
    disable cluster deployment of a certain kind in the OVDC.

    Required data: k8s_provider

    :return: Dictionary with org VDC update task href.
    """
    # ovdc_id = data[RequestKey.OVDC_ID]
    # request_data = data[RequestKey.V35_SPEC]
    # required = [
    #     RequestKey.K8S_RUNTIME,
    # ]
    # validated_data = request_data
    # req_utils.validate_payload(request_data, required)

    # if set(validated_data[RequestKey.K8S_RUNTIME]) - set(CLUSTER_RUNTIME_PLACEMENT_POLICIES): # noqa: E501
    #     msg = "Cluster providers should have one of the follwoing values:" \
    #           f" {', '.join(CLUSTER_RUNTIME_PLACEMENT_POLICIES)}."
    #     logger.SERVER_LOGGER.error(msg)
    #     raise ValueError(msg)

    ovdc_request = cse_models.Ovdc(**{**data[RequestKey.V35_SPEC], "id": data[RequestKey.OVDC_ID]})

    msg = "Updating OVDC placement policies"
    task = vcd_task.Task(operation_context.sysadmin_client)
    org = vcd_utils.get_org(operation_context.client)
    user_href = org.get_user(operation_context.user.name).get('href')
    vdc = vcd_utils.get_vdc(operation_context.sysadmin_client, vdc_id=ovdc_request.id,
                            is_admin_operation=True)
    logger.SERVER_LOGGER.debug(msg)
    task_resource = task.update(
        status=vcd_client.TaskStatus.RUNNING.value,
        namespace='vcloud.cse',
        operation=msg,
        operation_name='OVDC Update',
        details='',
        progress=None,
        owner_href=vdc.href,
        owner_name=vdc.name,
        owner_type=vcd_client.EntityType.VDC.value,
        user_href=user_href,
        user_name=operation_context.user.name,
        org_href=operation_context.user.org_href,
        task_href=None,
        error_message=None,
        stack_trace=None)
    task_href = task_resource.get('href')
    operation_context.is_async = True
    _update_ovdc_using_placement_policy_async(operation_context=operation_context,  # noqa:E501
                                              task=task,
                                              task_href=task_href,
                                              user_href=user_href,
                                              policy_list=validated_data[RequestKey.K8S_RUNTIME],  # noqa:E501
                                              ovdc_id=ovdc_id,
                                              vdc=vdc,
                                              remove_compute_policy_from_vms=ovdc_request.remove_compute_policy_from_vms or False)  # noqa:E501
    return {'task_href': task_href}


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
def ovdc_info(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc info operation.

    Required data: ovdc_id

    :return: Dictionary with org VDC k8s provider metadata.
    """
    ovdc_id = data[RequestKey.OVDC_ID]

    # Record telemetry data
    cse_params = copy.deepcopy(data)
    record_user_action_details(cse_operation=CseOperation.OVDC_INFO,
                               cse_params=cse_params)
    config = utils.get_server_runtime_config()
    log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
    return ovdc_utils.get_ovdc_k8s_provider_details(
        operation_context.sysadmin_client,
        ovdc_id=ovdc_id,
        log_wire=log_wire)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
def ovdc_list(data, operation_context: ctx.OperationContext):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s provider metadata.
    """
    cse_params = copy.deepcopy(data)
    record_user_action_details(cse_operation=CseOperation.OVDC_LIST,
                               cse_params=cse_params)

    # Ideally this should be extracted out to ovdc_utils, but the mandatory
    # usage of sysadmin client along with a potentially non-sysadmin client
    # means that the function signature require both tenant client and
    # sysadmin client, which is very awkward
    if operation_context.client.is_sysadmin():
        org_resource_list = operation_context.client.get_org_list()
    else:
        org_resource_list = list(operation_context.client.get_org())
    ovdcs = []
    for org_resource in org_resource_list:
        org = vcd_org.Org(operation_context.client, resource=org_resource)
        for vdc_sparse in org.list_vdcs():
            ovdc_name = vdc_sparse['name']
            org_name = org.get_name()
            ovdc_details = ovdc_utils.get_ovdc_k8s_provider_details(
                operation_context.sysadmin_client,
                org_name=org_name,
                ovdc_name=ovdc_name
            )
            ovdcs.append(ovdc_details)

    return ovdcs


@utils.run_async
def _update_ovdc_using_placement_policy_async(operation_context: ctx.OperationContext,  # noqa: E501
                                              task: vcd_task.Task,
                                              task_href,
                                              user_href,
                                              policy_list,
                                              ovdc_id,
                                              vdc,
                                              remove_compute_policy_from_vms=False):  # noqa: E501
    """Enable ovdc using placement policies.

    :param operation_context ctx.OperationContext: operation context object
    :param task vcd_task.Task: Task resource to track progress
    :param task_href str: href of the task
    :param user_href str:
    :param policy_list str[]: The new list of policies associated with the ovdc
    :param ovdc_id str:
    :param vdc: VDC object
    """
    operation_name = "Update OVDC with placement policies"
    try:
        config = utils.get_server_runtime_config()
        log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
        cpm = compute_policy_manager.ComputePolicyManager(
            operation_context.sysadmin_client, log_wire=log_wire)
        existing_policies = []
        for policy in cpm.list_vdc_placement_policies_on_vdc(ovdc_id):
            existing_policies.append(policy['name'])

        policies_to_add = set(policy_list) - set(existing_policies)
        policies_to_delete = set(existing_policies) - set(policy_list)

        for cp_name in policies_to_add:
            msg = f"Adding k8s provider {cp_name} to OVDC {vdc.name}"
            logger.SERVER_LOGGER.debug(msg)
            task.update(status=vcd_client.TaskStatus.RUNNING.value,
                        namespace='vcloud.cse',
                        operation=msg,
                        operation_name=operation_name,
                        details='',
                        progress=None,
                        owner_href=vdc.href,
                        owner_name=vdc.name,
                        owner_type=vcd_client.EntityType.VDC.value,
                        user_href=user_href,
                        user_name=operation_context.user.name,
                        task_href=task_href,
                        org_href=operation_context.user.org_href)
            policy = cpm.get_vdc_compute_policy(cp_name, is_placement_policy=True)  # noqa: E501
            cpm.add_compute_policy_to_vdc(vdc_id=ovdc_id,
                                          compute_policy_href=policy['href'])

        for cp_name in policies_to_delete:
            msg = f"Removing k8s provider {cp_name} from OVDC {ovdc_id}"
            logger.SERVER_LOGGER.debug(msg)
            task.update(status=vcd_client.TaskStatus.RUNNING.value,
                        namespace='vcloud.cse',
                        operation=msg,
                        operation_name=operation_name,
                        details='',
                        progress=None,
                        owner_href=vdc.href,
                        owner_name=vdc.name,
                        owner_type=vcd_client.EntityType.VDC.value,
                        user_href=user_href,
                        user_name=operation_context.user.name,
                        task_href=task_href,
                        org_href=operation_context.user.org_href)
            policy = cpm.get_vdc_compute_policy(cp_name, is_placement_policy=True)  # noqa: E501
            cpm.remove_compute_policy_from_vdc(task=task,
                                               task_href=task_href,
                                               user_href=user_href,
                                               org_href=operation_context.user.org_href,  # noqa: E501
                                               ovdc_id=ovdc_id,
                                               vdc=vdc,
                                               compute_policy_href=policy['href'],  # noqa: E501
                                               remove_compute_policy_from_vms=remove_compute_policy_from_vms, # noqa: E501
                                               is_placement_policy=True)
        msg = f"Successfully updated OVDC: {vdc.name}"
        logger.SERVER_LOGGER.debug(msg)
        task.update(status=vcd_client.TaskStatus.SUCCESS.value,
                    namespace='vcloud.cse',
                    operation="Operation success",
                    operation_name=operation_name,
                    details=msg,
                    progress=None,
                    owner_href=vdc.href,
                    owner_name=vdc.name,
                    owner_type=vcd_client.EntityType.VDC.value,
                    user_href=user_href,
                    user_name=operation_context.user.name,
                    task_href=task_href,
                    org_href=operation_context.user.org_href)
    except Exception as err:
        logger.SERVER_LOGGER.error(err)
        task.update(status=vcd_client.TaskStatus.ERROR.value,
                    namespace='vcloud.cse',
                    operation='',
                    operation_name=operation_name,
                    details=f'Failed with error: {err}',
                    progress=None,
                    owner_href=vdc.href,
                    owner_name=vdc.name,
                    owner_type=vcd_client.EntityType.VDC.value,
                    user_href=user_href,
                    user_name=operation_context.user.name,
                    task_href=task_href,
                    org_href=operation_context.user.org_href,
                    error_message=f"{err}")
    finally:
        if operation_context.sysadmin_client:
            operation_context.end()
