# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.exceptions as vcd_e
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
import container_service_extension.exceptions as cse_exception
import container_service_extension.logger as logger
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_context as ctx
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import ComputePolicyAction
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.telemetry_handler import record_user_action  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_details  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
import container_service_extension.utils as utils


def ovdc_update(request_context: ctx.RequestContext):
    """Request handler for ovdc enable, disable operations.

    Add or remove the respective cluster placement policies to enable or
    disable cluster deployment of a certain kind in the OVDC.

    Required data: org_name, ovdc_name, k8s_provider
    Conditional data:
        if k8s_provider is 'ent-pks': pks_plan_name, pks_cluster_domain

    :return: Dictionary with org VDC update task href.
    """
    request_data = {**request_context.body, **(request_context.url_data or {})}
    # TODO the data flow here should be better understood.
    # org_name and ovdc_name seem redundant if we already have ovdc_id
    required = [
        RequestKey.K8S_PROVIDER,
        RequestKey.OVDC_ID
    ]
    validated_data = request_data
    req_utils.validate_payload(validated_data, required)
     # TODO record telemetry data for new api handler

     # create an umbrella task
    msg = "Updating OVDCs"
    ovdc_id = validated_data[RequestKey.OVDC_ID]
    task = vcd_task.Task(request_context.sysadmin_client)
    org = vcd_utils.get_org(request_context.client)
    user_href = org.get_user(request_context.user.name).get('href')
    vdc = vcd_utils.get_vdc(request_context.sysadmin_client, vdc_id=ovdc_id,
                                is_admin_operation=True)
    task_resource = task.update(
            status=vcd_client.TaskStatus.RUNNING.value,
            namespace='vcloud.cse',
            operation=msg,
            operation_name='',
            details='',
            progress=None,
            owner_href=vdc.href,
            owner_name=vdc.name,
            owner_type=vcd_client.EntityType.VDC.value,
            user_href=user_href,
            user_name=request_context.user.name,
            org_href=request_context.user.org_href,
            task_href=None,
            error_message=None,
            stack_trace=None)
    task_href = task_resource.get('href')
    request_context.is_async = True
    _update_ovdc_using_placement_policy_async(request_context=request_context,
                                              task=task,
                                              task_href=task_href,
                                              user_href=user_href,
                                              owner_href=vdc.href,
                                              owner_name=vdc.name,
                                              policy_list=validated_data[RequestKey.K8S_PROVIDER],
                                              ovdc_id=ovdc_id,
                                              vdc=vdc,
                                              request_data=validated_data)
    # TODO record telemetry data
    return {
        'task_href': task_href
    }


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
def ovdc_info(request_context: ctx.RequestContext):
    """Request handler for ovdc info operation.

    Required data: ovdc_id

    :return: Dictionary with org VDC k8s provider metadata.
    """
    request_data = request_context.url_data
    required = [
        RequestKey.OVDC_ID
    ]
    req_utils.validate_payload(request_data, required)

    # Record telemetry data
    cse_params = copy.deepcopy(request_data)
    record_user_action_details(cse_operation=CseOperation.OVDC_INFO,
                               cse_params=cse_params)
    config = utils.get_server_runtime_config()
    log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
    return ovdc_utils.get_ovdc_k8s_provider_details(
        request_context.sysadmin_client,
        ovdc_id=request_data[RequestKey.OVDC_ID],
        log_wire=log_wire)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
def ovdc_list(request_context: ctx.RequestContext):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s provider metadata.
    """
    # TODO record telemetry data
    # cse_params = copy.deepcopy(validated_data)
    # cse_params[RequestKey.LIST_PKS_PLANS] = list_pks_plans
    # record_user_action_details(cse_operation=CseOperation.OVDC_LIST,
    #                            cse_params=cse_params)

    # if list_pks_plans and not request_context.client.is_sysadmin():
    #     raise cse_exception.UnauthorizedRequestError(
    #         'Operation denied. Enterprise PKS plans visible only '
    #         'to System Administrators.')

    # Ideally this should be extracted out to ovdc_utils, but the mandatory
    # usage of sysadmin client along with a potentially non-sysadmin client
    # means that the function signature require both tenant client and
    # sysadmin client, which is very awkward
    if request_context.client.is_sysadmin():
        org_resource_list = request_context.client.get_org_list()
    else:
        org_resource_list = list(request_context.client.get_org())
    ovdcs = []
    for org_resource in org_resource_list:
        org = vcd_org.Org(request_context.client, resource=org_resource)
        for vdc_sparse in org.list_vdcs():
            ovdc_name = vdc_sparse['name']
            org_name = org.get_name()
            ovdc_details = ovdc_utils.get_ovdc_k8s_provider_details(
                request_context.sysadmin_client,
                org_name=org_name,
                ovdc_name=ovdc_name
            )
            # k8s_provider = k8s_details[K8S_PROVIDER_KEY]
            # ovdc_dict = {
            #     'id': ovdc_id,
            #     'name': ovdc_name,
            #     'org': org_name,
            #     'k8s provider': k8s_provider # this will be an array
            # }
            ovdcs.append(ovdc_details)

    return ovdcs


def _update_ovdc_using_metadata(request_context: ctx.RequestContext,
                                request_data):
    """Legacy method of enabling metadata.

    Executed if Global PVDC compute policies are not supported.

    :param request_context ctx.RequestContext: request context object
    :param request_data dict: A validated dictionary containing request data

    :return task object for updation of OVDC metadata
    """
    k8s_provider = request_data[RequestKey.K8S_PROVIDER]
    k8s_provider_info = {K8S_PROVIDER_KEY: k8s_provider}
    if k8s_provider == K8sProvider.PKS:
        # Check if target ovdc is not already enabled for other non PKS k8 providers # noqa: E501
        ovdc_metadata = ovdc_utils.get_ovdc_k8s_provider_metadata(
            request_context.sysadmin_client,
            ovdc_id=request_data[RequestKey.OVDC_ID])
        ovdc_k8_provider = ovdc_metadata.get(K8S_PROVIDER_KEY)
        if ovdc_k8_provider != K8sProvider.NONE and \
                ovdc_k8_provider != k8s_provider:
            raise cse_exception.CseServerError("OVDC already enabled for different K8 provider")  # noqa: E501

        k8s_provider_info = ovdc_utils.construct_k8s_metadata_from_pks_cache(  # noqa: E501
            request_context.sysadmin_client,
            ovdc_id=request_data[RequestKey.OVDC_ID],
            org_name=request_data[RequestKey.ORG_NAME],
            pks_plans=request_data[RequestKey.PKS_PLAN_NAME],
            pks_cluster_domain=request_data[RequestKey.PKS_CLUSTER_DOMAIN],
            k8s_provider=k8s_provider)
        ovdc_utils.create_pks_compute_profile(request_data,
                                              request_context,
                                              k8s_provider_info)

    return ovdc_utils.update_ovdc_k8s_provider_metadata(
        request_context.sysadmin_client, 
        request_data[RequestKey.OVDC_ID],
        k8s_provider_data=k8s_provider_info,
        k8s_provider=k8s_provider)


@utils.run_async
def _update_ovdc_using_placement_policy_async(request_context: ctx.RequestContext,  # noqa: E501
                                              task: vcd_task.Task,
                                              task_href,
                                              user_href,
                                              owner_href,
                                              owner_name,
                                              policy_list,
                                              ovdc_id,
                                              vdc,
                                              request_data,
                                              remove_compute_policy_from_vms=False):  # noqa: E501
    """Enable ovdc using placement policies.

    :param request_context ctx.RequestContext: request context object
    :param request_data dict:  A validated dictionary containing request data
    raises:
    """
    operation_name = "Update OVDC with placement policies"
    try:
        config = utils.get_server_runtime_config()
        log_wire = utils.str_to_bool(config.get('service', {}).get('log_wire'))
        cpm = compute_policy_manager.ComputePolicyManager(
            request_context.sysadmin_client, log_wire=log_wire)
        existing_policies = []
        for policy in cpm.list_vdc_placement_policies_on_vdc(ovdc_id):
            existing_policies.append(policy['name'])
        
        policies_to_add = set(policy_list) - set(existing_policies)
        policies_to_delete = set(existing_policies) - set(policy_list)
        
        # TODO check if the policy name is valid.
        for cp_name in policies_to_add:
            msg = f"Adding k8s provider {cp_name} to OVDC {ovdc_id}"
            logger.SERVER_LOGGER.debug(msg)
            task.update(status=vcd_client.TaskStatus.RUNNING.value,
                        namespace='vcloud.cse',
                        operation=msg,
                        operation_name=operation_name,
                        details='',
                        progress=None,
                        owner_href=owner_href,
                        owner_name=owner_name,
                        owner_type=vcd_client.EntityType.VDC.value,
                        user_href=user_href,
                        user_name=request_context.user.name,
                        task_href=task_href,
                        org_href=request_context.user.org_href)
            policy = cpm.get_vdc_compute_policy(cp_name, is_placement_policy=True)
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
                        owner_href=owner_href,
                        owner_name=owner_name,
                        owner_type=vcd_client.EntityType.VDC.value,
                        user_href=user_href,
                        user_name=request_context.user.name,
                        task_href=task_href,
                        org_href=request_context.user.org_href)
            policy = cpm.get_vdc_compute_policy(cp_name, is_placement_policy=True)
            cpm.remove_compute_policy_from_vdc_with_task(task=task,
                                                         task_href=task_href,
                                                         user_href=user_href,
                                                         org_href=request_context.user.org_href,
                                                         ovdc_id=ovdc_id,
                                                         vdc=vdc,
                                                         compute_policy_href=policy['href'],
                                                         remove_compute_policy_from_vms=remove_compute_policy_from_vms)

        task.update(status=vcd_client.TaskStatus.SUCCESS.value,
                        namespace='vcloud.cse',
                        operation="Operation success",
                        operation_name=operation_name,
                        details='Successfully updated OVDC',
                        progress=None,
                        owner_href=owner_href,
                        owner_name=owner_name,
                        owner_type=vcd_client.EntityType.VDC.value,
                        user_href=user_href,
                        user_name=request_context.user.name,
                        task_href=task_href,
                        org_href=request_context.user.org_href)
    except Exception as err:
        logger.SERVER_LOGGER.error(err)
        task.update(
                status=vcd_client.TaskStatus.ERROR.value,
                namespace='vcloud.cse',
                operation='',
                operation_name=operation_name,
                details='',
                progress=None,
                owner_href=owner_href,
                owner_name=owner_name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=request_context.user.name,
                task_href=task_href,
                org_href=request_context.user.org_href,
                error_message=f"{err}")
    finally:
        if request_context.sysadmin_client:
            request_context.end()

