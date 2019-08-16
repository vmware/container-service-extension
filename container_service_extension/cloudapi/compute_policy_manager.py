# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import find_link

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import \
    COMPUTE_POLICY_NAME_PREFIX
from container_service_extension.cloudapi.constants import EntityType
from container_service_extension.cloudapi.constants import RelationType
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.pyvcloud_utils import get_vdc
from container_service_extension.shared_constants import RequestMethod


class ComputePolicyManager:
    """Manages creating, deleting, updating cloudapi compute policies.

    All policy names are prepended with CSE specific literal and restored to
    original names when returned back to the caller.
    """

    def __init__(self, vcd_uri, tenant_auth_token, verify_ssl,
                 api_version):
        """Initialize ComputePolicyManager Object.

        :param str vcd_uri: base_url to create client
        :param str tenant_auth_token: HTTP basic authentication token
        :param str api_version:
        :param bool verify_ssl: if True, verify SSL certificates of remote
        host, else ignore verification.
        """
        self._vcd_client = Client(uri=vcd_uri,
                                  api_version=api_version,
                                  verify_ssl_certs=verify_ssl)
        session = self._vcd_client.rehydrate_from_token(tenant_auth_token)
        link = find_link(session, RelationType.OPEN_API,
                         EntityType.APPLICATION_JSON)

        self.cloud_api_client = CloudApiClient(
            base_url=link.href,
            auth_token=tenant_auth_token,
            verify_ssl=verify_ssl)

    def list_policies(self):
        """Get all policies that are created by CSE.

        :return: list of CSE created policies
        :rtype: list of dict
        """
        policies = self.cloud_api_client.do_request(
            RequestMethod.GET, CloudApiResource.VDC_COMPUTE_POLICIES)
        cse_policies = []
        for policy in policies['values']:
            if policy['name'].startswith(COMPUTE_POLICY_NAME_PREFIX):
                policy['display_name'] = \
                    self._get_original_policy_name(policy['name'])
            else:
                policy['display_name'] = policy['name']
            cse_policies.append(policy)

        return cse_policies

    def get_policy(self, policy_name):
        """Get the compute policy information for the given policy name.

        :param str policy_name: name of the compute policy

        :return: policy details if found, else None
        :rtype: dict
        """
        for policy_dict in self.list_policies():
            if policy_dict.get('display_name') == policy_name:
                policy_dict['href'] = self._get_policy_href(policy_dict['id'])
                return policy_dict

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
        created_policy['display_name'] = self._get_original_policy_name(
            created_policy['name'])
        created_policy['href'] = self._get_policy_href(created_policy['id'])
        return created_policy

    def remove_policy(self, policy_name):
        """Remove the compute policy with the given name.

        :param str policy_name: name of the compute policy
        """
        policy_info = self.get_policy(policy_name)
        if policy_info:
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
        if policy_info and new_policy_info.get('name'):
            payload = {}
            payload['name'] = \
                self._get_cse_policy_name(new_policy_info['name'])
            if new_policy_info.get('description'):
                payload['description'] = new_policy_info['description']
            resource_url_relative_path = \
                f"{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_info['id']}"
            updated_policy = self.cloud_api_client.do_request(
                RequestMethod.PUT,
                resource_url_relative_path=resource_url_relative_path,
                payload=payload)
            updated_policy['display_name'] = \
                self._get_original_policy_name(updated_policy['name'])
            updated_policy['href'] = policy_info['href']
            return updated_policy

    def add_compute_policy_to_vdc(self, org_name, vdc_name, policy_href):
        """Add compute policy to the given vdc that is found in given org.

        :param str org_name: name of the organization to look for the vdc
        :param str vdc_name: name of the vdc to assign the policy
        :param policy_href: policy href that is created using cloudapi

        :return: an object containing VdcComputePolicyReferences XML element
        that refers to individual VdcComputePolicies.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        vdc = get_vdc(self._vcd_client, org_name=org_name, vdc_name=vdc_name,
                      is_admin_operation=True)
        return vdc.add_compute_policy(policy_href)

    def remove_compute_policy_from_vdc(self, org_name, vdc_name, policy_href):
        """Delete the compute policy from the vdc that belongs to given org.

        :param str org_name: name of the organization to look for the vdc
        :param str vdc_name: name of the vdc to assign the policy
        :param policy_href: policy href that is created using cloudapi

        :return: an object containing VdcComputePolicyReferences XML element
        that refers to individual VdcComputePolicies.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        vdc = get_vdc(self._vcd_client, org_name=org_name, vdc_name=vdc_name,
                      is_admin_operation=True)
        return vdc.remove_compute_policy(policy_href)

    def assign_compute_policy_to_vapp_template_vms(self,
                                                   org_name,
                                                   catalog_name,
                                                   catalog_item_name,
                                                   compute_policy_href):
        """Assign the compute policy to vms of given vapp template.

        :param str org_name: name of the organization that has the catalog
        :param str catalog_name: name of the catalog
        :param str catalog_item_name: name of the catalog item that has vms
        :param str compute_policy_href: compute policy to be removed

        :return: an object of type EntityType.TASK XML which represents
        the asynchronous task that is updating virtual application template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        org = get_org(self._vcd_client, org_name=org_name)
        return org.assign_compute_policy_to_vapp_template_vms(
            catalog_name, catalog_item_name, compute_policy_href)

    def remove_compute_policy_from_vapp_template_vms(self,
                                                     org_name,
                                                     catalog_name,
                                                     catalog_item_name,
                                                     compute_policy_href):
        """Remove the compute policy from vms of given vapp template.

        :param str org_name: name of the organization that has the catalog
        :param str catalog_name: name of the catalog
        :param str catalog_item_name: name of the catalog item that has vms
        :param str compute_policy_href: compute policy to be removed

        :return: an object of type EntityType.TASK XML which represents
        the asynchronous task that is updating virtual application template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        org = get_org(self._vcd_client, org_name=org_name)
        return org.remove_compute_policy_from_vapp_template_vms(
            catalog_name, catalog_item_name, compute_policy_href)

    def _get_cse_policy_name(self, policy_name):
        """Add cse specific prefix to the policy name.

        :param str policy_name: name of the compute policy

        :return: policy name unique to cse
        :rtype: str
        """
        return f"{COMPUTE_POLICY_NAME_PREFIX}{policy_name}"

    def _get_original_policy_name(self, policy_name):
        """Remove cse specific prefix from the given policy name.

        :param str policy_name: name of the policy

        :return: policy name after removing cse specific prefix
        :rtype: str
        """
        if policy_name and policy_name.startswith(COMPUTE_POLICY_NAME_PREFIX):
            return policy_name.replace(COMPUTE_POLICY_NAME_PREFIX, '', 1)
        return policy_name

    def _get_policy_href(self, policy_id):
        """Construct policy href from given policy id.

        :param str policy_id: policy id

        :return: policy href
        :rtype: str
        """
        return f"{self.cloud_api_client._versioned_url}{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_id}"  # noqa
