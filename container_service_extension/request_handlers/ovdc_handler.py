import container_service_extension.pyvcloud_utils as vcd_utils

from container_service_extension.exceptions import CseServerError
import container_service_extension.ovdc_utils as ovdc_utils
from container_service_extension.server_constants import K8sProvider
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils


def ovdc_update(request_dict, tenant_auth_token):
    """Request handler for ovdc enable, disable operations.

    Required data: (str) org_name, (str) ovdc_name, (str) k8s_provider.
    Conditional data: if k8s_provider is 'ent-pks', (str) pks_plan_name, (str) pks_cluster_domain are required.
    """

    required = [RequestKey.ORG_NAME, RequestKey.OVDC_NAME, RequestKey.K8S_PROVIDER]
    utils.check_keys_in_dikt(required, request_dict, dict_name='request')
    if request_dict.get(RequestKey.K8S_PROVIDER) == K8sProvider.PKS:
        required = [RequestKey.PKS_PLAN_NAME, RequestKey.PKS_CLUSTER_DOMAIN]
        utils.check_keys_in_dikt(required, request_dict, dict_name='request')

    k8s_provider_info = ovdc_utils.construct_ctr_prov_ctx_from_pks_cache(
        ovdc_id=request_dict.get(RequestKey.OVDC_ID),
        org_name=request_dict.get(RequestKey.ORG_NAME),
        pks_plans=request_dict.get(RequestKey.PKS_PLAN_NAME),
        pks_cluster_domain=request_dict.get(RequestKey.PKS_CLUSTER_DOMAIN),
        container_provider=request_dict.get(RequestKey.K8S_PROVIDER))

    if request_dict.get(RequestKey.K8S_PROVIDER) == K8sProvider.PKS:
        if not utils.is_pks_enabled():
            raise CseServerError('CSE is not configured to work with PKS.')
        ovdc_utils.create_pks_compute_profile(k8s_provider_info, tenant_auth_token, request_dict)

    task = ovdc_utils.set_ovdc_k8s_provider_metadata(
        ovdc_id=request_dict.get(RequestKey.OVDC_ID),
        k8s_provider_data=k8s_provider_info,
        k8s_provider=request_dict.get(RequestKey.K8S_PROVIDER))
    return {'task_href': task.get('href')}


def ovdc_info(request_dict, tenant_auth_token):
    """Request handler for ovdc info operation.
    """

    required = [RequestKey.ORG_NAME, RequestKey.OVDC_NAME]
    utils.check_keys_in_dikt(required, request_dict, dict_name='request')

    return ovdc_utils.get_ovdc_k8s_provider_metadata(
        org_name=request_dict.get(RequestKey.ORG_NAME),
        ovdc_name=request_dict.get(RequestKey.OVDC_NAME),
        ovdc_id=request_dict.get(RequestKey.OVDC_ID))


def ovdc_list(request_dict, tenant_auth_token):
    """Request handler for ovdc list operation.
    """

    client, _ = vcd_utils.connect_vcd_user_via_token(tenant_auth_token)
    list_pks_plans = utils.str_to_bool(request_dict.get(RequestKey.LIST_PKS_PLANS))

    return ovdc_utils.get_ovdc_list(client, list_pks_plans=list_pks_plans, request_dict=request_dict, tenant_auth_token=tenant_auth_token)
