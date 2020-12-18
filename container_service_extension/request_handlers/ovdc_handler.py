# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.exceptions as vcd_e
import pyvcloud.vcd.task as vcd_task

import container_service_extension.compute_policy_manager as compute_policy_manager # noqa: E501
import container_service_extension.exceptions as e
import container_service_extension.logger as logger
import container_service_extension.operation_context as ctx
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import CseOperation as CseServerOperationInfo  # noqa: E501
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import ThreadLocalData
from container_service_extension.shared_constants import ComputePolicyAction
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import PaginationKey
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler import record_user_action  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_details  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
import container_service_extension.thread_local_data as thread_local_data
import container_service_extension.utils as utils

SYSTEM_DEFAULT_COMPUTE_POLICY_NAME = "System Default"


def ovdc_update(request_data, op_ctx: ctx.OperationContext):
    """Request handler for ovdc enable, disable operations.

    Required data: org_name, ovdc_name, k8s_provider
    Conditional data:
        if k8s_provider is 'ent-pks': pks_plan_name, pks_cluster_domain

    :return: Dictionary with org VDC update task href.
    """
    # TODO the data flow here should be better understood.
    # org_name and ovdc_name seem redundant if we already have ovdc_id
    required = [
        RequestKey.ORG_NAME,
        RequestKey.OVDC_NAME,
        RequestKey.K8S_PROVIDER,
        RequestKey.OVDC_ID
    ]
    validated_data = request_data
    req_utils.validate_payload(validated_data, required)

    k8s_provider = validated_data[RequestKey.K8S_PROVIDER]
    k8s_provider_info = {K8S_PROVIDER_KEY: k8s_provider}

    # Record the telemetry data
    cse_params = copy.deepcopy(validated_data)
    cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
    cse_operation = CseOperation.OVDC_DISABLE if k8s_provider == K8sProvider.NONE else CseOperation.OVDC_ENABLE  # noqa: E501
    record_user_action_details(cse_operation=cse_operation, cse_params=cse_params)  # noqa: E501

    try:
        task = ovdc_utils.update_ovdc_k8s_provider_metadata(
            op_ctx.sysadmin_client,
            validated_data[RequestKey.OVDC_ID],
            k8s_provider_data=k8s_provider_info,
            k8s_provider=k8s_provider)

        # Telemetry - Record successful enabling/disabling of ovdc
        record_user_action(cse_operation, status=OperationStatus.SUCCESS)

        return {'task_href': task.get('href')}
    except Exception as err:
        # Telemetry - Record failed enabling/disabling of ovdc
        record_user_action(cse_operation, status=OperationStatus.FAILED)
        raise err


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
def ovdc_info(request_data, op_ctx: ctx.OperationContext):
    """Request handler for ovdc info operation.

    Required data: org_name, ovdc_name

    :return: Dictionary with org VDC k8s provider metadata.
    """
    required = [
        RequestKey.OVDC_ID
    ]
    req_utils.validate_payload(request_data, required)

    # Record telemetry data
    cse_params = copy.deepcopy(request_data)
    cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
    record_user_action_details(cse_operation=CseOperation.OVDC_INFO,
                               cse_params=cse_params)

    return ovdc_utils.get_ovdc_k8s_provider_metadata(
        op_ctx.sysadmin_client,
        ovdc_id=request_data[RequestKey.OVDC_ID])


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
def ovdc_list(request_data, op_ctx: ctx.OperationContext):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s provider metadata.
    """
    defaults = {
        PaginationKey.PAGE_NUMBER: CSE_PAGINATION_FIRST_PAGE_NUMBER,
        PaginationKey.PAGE_SIZE: CSE_PAGINATION_DEFAULT_PAGE_SIZE
    }
    validated_data = {**defaults, **request_data}

    page_number = int(validated_data[PaginationKey.PAGE_NUMBER])
    page_size = int(validated_data[PaginationKey.PAGE_SIZE])

    # Record telemetry data
    cse_params = copy.deepcopy(validated_data)
    cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
    record_user_action_details(cse_operation=CseOperation.OVDC_LIST,
                               cse_params=cse_params)

    ovdcs = []
    result = \
        vcd_utils.get_ovdcs_by_page(op_ctx.client,
                                    page=page_number,
                                    page_size=page_size)
    org_vdcs = result[PaginationKey.VALUES]
    result_total = result[PaginationKey.RESULT_TOTAL]
    next_page_uri = result.get(PaginationKey.NEXT_PAGE_URI)
    prev_page_uri = result.get(PaginationKey.PREV_PAGE_URI)
    for ovdc in org_vdcs:
        ovdc_name = ovdc.get('name')
        org_name = ovdc.get('orgName')
        ovdc_id = vcd_utils.extract_id(ovdc.get('id'))
        k8s_metadata = ovdc_utils.get_ovdc_k8s_provider_metadata(
            op_ctx.sysadmin_client,
            ovdc_id=ovdc_id,
            ovdc_name=ovdc_name,
            org_name=org_name)
        k8s_provider = k8s_metadata[K8S_PROVIDER_KEY]
        ovdc_dict = {
            'name': ovdc_name,
            'org': org_name,
            'k8s provider': k8s_provider
        }
        ovdcs.append(ovdc_dict)
    api_path = CseServerOperationInfo.OVDC_LIST.api_path_format
    next_page_uri = vcd_utils.create_cse_page_uri(op_ctx.client,
                                                  api_path,
                                                  vcd_uri=next_page_uri)
    prev_page_uri = vcd_utils.create_cse_page_uri(op_ctx.client,
                                                  api_path,
                                                  vcd_uri=prev_page_uri)
    return utils.construct_paginated_response(values=ovdcs,
                                              result_total=result_total,
                                              page_number=page_number,
                                              page_size=page_size,
                                              next_page_uri=next_page_uri,
                                              prev_page_uri=prev_page_uri)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_COMPUTE_POLICY_LIST)  # noqa: E501
def ovdc_compute_policy_list(request_data,
                             op_ctx: ctx.OperationContext):
    """Request handler for ovdc compute-policy list operation.

    Required data: ovdc_id

    :return: Dictionary with task href.
    """
    required = [
        RequestKey.OVDC_ID
    ]
    req_utils.validate_payload(request_data, required)

    config = utils.get_server_runtime_config()
    cpm = compute_policy_manager.ComputePolicyManager(
        op_ctx.sysadmin_client,
        log_wire=utils.str_to_bool(config['service'].get('log_wire')))
    compute_policies = []
    for cp in \
            compute_policy_manager.list_cse_sizing_policies_on_vdc(
                cpm,
                request_data[RequestKey.OVDC_ID]):
        policy = {
            'name': cp['display_name'],
            'id': cp['id'],
            'href': cp['href']
        }
        compute_policies.append(policy)
    return compute_policies


def ovdc_compute_policy_update(request_data,
                               op_ctx: ctx.OperationContext):
    """Request handler for ovdc compute-policy update operation.

    Required data: ovdc_id, compute_policy_action, compute_policy_names

    :return: Dictionary with task href.
    """
    required = [
        RequestKey.OVDC_ID,
        RequestKey.COMPUTE_POLICY_ACTION,
        RequestKey.COMPUTE_POLICY_NAME
    ]
    defaults = {
        RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS: False,
    }
    validated_data = {**defaults, **request_data}
    req_utils.validate_payload(validated_data, required)

    action = validated_data[RequestKey.COMPUTE_POLICY_ACTION]
    cp_name = validated_data[RequestKey.COMPUTE_POLICY_NAME]
    ovdc_id = validated_data[RequestKey.OVDC_ID]
    remove_compute_policy_from_vms = validated_data[RequestKey.REMOVE_COMPUTE_POLICY_FROM_VMS] # noqa: E501
    try:
        config = utils.get_server_runtime_config()
        cpm = compute_policy_manager.ComputePolicyManager(
            op_ctx.sysadmin_client,
            log_wire=utils.str_to_bool(config['service'].get('log_wire'))) # noqa: E501
        cp_href = None
        cp_id = None
        if cp_name == SYSTEM_DEFAULT_COMPUTE_POLICY_NAME:
            for _cp in cpm.list_compute_policies_on_vdc(ovdc_id):
                if _cp['name'] == cp_name:
                    cp_href = _cp['href']
                    cp_id = _cp['id']
        else:
            try:
                _cp = compute_policy_manager.get_cse_vdc_compute_policy(cpm, cp_name)  # noqa: E501
                cp_href = _cp['href']
                cp_id = _cp['id']
            except vcd_e.EntityNotFoundException:
                pass

        if cp_href is None:
            raise e.BadRequestError(f"Compute policy '{cp_name}' not found.")

        if action == ComputePolicyAction.ADD:
            cpm.add_compute_policy_to_vdc(ovdc_id, cp_href)
            # Record telemetry data
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_ADD)
            return f"Added compute policy '{cp_name}' ({cp_id}) to ovdc " \
                   f"({ovdc_id})"

        if action == ComputePolicyAction.REMOVE:
            # TODO: fix remove_compute_policy by implementing a proper way
            # for calling async methods without having to pass op_ctx
            # outside handlers.
            op_ctx.is_async = True
            response = cpm.remove_vdc_compute_policy_from_vdc(
                ovdc_id,
                cp_href,
                force=remove_compute_policy_from_vms)
            # Follow task_href to completion in a different thread and end
            # operation context
            _follow_task(op_ctx, response['task_href'], ovdc_id)
            # Record telemetry data
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_REMOVE)
            return response

        raise e.BadRequestError("Unsupported compute policy action")

    except Exception as err:
        # Record telemetry data failure`
        if action == ComputePolicyAction.ADD:
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_ADD,
                               status=OperationStatus.FAILED)
        elif action == ComputePolicyAction.REMOVE:
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_REMOVE,
                               status=OperationStatus.FAILED)
        raise err


@utils.run_async
def _follow_task(op_ctx: ctx.OperationContext, task_href: str, ovdc_id: str):
    try:
        task = vcd_task.Task(client=op_ctx.sysadmin_client)
        session = op_ctx.sysadmin_client.get_vcloud_session()
        vdc = vcd_utils.get_vdc(op_ctx.sysadmin_client, vdc_id=ovdc_id)
        org = vcd_utils.get_org(op_ctx.sysadmin_client)
        user_name = session.get('user')
        user_href = org.get_user(user_name).get('href')
        msg = "Remove ovdc compute policy"
        # TODO(pyvcloud): Add method to retireve task from task href
        t = task.update(
            status=vcd_task.TaskStatus.RUNNING.value,
            namespace='vcloud.cse',
            operation=msg,
            operation_name=msg,
            details='',
            progress=None,
            owner_href=vdc.href,
            owner_name=vdc.name,
            owner_type=vcd_client.EntityType.VDC.value,
            user_href=user_href,
            user_name=user_name,
            org_href=op_ctx.user.org_href,
            task_href=task_href)
        op_ctx.sysadmin_client.get_task_monitor().wait_for_status(t)
    except Exception as err:
        logger.SERVER_LOGGER.error(f"{err}")
    finally:
        if op_ctx.sysadmin_client:
            op_ctx.end()
