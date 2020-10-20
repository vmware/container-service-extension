# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
# import copy
from dataclasses import asdict
from typing import List

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
import container_service_extension.def_.models as def_models
import container_service_extension.logger as logger
import container_service_extension.operation_context as ctx
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.shared_constants import ClusterEntityKind
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP  # noqa: E501
from container_service_extension.shared_constants import RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP  # noqa: E501
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
import container_service_extension.telemetry.telemetry_handler as telemetry_handler # noqa: E501
import container_service_extension.utils as utils


def update_ovdc(operation_context: ctx.OperationContext,
                ovdc_id: str, ovdc_spec: def_models.Ovdc) -> dict: # noqa: 501
    """Update ovdc with the updated k8s runtimes list.

    :param ctx.OperationContext operation_context: context for the request
    :param def_models.Ovdc ovdc_spec: Ovdc object having the updated
        k8s runtime list
    :return: dictionary containing the task href for the update operation
    :rtype: dict
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` flag in config is set to false,
    # Prevent enable/disable of OVDC for TKG+ k8s runtime by throwing an
    # exception
    msg = "Updating OVDC placement policies"
    task = vcd_task.Task(operation_context.sysadmin_client)
    org = vcd_utils.get_org(operation_context.client)
    user_href = org.get_user(operation_context.user.name).get('href')
    vdc = vcd_utils.get_vdc(operation_context.sysadmin_client, vdc_id=ovdc_id, # noqa: E501
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
    # NOTE: Telemetry is currently handled in the async function as it is not
    # possible to know the operation (enable/disable) without comparing it to
    # current k8s runtimes.
    if ClusterEntityKind.TKG_PLUS.value in ovdc_spec.k8s_runtime and \
            not utils.is_tkg_plus_enabled():
        msg = "TKG+ is not enabled on CSE server. Please enable TKG+ in the " \
              "server and try again."
        logger.SERVER_LOGGER.debug(msg)
        raise Exception(msg)
    policy_list = [RUNTIME_DISPLAY_NAME_TO_INTERNAL_NAME_MAP[p] for p in ovdc_spec.k8s_runtime]  # noqa: E501
    _update_ovdc_using_placement_policy_async(operation_context=operation_context, # noqa:E501
                                              task=task,
                                              task_href=task_href,
                                              user_href=user_href,
                                              policy_list=policy_list, # noqa:E501
                                              ovdc_id=ovdc_id,
                                              vdc=vdc,
                                              remove_cp_from_vms_on_disable=ovdc_spec.remove_cp_from_vms_on_disable) # noqa:E501
    return {'task_href': task_href}


def get_ovdc(operation_context: ctx.OperationContext, ovdc_id: str) -> dict:
    """Get ovdc info for a particular ovdc.

    :param ctx.OperationContext operation_context: context for the request
    :param str ovdc_id: ID of the ovdc
    :return: dictionary containing the ovdc information
    :rtype: dict
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` flag in config is set to false,
    # Prevent showing information about TKG+ by skipping TKG+ from the result.
    cse_params = {
        RequestKey.OVDC_ID: ovdc_id
    }
    telemetry_handler.record_user_action_details(cse_operation=CseOperation.OVDC_INFO, # noqa: E501
                                                 cse_params=cse_params)
    config = utils.get_server_runtime_config()
    log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
    result = asdict(get_ovdc_k8s_runtime_details(operation_context.sysadmin_client, # noqa: E501
                                                 ovdc_id=ovdc_id,
                                                 log_wire=log_wire))
    # TODO: Find a better way to avoid sending remove_cp_from_vms_on_disable
    # flag
    if ClusterEntityKind.TKG_PLUS.value in result['k8s_runtime'] \
            and not utils.is_tkg_plus_enabled():
        result['k8s_runtime'].remove(ClusterEntityKind.TKG_PLUS.value)
    del result['remove_cp_from_vms_on_disable']
    return result


def list_ovdc(operation_context: ctx.OperationContext) -> List[dict]:
    """List all ovdc and their k8s runtimes.

    :param ctx.OperationContext operation_context: context for the request
    :return: list of dictionary containing details about the ovdc
    :rtype: List[dict]
    """
    # NOTE: For CSE 3.0, if `enable_tkg_plus` flag in config is set to false,
    # Prevent showing information about TKG+ by skipping TKG+ from the result.
    # Record telemetry
    telemetry_handler.record_user_action_details(cse_operation=CseOperation.OVDC_LIST, # noqa: E501
                                                 cse_params={})

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
            if ClusterEntityKind.TKG_PLUS.value in ovdc_details['k8s_runtime'] \
                    and not utils.is_tkg_plus_enabled():  # noqa: E501
                ovdc_details['k8s_runtime'].remove(ClusterEntityKind.TKG_PLUS.value)  # noqa: E501
            # TODO: Find a better way to remove remove_cp_from_vms_on_disable
            del ovdc_details['remove_cp_from_vms_on_disable']
            ovdcs.append(ovdc_details)
    return ovdcs


def get_ovdc_k8s_runtime_details(sysadmin_client: vcd_client.Client,
                                 org_name=None, ovdc_name=None,
                                 ovdc_id=None, log_wire=False) -> def_models.Ovdc: # noqa: E501
    """Get k8s runtime details for an ovdc.

    :param sysadmin_client vcd_client.Client: vcd sysadmin client
    :param str org_name:
    :param str ovdc_name:
    :param str ovdc_id:
    :param bool log_wire:
    :return: Ovdc object with k8s runtimes
    :rtype: def_models.Ovdc
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
    for cse_policy in \
            compute_policy_manager.list_cse_placement_policies_on_vdc(cpm, ovdc_id):  # noqa: E501
        policies.append(RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP[cse_policy['display_name']])  # noqa: E501
    return def_models.Ovdc(ovdc_name=ovdc_name, ovdc_id=ovdc_id, k8s_runtime=policies) # noqa: E501


@utils.run_async
def _update_ovdc_using_placement_policy_async(operation_context: ctx.OperationContext,  # noqa: E501
                                              task: vcd_task.Task,
                                              task_href,
                                              user_href,
                                              policy_list,
                                              ovdc_id,
                                              vdc,
                                              remove_cp_from_vms_on_disable=False):  # noqa: E501
    """Enable ovdc using placement policies.

    :param ctx.OperationContext operation_context: operation context object
    :param vcd_task.Task task: Task resource to track progress
    :param str task_href: href of the task
    :param str user_href:
    :param List[str] policy_list: The new list of policies associated with
        the ovdc
    :param str ovdc_id:
    :param pyvcloud.vcd.vdc.VDC vdc: VDC object
    :param bool remove_cp_from_vms_on_disable: Set to true if placement
        policies need to be removed from the vms before removing from the VDC.
    """
    operation_name = "Update OVDC with placement policies"
    k8s_runtimes_added = ''
    k8s_runtimes_deleted = ''
    try:
        config = utils.get_server_runtime_config()
        log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
        cpm = compute_policy_manager.ComputePolicyManager(
            operation_context.sysadmin_client, log_wire=log_wire)
        existing_policies = []
        for cse_policy in \
                compute_policy_manager.list_cse_placement_policies_on_vdc(cpm, ovdc_id):  # noqa: E501
            existing_policies.append(cse_policy['display_name'])

        logger.SERVER_LOGGER.debug(policy_list)
        logger.SERVER_LOGGER.debug(existing_policies)
        policies_to_add = set(policy_list) - set(existing_policies)
        policies_to_delete = set(existing_policies) - set(policy_list)

        # Telemetry for 'vcd cse ovdc enable' command
        # TODO: Update telemetry request to handle 'k8s_runtime' array
        k8s_runtimes_added = ','.join(policies_to_add)
        if k8s_runtimes_added:
            cse_params = {
                RequestKey.K8S_PROVIDER: k8s_runtimes_added,
                RequestKey.OVDC_ID: ovdc_id,
            }
            telemetry_handler.record_user_action_details(cse_operation=CseOperation.OVDC_ENABLE, # noqa: E501
                                                         cse_params=cse_params)

        # Telemetry for 'vcd cse ovdc enable' command
        # TODO: Update telemetry request to handle 'k8s_runtime' array
        k8s_runtimes_deleted = '.'.join(policies_to_delete)
        if k8s_runtimes_deleted:
            cse_params = {
                RequestKey.K8S_PROVIDER: k8s_runtimes_deleted,
                RequestKey.OVDC_ID: ovdc_id,
                RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS: remove_cp_from_vms_on_disable # noqa: E501
            }
            telemetry_handler.record_user_action_details(cse_operation=CseOperation.OVDC_DISABLE, # noqa: E501
                                                         cse_params=cse_params)

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
            policy = compute_policy_manager.get_cse_vdc_compute_policy(
                cpm,
                cp_name,
                is_placement_policy=True)
            cpm.add_compute_policy_to_vdc(vdc_id=ovdc_id,
                                          compute_policy_href=policy['href'])

        for cp_name in policies_to_delete:
            msg = f"Removing k8s provider {RUNTIME_INTERNAL_NAME_TO_DISPLAY_NAME_MAP[cp_name]} from OVDC {ovdc_id}"  # noqa: E501
            logger.SERVER_LOGGER.debug(msg)
            task_resource = \
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
            policy = compute_policy_manager.get_cse_vdc_compute_policy(cpm,
                                                                       cp_name,
                                                                       is_placement_policy=True)  # noqa: E501
            cpm.remove_compute_policy_from_vdc_sync(vdc=vdc,
                                                    compute_policy_href=policy['href'],  # noqa: E501
                                                    force=remove_cp_from_vms_on_disable, # noqa: E501
                                                    is_placement_policy=True,
                                                    task_resource=task_resource) # noqa: E501
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
        # Record telemetry
        if k8s_runtimes_added:
            telemetry_handler.record_user_action(CseOperation.OVDC_ENABLE,
                                                 status=OperationStatus.SUCCESS) # noqa: E501
        if k8s_runtimes_deleted:
            telemetry_handler.record_user_action(CseOperation.OVDC_DISABLE,
                                                 status=OperationStatus.SUCCESS) # noqa: E501
    except Exception as err:
        # Record telemetry
        if k8s_runtimes_added:
            telemetry_handler.record_user_action(CseOperation.OVDC_ENABLE,
                                                 status=OperationStatus.FAILED)
        if k8s_runtimes_deleted:
            telemetry_handler.record_user_action(CseOperation.OVDC_DISABLE,
                                                 status=OperationStatus.FAILED)
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
