# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import \
    COMPUTE_POLICY_NAME_PREFIX
from container_service_extension.shared_constants import RequestMethod


class ComputePolicyManager:
    """Manages creating, deleting, updating cloudapi compute policies.

    All policy names are prepended with CSE specific literal and restored to
    original names when returned back to the caller.
    """

    def __init__(self, host, tenant_auth_token, verify_ssl):
        """Initialize ComputePolicyManager Object.

        :param str host: cloudapi host name
        :param str tenant_auth_token: HTTP basic authentication token
        :param bool verify_ssl: if True, verify SSL certificates of remote
        host, else ignore verification.
        """
        self.tenant_auth_token = tenant_auth_token
        self.host = host
        self.verify_ssl = verify_ssl
        self.cloud_api_client = CloudApiClient(
            host=host,
            auth_token=tenant_auth_token,
            verify_ssl=verify_ssl)

    def list_policies(self):
        """Get all policies that are created by CSE.

        :return: list of CSE created policies
        :rtype: list of dict
        """
        policies = self.cloud_api_client.do_request(
            RequestMethod.GET, CloudApiResource.VDC_COMPUTE_POLICIES)
        for policy in policies['values']:
            if COMPUTE_POLICY_NAME_PREFIX in policy['name']:
                policy['name'] = \
                    self._restore_original_policy_name(policy['name'])

        return policies['values']

    def get_policy(self, policy_name):
        """Get the compute policy information for the given policy name.

        :param str policy_name: name of the compute policy

        :return: policy details
        :rtype: dict
        """
        for policy_dict in self.list_policies():
            if policy_dict['name'] == policy_name:
                policy_dict['href'] = self._get_policy_href(policy_dict['id'])
                return policy_dict
        return {}

    def add_policy(self, policy_name, description=None):
        """Add policy with the given name and description.

        :param str policy_name: name of the compute policy
        :param str description: description about the policy

        :return: created policy information
        :rtype: dict
        """
        policy_info = {}
        policy_info['name'] = self._get_cse_policy_name(policy_name)
        if description:
            policy_info['description'] = description
        created_policy = self.cloud_api_client.do_request(
            RequestMethod.POST,
            resource_url_relative_path=CloudApiResource.VDC_COMPUTE_POLICIES,
            payload=policy_info)
        created_policy['name'] = self._restore_original_policy_name(
            created_policy['name'])
        created_policy['href'] = self._get_policy_href(created_policy['id'])
        return created_policy

    def remove_policy(self, policy_name):
        """Remove the compute policy with the given name.

        :param str policy_name: name of the compute policy
        """
        policy_info = self.get_policy(policy_name)
        if bool(policy_info):
            policy_info['name'] = \
                self._get_cse_policy_name(policy_info['name'])
            resource_url_relative_path = \
                f"{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_info['id']}"
            return self.cloud_api_client.do_request(
                RequestMethod.DELETE,
                resource_url_relative_path=resource_url_relative_path)

    def update_policy(self, policy_name, new_policy_info):
        """Update the existing compute policy with new policy information.

        :param str policy_name: existing policy name
        :param dict new_policy_info: updated policy information with name and
        optional description

        :return: updated policy information; if no policy is found, return None
        :rtype: dict
        """
        policy_info = self.get_policy(policy_name)
        if bool(policy_info):
            new_policy_info['name'] = \
                self._get_cse_policy_name(new_policy_info['name'])
            resource_url_relative_path = \
                f"{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_info['id']}"
            updated_policy = self.cloud_api_client.do_request(
                RequestMethod.PUT,
                resource_url_relative_path=resource_url_relative_path,
                payload=new_policy_info)
            updated_policy['name'] = self._restore_original_policy_name(
                updated_policy['name'])
            updated_policy['href'] = policy_info['href']
            return updated_policy

    def _get_cse_policy_name(self, policy_name):
        """Add cse specific prefix to the policy name.

        :param str policy_name: name of the compute policy

        :return: policy name unique to cse
        :rtype: str
        """
        return f"{COMPUTE_POLICY_NAME_PREFIX}{policy_name}"

    def _restore_original_policy_name(self, policy_name):
        """Remove cse specific prefix from the given policy name.

        :param str policy_name: name of the policy

        :return: policy name after removing cse specific prefix
        :rtype: str
        """
        return policy_name.replace(COMPUTE_POLICY_NAME_PREFIX, '')

    def _get_policy_href(self, policy_id):
        """Construct policy href from given policy id.

        :param str policy_id: policy id

        :return: policy href
        :rtype: str
        """
        return f"{self.cloud_api_client._versioned_url}{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_id}"  # noqa
