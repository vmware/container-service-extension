# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy
import urllib

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.exceptions as vcd_e
import pyvcloud.vcd.utils as pyvcd_utils

import container_service_extension.exceptions as e
import container_service_extension.logger as logger
import container_service_extension.operation_context as ctx
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pksbroker as pksbroker
import container_service_extension.pksbroker_manager as pksbroker_manager
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import CseOperation as CseServerOperationInfo  # noqa: E501
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import PaginationKey
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.telemetry_handler import record_user_action  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_details  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
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
    cse_operation = CseOperation.OVDC_DISABLE if k8s_provider == K8sProvider.NONE else CseOperation.OVDC_ENABLE  # noqa: E501
    record_user_action_details(cse_operation=cse_operation, cse_params=cse_params)  # noqa: E501

    try:
        if k8s_provider == K8sProvider.PKS:
            if not utils.is_pks_enabled():
                raise e.CseServerError('CSE server is not '
                                       'configured to work with PKS.')
            required = [
                RequestKey.PKS_PLAN_NAME,
                RequestKey.PKS_CLUSTER_DOMAIN
            ]
            req_utils.validate_payload(validated_data, required)

            # Check if target ovdc is not already enabled for other non PKS k8 providers # noqa: E501
            ovdc_metadata = ovdc_utils.get_ovdc_k8s_provider_metadata(
                op_ctx.sysadmin_client,
                ovdc_id=validated_data[RequestKey.OVDC_ID])
            ovdc_k8_provider = ovdc_metadata.get(K8S_PROVIDER_KEY)
            if ovdc_k8_provider != K8sProvider.NONE and \
                    ovdc_k8_provider != k8s_provider:
                raise e.CseServerError("Ovdc already enabled for different K8 provider")  # noqa: E501

            k8s_provider_info = ovdc_utils.construct_k8s_metadata_from_pks_cache(  # noqa: E501
                op_ctx.sysadmin_client,
                ovdc_id=validated_data[RequestKey.OVDC_ID],
                org_name=validated_data[RequestKey.ORG_NAME],
                pks_plans=validated_data[RequestKey.PKS_PLAN_NAME],
                pks_cluster_domain=validated_data[RequestKey.PKS_CLUSTER_DOMAIN],  # noqa: E501
                k8s_provider=k8s_provider)
            ovdc_utils.create_pks_compute_profile(validated_data,
                                                  op_ctx,
                                                  k8s_provider_info)

        task = ovdc_utils.update_ovdc_k8s_provider_metadata(
            op_ctx.sysadmin_client,
            validated_data[RequestKey.OVDC_ID],
            k8s_provider_data=k8s_provider_info,
            k8s_provider=k8s_provider)

        # Telemetry - Record successful enabling/disabling of ovdc
        record_user_action(cse_operation, status=OperationStatus.SUCCESS)

        return {'task_href': task.get('href')}
    except Exception as err:
        logger.SERVER_LOGGER.error(f"Error while updating OVDC: {str(err)}")
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
        RequestKey.LIST_PKS_PLANS: False,
        PaginationKey.PAGE_NUMBER: CSE_PAGINATION_FIRST_PAGE_NUMBER,
        PaginationKey.PAGE_SIZE: CSE_PAGINATION_DEFAULT_PAGE_SIZE
    }
    validated_data = {**defaults, **request_data}

    page_number = int(validated_data[PaginationKey.PAGE_NUMBER])
    page_size = int(validated_data[PaginationKey.PAGE_SIZE])
    list_pks_plans = utils.str_to_bool(validated_data[RequestKey.LIST_PKS_PLANS]) # noqa: E501

    # Record telemetry data
    cse_params = copy.deepcopy(validated_data)
    cse_params[RequestKey.LIST_PKS_PLANS] = list_pks_plans
    record_user_action_details(cse_operation=CseOperation.OVDC_LIST,
                               cse_params=cse_params)

    if list_pks_plans and not op_ctx.client.is_sysadmin():
        raise e.UnauthorizedRequestError(
            'Operation denied. Enterprise PKS plans visible only '
            'to System Administrators.')

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
        if list_pks_plans:
            pks_plans = ''
            pks_server = ''
            if k8s_provider == K8sProvider.PKS:
                # vc name for vdc can only be found using typed query
                qfilter = f"name=={urllib.parse.quote(ovdc_name)};" \
                          f"orgName=={urllib.parse.quote(org_name)}"
                q = op_ctx.client.get_typed_query(
                    vcd_client.ResourceType.ADMIN_ORG_VDC.value,
                    query_result_format=vcd_client.QueryResultFormat.RECORDS, # noqa: E501
                    qfilter=qfilter)
                # should only ever be one element in the generator
                ovdc_records = list(q.execute())
                if len(ovdc_records) == 0:
                    raise vcd_e.EntityNotFoundException(
                        f"Org VDC {ovdc_name} not found in org {org_name}")
                ovdc_record = None
                for record in ovdc_records:
                    ovdc_record = pyvcd_utils.to_dict(
                        record, resource_type=vcd_client.ResourceType.ADMIN_ORG_VDC.value) # noqa: E501
                    break

                vc_to_pks_plans_map = {}
                pks_contexts = pksbroker_manager.create_pks_context_for_all_accounts_in_org(op_ctx)  # noqa: E501

                for pks_context in pks_contexts:
                    if pks_context['vc'] in vc_to_pks_plans_map:
                        continue
                    pks_broker = pksbroker.PksBroker(pks_context,
                                                     op_ctx)
                    plans = pks_broker.list_plans()
                    plan_names = [plan.get('name') for plan in plans]
                    vc_to_pks_plans_map[pks_context['vc']] = \
                        [plan_names, pks_context['host']]

                pks_plan_and_server_info = vc_to_pks_plans_map.get(
                    ovdc_record['vcName'], [])
                if len(pks_plan_and_server_info) > 0:
                    pks_plans = pks_plan_and_server_info[0]
                    pks_server = pks_plan_and_server_info[1]

            ovdc_dict['pks api server'] = pks_server
            ovdc_dict['available pks plans'] = pks_plans
        ovdcs.append(ovdc_dict)
    api_path = CseServerOperationInfo.PKS_OVDC_LIST.api_path_format
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
