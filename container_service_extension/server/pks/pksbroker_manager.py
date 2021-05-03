# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.org import Org

from container_service_extension.common.constants.server_constants import K8S_PROVIDER_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import K8sProvider  # noqa: E501
import container_service_extension.common.utils.ovdc_utils as ovdc_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.security.context.operation_context as ctx
from container_service_extension.server.pks.pksbroker import PksBroker

DEFAULT_API_VERSION = vcd_client.ApiVersion.VERSION_33.value


def list_clusters(request_data, op_ctx: ctx.OperationContext):
    request_data['is_admin_request'] = True
    pks_clusters = []
    pks_contexts = create_pks_context_for_all_accounts_in_org(op_ctx)
    for pks_context in pks_contexts:
        pks_broker = PksBroker(pks_context, op_ctx)
        # Get all cluster information to get vdc name from compute-profile-name
        pks_clusters.extend(pks_broker.list_clusters(data=request_data))
    return pks_clusters


def create_pks_context_for_all_accounts_in_org(op_ctx: ctx.OperationContext):  # noqa: E501
    """Create PKS context for accounts in a given Org.

    If user is Sysadmin
        Creates PKS contexts for all PKS accounts defined in the entire
        system.
    else
        Creates PKS contexts for all PKS accounts assigned to the org.
        However if separate service accounts for each org hasn't been
        configured by admin via pks.yaml, then PKS accounts of the PKS
        server corresponding to the vCenters powering the individual
        orgVDC of the org will be picked up for creating the PKS contexts.

    :return: list of dict, where each dictionary is a PKS context

    :rtype: list
    """
    pks_cache = server_utils.get_pks_cache()
    if pks_cache is None:
        return []

    client_v33 = op_ctx.get_client(api_version=DEFAULT_API_VERSION)
    if client_v33.is_sysadmin():
        all_pks_account_info = pks_cache.get_all_pks_account_info_in_system()
        pks_ctx_list = [ovdc_utils.construct_pks_context(pks_account_info, credentials_required=True) for pks_account_info in all_pks_account_info]  # noqa: E501
        return pks_ctx_list

    if pks_cache.do_orgs_have_exclusive_pks_account():
        pks_account_infos = pks_cache.get_exclusive_pks_accounts_info_for_org(op_ctx.user.org_name)  # noqa: E501
        pks_ctx_list = [ovdc_utils.construct_pks_context(pks_account_info, credentials_required=True) for pks_account_info in pks_account_infos]  # noqa: E501
        return pks_ctx_list

    org_resource = client_v33.get_org()
    org = Org(client_v33, resource=org_resource)
    vdc_names = [vdc['name'] for vdc in org.list_vdcs()]
    # Constructing dict instead of list to avoid duplicates
    # TODO() figure out a way to add pks contexts to a set directly
    pks_ctx_dict = {}
    sysadmin_client_v33 = \
        op_ctx.get_sysadmin_client(api_version=DEFAULT_API_VERSION)
    for vdc_name in vdc_names:
        # this is a full blown pks_account_info + pvdc_info +
        # compute_profile_name dictionary
        k8s_metadata = ovdc_utils.get_ovdc_k8s_provider_metadata(
            sysadmin_client_v33,
            ovdc_name=vdc_name,
            org_name=op_ctx.user.org_name,
            include_credentials=True)
        if k8s_metadata[K8S_PROVIDER_KEY] == K8sProvider.PKS:
            pks_ctx_dict[k8s_metadata['vc']] = k8s_metadata

    return list(pks_ctx_dict.values())
