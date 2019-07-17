# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils

from container_service_extension.client.response_processor import \
    process_response
from container_service_extension.pyvcloud_utils import get_vdc
from container_service_extension.server_constants import K8sProviders
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RequestMethod


class Ovdc:
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def list_ovdc_for_k8s(self, get_pks_plans=False):
        method = RequestMethod.GET
        uri = f'{self._uri}/ovdcs'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json',
            params={RequestKey.GET_PKS_PLANS: get_pks_plans})
        return process_response(response)

    def update_ovdc_for_k8s(self,
                            enable,
                            ovdc_name,
                            org_name=None,
                            container_provider=None,
                            pks_plan=None,
                            pks_cluster_domain=None):
        """Enable/Disable ovdc for k8s for the given container provider.

        :param bool enable: If set to True will enable the vdc for the
            paricular container_provider else if set to False, K8 support on
            the vdc will be disabled.
        :param str ovdc_name: Name of the ovdc to be enabled
        :param str k8s_provider: Name of the container provider
        :param str pks_plan: PKS plan
        :param str pks_cluster_domain: Suffix of the domain name, which will be
         used to construct FQDN of the clusters.
        :param str org_name: Name of organization that belongs to ovdc_name

        :return: response object

        :rtype: dict
        """
        method = RequestMethod.PUT
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}'

        if not enable:
            container_provider = K8sProviders.NONE
            pks_plan = None
            pks_cluster_domain = None

        data = {
            RequestKey.OVDC_ID: ovdc_id,
            RequestKey.OVDC_NAME: ovdc_name,
            RequestKey.ORG_NAME: org_name,
            RequestKey.K8S_PROVIDER: container_provider,
            RequestKey.PKS_PLAN_NAME: pks_plan,
            RequestKey.PKS_CLUSTER_DOMAIN: pks_cluster_domain,
        }

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type='application/json',
            accept_type='application/json')
        return process_response(response)

    def info_ovdc_for_k8s(self, ovdc_name, org_name=None):
        """Disable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the ovdc to be enabled
        :param str org_name: Name of organization that belongs to ovdc_name

        :return: response object

        :rtype: dict
        """
        method = RequestMethod.GET
        ovdc = get_vdc(self.client, vdc_name=ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.get_resource().get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}'

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            accept_type='application/json')
        return process_response(response)
