# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import find_link
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import MissingLinkException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.utils import retrieve_compute_policy_id_from_href
from pyvcloud.vcd.vm import VM

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import COMPUTE_POLICY_NAME_PREFIX # noqa: E501
from container_service_extension.cloudapi.constants import EntityType
from container_service_extension.cloudapi.constants import RelationType
import container_service_extension.pyvcloud_utils as pyvcd_utils
from container_service_extension.shared_constants import RequestMethod

_SYSTEM_DEFAULT_COMPUTE_POLICY = 'System Default'


class ComputePolicyManager:
    """Manages creating, deleting, updating cloudapi compute policies.

    Also provides an interface to assign/remove/list compute policies to/from
    vapp templates and org vdcs.

    These operations are supposed to be performed by only sytem administrators.

    All policy names are prepended with CSE specific literal and restored to
    original names when returned back to the caller.
    """

    def __init__(self, client):
        """Initialize ComputePolicyManager Object.

        :param pyvcloud.vcd.client client:

        :raises: OperationNotSupportedException: If cloudapi endpoint is not
            found in session.
        :raises: ValueError: If non sys admin client is passed during
            initialization.
        """
        if not client.is_sysadmin():
            raise ValueError("Only Sys admin clients should be used to "
                             "initialize ComputePolicyManager.")

        self._vcd_client = client
        # TODO: pyvcloud should expose methods to grab the session and token
        # from a client object.
        auth_token = \
            self._vcd_client._session.headers['x-vcloud-authorization']
        # pyvcloud doesn't store the vCD session response in client. So we need
        # to get it from vCD.
        session = self._vcd_client.rehydrate_from_token(auth_token)
        # Ideally this information should be fetched from
        # client._session_endpoints. However pyvcloud client doesn't store
        # the cloudapi link, so we have to find it manually.
        try:
            link = find_link(session, RelationType.OPEN_API,
                             EntityType.APPLICATION_JSON)
        except MissingLinkException:
            raise OperationNotSupportedException(
                "Cloudapi endpoint unavailable at current api version.")

        self._cloudapi_client = CloudApiClient(
            base_url=link.href,
            auth_token=auth_token,
            verify_ssl=self._vcd_client._verify_ssl_certs)

    def list_policies(self):
        """Get all policies that are created by CSE.

        :return: list of CSE created policies
        :rtype: list of dict
        """
        policies = self._cloudapi_client.do_request(
            RequestMethod.GET, CloudApiResource.VDC_COMPUTE_POLICIES)
        cse_policies = []
        for policy in policies['values']:
            if policy['name'].startswith(COMPUTE_POLICY_NAME_PREFIX):
                policy['display_name'] = \
                    self._get_policy_display_name(policy['name'])
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
        # TODO there can be multiple policies with the same name
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
        created_policy = self._cloudapi_client.do_request(
            RequestMethod.POST,
            resource_url_relative_path=CloudApiResource.VDC_COMPUTE_POLICIES,
            payload=policy_info)
        created_policy['display_name'] = self._get_policy_display_name(
            created_policy['name'])
        created_policy['href'] = self._get_policy_href(created_policy['id'])
        return created_policy

    def delete_policy(self, policy_name):
        """Delete the compute policy with the given name.

        :param str policy_name: name of the compute policy
        """
        policy_info = self.get_policy(policy_name)
        if policy_info:
            resource_url_relative_path = \
                f"{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_info['id']}"
            return self._cloudapi_client.do_request(
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
            updated_policy = self._cloudapi_client.do_request(
                RequestMethod.PUT,
                resource_url_relative_path=resource_url_relative_path,
                payload=payload)
            updated_policy['display_name'] = \
                self._get_policy_display_name(updated_policy['name'])
            updated_policy['href'] = policy_info['href']
            return updated_policy

    def add_compute_policy_to_vdc(self, vdc_id, compute_policy_href):
        """Add compute policy to the given vdc.

        :param str vdc_id: id of the vdc to assign the policy
        :param compute_policy_href: policy href that is created using cloudapi

        :return: an object containing VdcComputePolicyReferences XML element
        that refers to individual VdcComputePolicies.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        vdc = pyvcd_utils.get_vdc(self._vcd_client,
                                  vdc_id=vdc_id,
                                  is_admin_operation=True)
        return vdc.add_compute_policy(compute_policy_href)

    def list_compute_policies_on_vdc(self, vdc_id):
        """List compute policy currently assigned to a given vdc.

        :param str vdc_id: id of the vdc for which policies need to be
            retrieved.

        :return: A list of dictionaries with the keys 'name', 'href', and 'id'
        :rtype: List
        """
        vdc = pyvcd_utils.get_vdc(self._vcd_client,
                                  vdc_id=vdc_id,
                                  is_admin_operation=True)

        result = []
        cp_list = vdc.list_compute_policies()
        for cp in cp_list:
            result.append({
                'name': self._get_policy_display_name(cp.get('name')),
                'href': cp.get('href'),
                'id': cp.get('id')
            })

        return result

    def remove_compute_policy_from_vdc(self, vdc_id, compute_policy_href,
                                       remove_compute_policy_from_vms=False):
        """Delete the compute policy from the specified vdc.

        :param str vdc_id: id of the vdc to assign the policy
        :param compute_policy_href: policy href that is created using cloudapi
        :param bool remove_compute_policy_from_vms: If True, will set affected
            VMs' compute policy to 'System Default'

        :return: an object containing VdcComputePolicyReferences XML element
        that refers to individual VdcComputePolicies.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        if remove_compute_policy_from_vms:
            cp_list = self.list_compute_policies_on_vdc(vdc_id)
            system_default_href = None
            system_default_id = None
            for cp_dict in cp_list:
                if cp_dict['name'] == _SYSTEM_DEFAULT_COMPUTE_POLICY:
                    system_default_href = cp_dict['href']
                    system_default_id = cp_dict['id']
            if system_default_href is None:
                raise EntityNotFoundException(
                    f"Error: {_SYSTEM_DEFAULT_COMPUTE_POLICY} "
                    f"compute policy not found.")

            compute_policy_id = retrieve_compute_policy_id_from_href(compute_policy_href) # noqa: E501
            vapps = pyvcd_utils.get_all_vapps_in_ovdc(self._vcd_client, vdc_id)
            for vapp in vapps:
                vm_resources = vapp.get_all_vms()
                for vm_resource in vm_resources:
                    if vm_resource.VdcComputePolicy.get('id') == compute_policy_id: # noqa: E501
                        vm = VM(self._vcd_client, resource=vm_resource)
                        task = vm.update_compute_policy(system_default_href,
                                                        system_default_id)
                        self._vcd_client.get_task_monitor().wait_for_status(task) # noqa: E501

        vdc = pyvcd_utils.get_vdc(self._vcd_client,
                                  vdc_id=vdc_id,
                                  is_admin_operation=True)
        return vdc.remove_compute_policy(compute_policy_href)

    def assign_compute_policy_to_vapp_template_vms(self,
                                                   compute_policy_href,
                                                   org_name,
                                                   catalog_name,
                                                   catalog_item_name):
        """Assign the compute policy to vms of given vapp template.

        :param str compute_policy_href: compute policy to be removed
        :param str org_name: name of the organization that has the catalog
        :param str catalog_name: name of the catalog
        :param str catalog_item_name: name of the catalog item that has vms

        :return: an object of type EntityType.TASK XML which represents
        the asynchronous task that is updating virtual application template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        org = pyvcd_utils.get_org(self._vcd_client, org_name=org_name)
        return org.assign_compute_policy_to_vapp_template_vms(
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name,
            compute_policy_href=compute_policy_href)

    def remove_compute_policy_from_vapp_template_vms(self,
                                                     compute_policy_href,
                                                     org_name,
                                                     catalog_name,
                                                     catalog_item_name):
        """Remove the compute policy from vms of given vapp template.

        :param str compute_policy_href: compute policy to be removed.
        :param str org_name: name of the organization that has the catalog.
        :param str catalog_name: name of the catalog.
        :param str catalog_item_name: name of the catalog item that has vms.

        :return: an object of type EntityType.TASK XML which represents
            the asynchronous task that is updating virtual application
            template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        org = pyvcd_utils.get_org(self._vcd_client, org_name=org_name)
        return org.remove_compute_policy_from_vapp_template_vms(
            catalog_name,
            catalog_item_name,
            compute_policy_href)

    def remove_all_compute_policies_from_vapp_template_vms(self,
                                                           org_name,
                                                           catalog_name,
                                                           catalog_item_name):
        """Remove all compute policies from vms of given vapp template.

        :param str org_name: name of the organization that has the catalog.
        :param str catalog_name: name of the catalog.
        :param str catalog_item_name: name of the catalog item that has vms.

        :return: an object of type EntityType.TASK XML which represents
            the asynchronous task that is updating virtual application
            template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        org = pyvcd_utils.get_org(self._vcd_client, org_name=org_name)
        return org.remove_all_compute_policies_from_vapp_template_vms(
            catalog_name, catalog_item_name)

    def _get_cse_policy_name(self, policy_name):
        """Add cse specific prefix to the policy name.

        :param str policy_name: name of the compute policy

        :return: policy name unique to cse
        :rtype: str
        """
        return f"{COMPUTE_POLICY_NAME_PREFIX}{policy_name}"

    def _get_policy_display_name(self, policy_name):
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
        return f"{self._cloudapi_client.get_versioned_url()}{CloudApiResource.VDC_COMPUTE_POLICIES}/{policy_id}"  # noqa
