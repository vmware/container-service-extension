from container_service_extension.utils import process_response


class Ovdc(object):
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def enable_ovdc_for_k8s(self,
                            ovdc_name,
                            container_provider=None,
                            pks_plans=None,
                            org_name=None):
        """Enable ovdc for k8s for the given container provider.

        :param str ovdc_name: Name of the ovdc to be enabled
        :param str container_provider: Name of the container provider
        :param str pks_plans: pks plans separated by comma
        :param str org_name: Name of organization that belongs to ovdc_name

        :return: response object

        :rtype: dict
        """
        method = 'POST'
        uri = f'{self._uri}/ovdc'
        data = {
            'ovdc_name': ovdc_name,
            'container_provider': container_provider,
            'pks_plans': pks_plans,
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
        method = 'POST'
        uri = f'{self._uri}/ovdc'
        data = {
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
