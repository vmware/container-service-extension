from pyvcloud.vcd.exceptions import EntityNotFoundException

from container_service_extension.compute_policy_manager import ComputePolicyManager # noqa: E501
from container_service_extension.exceptions import CseServerError
import container_service_extension.ovdc_utils as ovdc_utils
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import ComputePolicyAction
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils


def ovdc_update(request_data, tenant_auth_token):
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
    utils.ensure_keys_in_dict(required, request_data, dict_name='data')
    validated_data = request_data

    k8s_provider = validated_data[RequestKey.K8S_PROVIDER]
    k8s_provider_info = {K8S_PROVIDER_KEY: k8s_provider}

    if k8s_provider == K8sProvider.PKS:
        if not utils.is_pks_enabled():
            raise CseServerError('CSE is not configured to work with PKS.')
        required = [
            RequestKey.PKS_PLAN_NAME,
            RequestKey.PKS_CLUSTER_DOMAIN
        ]
        utils.ensure_keys_in_dict(required, validated_data, dict_name='data')

        k8s_provider_info = ovdc_utils.construct_k8s_metadata_from_pks_cache(
            ovdc_id=validated_data[RequestKey.OVDC_ID],
            org_name=validated_data[RequestKey.ORG_NAME],
            pks_plans=validated_data[RequestKey.PKS_PLAN_NAME],
            pks_cluster_domain=validated_data[RequestKey.PKS_CLUSTER_DOMAIN],
            k8s_provider=k8s_provider)
        ovdc_utils.create_pks_compute_profile(k8s_provider_info,
                                              tenant_auth_token,
                                              validated_data)

    task = ovdc_utils.update_ovdc_k8s_provider_metadata(
        ovdc_id=validated_data[RequestKey.OVDC_ID],
        k8s_provider_data=k8s_provider_info,
        k8s_provider=k8s_provider)

    return {'task_href': task.get('href')}


def ovdc_info(request_data, tenant_auth_token):
    """Request handler for ovdc info operation.

    Required data: org_name, ovdc_name

    :return: Dictionary with org VDC k8s provider metadata.
    """
    required = [
        RequestKey.OVDC_ID
    ]
    utils.ensure_keys_in_dict(required, request_data, dict_name='data')

    return ovdc_utils.get_ovdc_k8s_provider_metadata(
        ovdc_id=request_data[RequestKey.OVDC_ID])


def ovdc_list(request_data, tenant_auth_token):
    """Request handler for ovdc list operation.

    :return: List of dictionaries with org VDC k8s provider metadata.
    """
    client, _ = vcd_utils.connect_vcd_user_via_token(tenant_auth_token)
    list_pks_plans = utils.str_to_bool(request_data[RequestKey.LIST_PKS_PLANS])

    return ovdc_utils.get_ovdc_list(client, list_pks_plans=list_pks_plans,
                                    tenant_auth_token=tenant_auth_token)


def ovdc_compute_policy_list(request_data, tenant_auth_token):
    """Request handler for ovdc compute-policy list operation.

    Required data: ovdc_id

    :return: Dictionary with task href.
    """
    required = [
        RequestKey.OVDC_ID
    ]
    utils.ensure_keys_in_dict(required, request_data, dict_name='data')
    client, _ = vcd_utils.connect_vcd_user_via_token(tenant_auth_token)

    cpm = ComputePolicyManager(client)
    return cpm.list_compute_policies_on_vdc(vdc_id=request_data[RequestKey.OVDC_ID]) # noqa: E501


def ovdc_compute_policy_update(request_data, tenant_auth_token):
    """Request handler for ovdc compute-policy update operation.

    Required data: ovdc_id, compute_policy_action, compute_policy_names

    :return: Dictionary with task href.
    """
    required = [
        RequestKey.OVDC_ID,
        RequestKey.COMPUTE_POLICY_ACTION,
        RequestKey.COMPUTE_POLICY_NAME
    ]
    utils.ensure_keys_in_dict(required, request_data, dict_name='data')
    client, _ = vcd_utils.connect_vcd_user_via_token(tenant_auth_token)
    action = request_data[RequestKey.COMPUTE_POLICY_ACTION]
    cp_name = request_data[RequestKey.COMPUTE_POLICY_NAME]
    ovdc_id = request_data[RequestKey.OVDC_ID]

    cpm = ComputePolicyManager(client)
    cp = cpm.get_policy(cp_name)
    if cp is None:
        raise ValueError(f"Compute policy '{cp_name}' does not exist")
    cp_href = cp['href']

    if action == ComputePolicyAction.ADD:
        cpm.add_compute_policy_to_vdc(cp_href, vdc_id=ovdc_id)
        return f"Added compute policy '{cp_name}' to ovdc '{ovdc_id}'"

    if action == ComputePolicyAction.REMOVE:
        try:
            cpm.remove_compute_policy_from_vdc(cp_href, vdc_id=ovdc_id)
        except EntityNotFoundException:
            raise EntityNotFoundException(f"Compute policy '{cp_name}' not "
                                          f"found in ovdc '{ovdc_id}'")
        except Exception:
            # This ensures that BadRequestException message is printed
            # to console. (error when ovdc currently has VMs/vApp
            # templates with the compute policy reference, so compute policy
            # cannot be removed)
            raise Exception(f"Could not remove compute policy '{cp_name}' "
                            f"from ovdc '{ovdc_id}' (check that no vApp"
                            f" templates or VMs currently contain a reference"
                            f" to the compute policy).")
        return f"Removed compute policy '{cp_name}' from ovdc '{ovdc_id}'"

    raise ValueError("Unsupported compute policy action")
