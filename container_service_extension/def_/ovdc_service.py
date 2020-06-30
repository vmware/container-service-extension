# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
# import copy
from dataclasses import asdict
from dataclasses import dataclass
from typing import List

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
import container_service_extension.logger as logger
import container_service_extension.operation_context as ctx
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils


@dataclass()
class Ovdc:
    k8s_runtime: List[str]
    ovdc_name: str = None
    ovdc_id: str = None
    remove_compute_policy_from_vms: bool = False


# TODO address telemetry problem: Cannot decide before calling the async
# method if the operation is enable or disable. Enabling an OVDC and DISABLING
# another OVDC can also be done in the same request.
# TODO add remove_policy_from_vms flag.
def update_ovdc(operation_context: ctx.OperationContext, ovdc: Ovdc) -> dict:
    """Update ovdc with the updated k8s runtimes list.

    :param ctx.OperationContext operation_context: context for the request
    :param Ovdc ovdc: Ovdc object having the updated k8s runtime list
    :return: dictionary containing the task href for the update operation
    :rtype: dict
    """
    msg = "Updating OVDC placement policies"
    task = vcd_task.Task(operation_context.sysadmin_client)
    org = vcd_utils.get_org(operation_context.client)
    user_href = org.get_user(operation_context.user.name).get('href')
    vdc = vcd_utils.get_vdc(operation_context.sysadmin_client, vdc_id=ovdc.ovdc_id, # noqa: E501
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
                                              policy_list=ovdc.k8s_runtime,  # noqa:E501
                                              ovdc_id=ovdc.ovdc_id,
                                              vdc=vdc,
                                              remove_compute_policy_from_vms=ovdc.remove_compute_policy_from_vms)  # noqa:E501
    return {'task_href': task_href}


def get_ovdc(operation_context: ctx.OperationContext, ovdc_id: str) -> dict:
    """Get ovdc info for a particular ovdc.

    :param ctx.OperationContext operation_context: context for the request
    :param str ovdc_id: ID of the ovdc
    :return: dictionary containing the ovdc information
    :rtype: dict
    """
    # cse_params = copy.deepcopy(data)
    # record_user_action_details(cse_operation=CseOperation.OVDC_INFO,
    #                            cse_params=cse_params)
    # TODO find out the details to be recorded for telemetry
    config = utils.get_server_runtime_config()
    log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
    result = asdict(get_ovdc_k8s_runtime_details(operation_context.sysadmin_client, # noqa: E501
                                                 ovdc_id=ovdc_id,
                                                 log_wire=log_wire))
    # TODO: Find a better way to avoid sending remove_compute_policy_from_vms
    # flag
    del result[RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS]
    return result


def list_ovdc(operation_context: ctx.OperationContext) -> List[dict]:
    """List all ovdc and their k8s runtimes.

    :param ctx.OperationContext operation_context: context for the request
    :return: list of dictionary containing details about the ovdc
    :rtype: List[dict]
    """
    # cse_params = copy.deepcopy(data)
    # record_user_action_details(cse_operation=CseOperation.OVDC_LIST,
    #                            cse_params=cse_params)
    # TODO find out the details to be recorded for telemetry
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
            ovdc_details = asdict(
                get_ovdc_k8s_runtime_details(operation_context.sysadmin_client,
                                             org_name=org_name,
                                             ovdc_name=ovdc_name))
            # TODO: Find a better way to avoid sending
            # remove_compute_policy_from_vms flag
            del ovdc_details[RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS]
            ovdcs.append(ovdc_details)
    return ovdcs


def get_ovdc_k8s_runtime_details(sysadmin_client: vcd_client.Client,
                                 org_name=None, ovdc_name=None,
                                 ovdc_id=None, log_wire=False) -> Ovdc:
    """Get k8s runtime details for an ovdc.

    :param sysadmin_client vcd_client.Client: vcd sysadmin client
    :param str org_name:
    :param str ovdc_name:
    :param str ovdc_id:
    :param bool log_wire:
    :return: Ovdc object with k8s runtimes
    :rtype: Ovdc
    """
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
    cpm = compute_policy_manager.ComputePolicyManager(sysadmin_client,
                                                      log_wire=log_wire)
    ovdc = vcd_utils.get_vdc(client=sysadmin_client,
                             vdc_name=ovdc_name,
                             org_name=org_name,
                             vdc_id=ovdc_id,
                             is_admin_operation=True)
    ovdc_id = vcd_utils.extract_id(ovdc.get_resource().get('id'))
    ovdc_name = ovdc.get_resource().get('name')
    policies = []
    for policy in cpm.list_vdc_placement_policies_on_vdc(ovdc_id):
        policies.append(policy['name'])
    return Ovdc(ovdc_name=ovdc_name, ovdc_id=ovdc_id, k8s_runtime=policies)


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
