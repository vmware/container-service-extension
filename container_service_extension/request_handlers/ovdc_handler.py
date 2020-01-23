# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy

from pyvcloud.vcd.exceptions import EntityNotFoundException

from container_service_extension.compute_policy_manager import ComputePolicyManager # noqa: E501
from container_service_extension.exceptions import BadRequestError
from container_service_extension.exceptions import CseServerError
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import ComputePolicyAction
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import OperationStatus
from container_service_extension.telemetry.telemetry_handler import record_user_action  # noqa: E501
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
import container_service_extension.utils as utils


SYSTEM_DEFAULT_COMPUTE_POLICY_NAME = "System Default"


def ovdc_update(request_data, tenant_auth_token, is_jwt_token):
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
                raise CseServerError('CSE is not configured to work with PKS.')
            required = [
                RequestKey.PKS_PLAN_NAME,
                RequestKey.PKS_CLUSTER_DOMAIN
            ]
            req_utils.validate_payload(validated_data, required)

            k8s_provider_info = ovdc_utils.construct_k8s_metadata_from_pks_cache(  # noqa: E501
                ovdc_id=validated_data[RequestKey.OVDC_ID],
                org_name=validated_data[RequestKey.ORG_NAME],
                pks_plans=validated_data[RequestKey.PKS_PLAN_NAME],
                pks_cluster_domain=validated_data[RequestKey.PKS_CLUSTER_DOMAIN],  # noqa: E501
                k8s_provider=k8s_provider)
            ovdc_utils.create_pks_compute_profile(k8s_provider_info,
                                                  tenant_auth_token,
                                                  is_jwt_token,
                                                  validated_data)

        task = ovdc_utils.update_ovdc_k8s_provider_metadata(
            ovdc_id=validated_data[RequestKey.OVDC_ID],
            k8s_provider_data=k8s_provider_info,
            k8s_provider=k8s_provider)

        # Telemetry - Record successful enabling/disabling of ovdc
        record_user_action(cse_operation, status=OperationStatus.SUCCESS)

        return {'task_href': task.get('href')}
    except Exception as err:
        # Telemetry - Record failed enabling/disabling of ovdc
        record_user_action(cse_operation, status=OperationStatus.FAILED, message=str(err))  # noqa: E501
        raise err


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_INFO)
def ovdc_info(request_data, tenant_auth_token, is_jwt_token):
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
    record_user_action_details(cse_operation=CseOperation.OVDC_INFO, cse_params=cse_params)  # noqa: E501

    return ovdc_utils.get_ovdc_k8s_provider_metadata(
        ovdc_id=request_data[RequestKey.OVDC_ID])


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_LIST)
def ovdc_list(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s provider metadata.
    """
    defaults = {
        RequestKey.LIST_PKS_PLANS: False
    }
    validated_data = {**defaults, **request_data}

    client = vcd_utils.connect_vcd_user_via_token(
        tenant_auth_token, is_jwt_token)
    # TODO check if this is needed
    list_pks_plans = utils.str_to_bool(validated_data[RequestKey.LIST_PKS_PLANS]) # noqa: E501

    # Record telemetry data
    cse_params = copy.deepcopy(validated_data)
    cse_params[RequestKey.LIST_PKS_PLANS] = list_pks_plans
    record_user_action_details(cse_operation=CseOperation.OVDC_LIST, cse_params=cse_params)  # noqa: E501

    return ovdc_utils.get_ovdc_list(client, list_pks_plans=list_pks_plans,
                                    tenant_auth_token=tenant_auth_token,
                                    is_jwt_token=is_jwt_token)


@record_user_action_telemetry(cse_operation=CseOperation.OVDC_COMPUTE_POLICY_LIST)  # noqa: E501
def ovdc_compute_policy_list(request_data, tenant_auth_token, is_jwt_token):
    """Request handler for ovdc compute-policy list operation.

    Required data: ovdc_id

    :return: Dictionary with task href.
    """
    required = [
        RequestKey.OVDC_ID
    ]
    req_utils.validate_payload(request_data, required)

    client = vcd_utils.connect_vcd_user_via_token(
        tenant_auth_token, is_jwt_token)

    cpm = ComputePolicyManager(client)
    return cpm.list_compute_policies_on_vdc(request_data[RequestKey.OVDC_ID])


def ovdc_compute_policy_update(request_data, tenant_auth_token, is_jwt_token):
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

        client = vcd_utils.connect_vcd_user_via_token(
            tenant_auth_token, is_jwt_token)

        cpm = ComputePolicyManager(client)
        cp_href = None
        cp_id = None
        if cp_name == SYSTEM_DEFAULT_COMPUTE_POLICY_NAME:
            for _cp in cpm.list_compute_policies_on_vdc(ovdc_id):
                if _cp['name'] == cp_name:
                    cp_href = _cp['href']
                    cp_id = _cp['id']
        else:
            try:
                _cp = cpm.get_policy(cp_name)
                cp_href = _cp['href']
                cp_id = _cp['id']
            except EntityNotFoundException:
                pass

        if cp_href is None:
            raise BadRequestError(f"Compute policy '{cp_name}' not found.")

        if action == ComputePolicyAction.ADD:
            cpm.add_compute_policy_to_vdc(ovdc_id, cp_href)
            # Record telemetry data
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_ADD)
            return f"Added compute policy '{cp_name}' ({cp_id}) to ovdc " \
                   f"({ovdc_id})"

        if action == ComputePolicyAction.REMOVE:
            task_href = cpm.remove_compute_policy_from_vdc(
                ovdc_id,
                cp_href,
                remove_compute_policy_from_vms=remove_compute_policy_from_vms)
            # Record telemetry data
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_REMOVE)
            return task_href

        raise BadRequestError("Unsupported compute policy action")

    except Exception as err:
        # Record telemetry data failure
        if action == ComputePolicyAction.ADD:
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_ADD, status=OperationStatus.FAILED, message=str(err))  # noqa: E501
        elif action == ComputePolicyAction.REMOVE:
            record_user_action(CseOperation.OVDC_COMPUTE_POLICY_REMOVE, status=OperationStatus.FAILED, message=str(err))  # noqa: E501
        raise err
