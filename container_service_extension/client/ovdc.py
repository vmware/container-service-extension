# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd import utils

from container_service_extension.utils import get_vdc
from container_service_extension.utils import process_response


class Ovdc(object):
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def list(self):
        method = 'GET'
        uri = f'{self._uri}/ovdc'
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/json')
        return process_response(response)

    def enable_ovdc_for_k8s(self,
                            ovdc_name,
                            k8s_provider=None,
                            pks_plans=None,
                            pks_cluster_domain=None,
                            org_name=None):
        """Enable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the ovdc to be enabled
        :param str k8s_provider: Name of the container provider
        :param str pks_plans: pks plans separated by comma
        :param str pks_cluster_domain: Suffix of the domain name, which will be
         used to construct FQDN of the clusters.
        :param str org_name: Name of organization that belongs to ovdc_name

        :return: response object

        :rtype: dict
        """
        method = 'PUT'
        ovdc = get_vdc(self.client, ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.resource.get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}/info'

        # TODO() this is a temporary fix to hack in the name change
        # Naming changes (vcd -> native) (pks -> enterprise-pks)
        # More work needs to be done to fix how k8s_provider names are handled
        # Suggestion: we should have an enum for k8s_provider
        if k8s_provider == 'native':
            k8s_provider = 'vcd'
        if k8s_provider == 'enterprise-pks':
            k8s_provider = 'pks'

        data = {
            'ovdc_id': ovdc_id,
            'ovdc_name': ovdc_name,
            'container_provider': k8s_provider,
            'pks_plans': pks_plans,
            'pks_cluster_domain': pks_cluster_domain,
            'org_name': org_name,
            'enable': True
        }

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        return process_response(response)

    def disable_ovdc_for_k8s(self, ovdc_name, org_name=None):
        """Disable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the ovdc to be enabled
        :param str org_name: Name of organization that belongs to ovdc_name

        :return: response object

        :rtype: dict
        """
        method = 'PUT'
        ovdc = get_vdc(self.client, ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.resource.get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}/info'
        data = {
            'ovdc_id': ovdc_id,
            'ovdc_name': ovdc_name,
            'container_provider': None,
            'pks_plans': None,
            'org_name': org_name,
            'disable': True
        }

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=data,
            media_type=None,
            accept_type='application/*+json')
        return process_response(response)

    def info_ovdc_for_k8s(self, ovdc_name, org_name=None):
        """Disable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the ovdc to be enabled
        :param str org_name: Name of organization that belongs to ovdc_name

        :return: response object

        :rtype: dict
        """
        method = 'GET'
        ovdc = get_vdc(self.client, ovdc_name, org_name=org_name,
                       is_admin_operation=True)
        ovdc_id = utils.extract_id(ovdc.resource.get('id'))
        uri = f'{self._uri}/ovdc/{ovdc_id}/info'

        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json')
        return process_response(response)
