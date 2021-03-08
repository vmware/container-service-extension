# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.utils import retrieve_compute_policy_id_from_href
from pyvcloud.vcd.vm import VM
import requests

from container_service_extension.common.constants.shared_constants import PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.thread_utils as thread_utils
import container_service_extension.exception.exceptions as cse_exceptions
import container_service_extension.lib.cloudapi.constants as cloudapi_constants
import container_service_extension.logging.logger as logger

# cse compute policy prefix
CSE_COMPUTE_POLICY_PREFIX = 'cse----'
_SYSTEM_DEFAULT_COMPUTE_POLICY = 'System Default'
GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION = 35.0
PVDC_VM_POLICY_NAME = "PvdcVmPolicy"
VDC_VM_POLICY_NAME = "VdcVmPolicy"


class ComputePolicyManager:
    """Manages creating, deleting, updating cloudapi compute policies.

    Also provides an interface to assign/remove/list compute policies to/from
    vapp templates and org vdcs.

    These operations are supposed to be performed by only sytem administrators.

    All policy names are prepended with CSE specific literal and restored to
    original names when returned back to the caller.
    """

    def __init__(self, sysadmin_client: vcd_client.Client, log_wire=True):
        vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
        self._sysadmin_client: vcd_client.Client = sysadmin_client
        self._cloudapi_client = None
        self._session = self._sysadmin_client.get_vcloud_session()
        self._is_operation_supported = True

        try:
            wire_logger = logger.NULL_LOGGER
            if log_wire:
                wire_logger = logger.SERVER_CLOUDAPI_WIRE_LOGGER
            self._cloudapi_client = \
                vcd_utils.get_cloudapi_client_from_vcd_client(self._sysadmin_client, # noqa: E501
                                                              logger.SERVER_LOGGER, # noqa: E501
                                                              wire_logger)
            self._cloudapi_version = \
                cloudapi_constants.CloudApiVersion.VERSION_2_0_0
            if float(self._cloudapi_client.get_api_version()) < \
                    GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION:
                self._cloudapi_version = \
                    cloudapi_constants.CloudApiVersion.VERSION_1_0_0

            # Since the /cloudapi endpoint was added before the compute policy
            # endpoint. Mere presence of the /cloudapi uri is not enough, we
            # need to make sure that this cloud api client will be of actual
            # use to us.
            request_uri = f"{cloudapi_constants.CloudApiResource.VDC_COMPUTE_POLICIES}?"  \
                          f"{PaginationKey.PAGE_SIZE}=1"  # noqa: E501
            self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=self._cloudapi_version,
                resource_url_relative_path=request_uri) # noqa: E501
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
            self._is_operation_supported = False

    def get_all_pvdc_compute_policies(self, filters=None):
        """Get all pvdc compute policies in vCD.

        Returns a generator that when iterated over will yield all pvdc compute
        policies in VCD according to the filter if provided or else returns all
        the pvdc compute policies, making multiple requests when necessary.
        This is implemented with a generator because cloudapi paginates the
        'GET /pvdcComputePolicies' endpoint.

        :param dict filters: key and value pairs which represents a filter

        :return: Generator that yields all pvdc compute policies in vCD after
            filtering
        :rtype: Generator[Dict, None, None]
        """
        self._raise_error_if_not_supported()
        filter_string = utils.construct_filter_string(filters)
        cloudapiResource = cloudapi_constants.CloudApiResource
        page_num = 0
        while True:
            page_num += 1
            # without the &sortAsc parameter, vCD returns unpredictable results
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=self._cloudapi_version,
                resource_url_relative_path=f"{cloudapiResource.PVDC_COMPUTE_POLICIES}?{query_string}") # noqa: E501

            if len(response_body['values']) == 0:
                break
            for policy in response_body['values']:
                yield policy

    def get_all_vdc_compute_policies(self, filters=None):
        """Get all compute policies in vCD.

        Returns a generator that when iterated over will yield all compute
        policies in vCD, making multiple requests when necessary.
        This is implemented with a generator because cloudapi paginates
        the `GET /vdcComputePolicies` endpoint.

        :param dict filters: key and value pairs to filter the results

        :return: Generator that yields all compute policies in vCD
        :rtype: Generator[Dict, None, None]
        """
        self._raise_error_if_not_supported()
        filter_string = utils.construct_filter_string(filters)
        cloudapiResource = cloudapi_constants.CloudApiResource
        page_num = 0
        while True:
            page_num += 1
            # without the &sortAsc parameter, vCD returns unpredictable results
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            # without the &sortAsc parameter, vCD returns unpredictable results
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=self._cloudapi_version,
                resource_url_relative_path=f"{cloudapiResource.VDC_COMPUTE_POLICIES}?{query_string}") # noqa: E501

            if len(response_body['values']) == 0:
                break
            for policy in response_body['values']:
                yield policy

    def get_pvdc_compute_policy(self, policy_name):
        """Get the CSE created PVDC compute policy by name.

        :param str policy_name: name of the pvdc compute policy

        :return pvdc compute policy details
        :rtype: dict
        :raises: EntityNotFoundException if pvdc compute policy is not found
        """
        # NOTE if multiple pvdc compute policy exists, this function returns
        # the first one found.
        self._raise_error_if_not_supported()
        # CSE created policy will have a prefix
        filters = {'name': policy_name}
        for policy_dict in self.get_all_pvdc_compute_policies(filters=filters):
            if policy_dict.get('name') == policy_name:
                policy_dict['href'] = self._get_policy_href(policy_dict['id'],
                                                            is_pvdc_compute_policy=True) # noqa: E501
                return policy_dict

        raise EntityNotFoundException(f"Compute policy '{policy_name}'"
                                      f" does not exist.")

    def get_vdc_compute_policy(self, policy_name, is_placement_policy=False):
        """Get CSE created VDC compute policy by name.

        :param str policy_name: name of the compute policy
        :param boolean is_placement_policy: True if the VDC compute policy is a
            VDC placement policy

        :return: dictionary containing policy details
        :rtype: dict
        :raises: EntityNotFoundException: if compute policy is not found
        """
        # NOTE If multiple policies with the same name exist, this function
        # returns the first found.
        # 'System Default' is the only case where multiple compute
        # policies with the same name may exist.
        self._raise_error_if_not_supported()
        filters = \
            {
                # CSE created policy will have a prefix
                'name': policy_name,
                'isSizingOnly': str(not is_placement_policy).lower()
            }
        for policy_dict in self.get_all_vdc_compute_policies(filters=filters):
            if policy_dict.get('name') == policy_name:
                policy_dict['href'] = self._get_policy_href(policy_dict['id'])
                return policy_dict

        raise EntityNotFoundException(f"Compute policy '{policy_name}'"
                                      f" does not exist.")

    def add_pvdc_compute_policy(self, name, description):
        """Add PVDC compute policy with given name and description.

        :param str name: name of the PVDC compute policy
        :param str description: description for the PVDC compute policy

        :return created PVDC compute policy information
        :rtype dict
        :raises: HTTPError 400 Bad Request if policy already exists
        """
        self._raise_error_if_not_supported()
        self._raise_error_if_global_pvdc_compute_policy_not_supported()
        policy_info = {}
        policy_info['name'] = name
        policy_info['description'] = description
        resource = cloudapi_constants.CloudApiResource

        if self._cloudapi_version == \
                cloudapi_constants.CloudApiVersion.VERSION_2_0_0:
            policy_info['policyType'] = PVDC_VM_POLICY_NAME

        pvdc_policy = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=self._cloudapi_version,
            resource_url_relative_path=resource.PVDC_COMPUTE_POLICIES,
            payload=policy_info)
        pvdc_policy['href'] = self._get_policy_href(pvdc_policy['id'],
                                                    is_pvdc_compute_policy=True) # noqa: E501
        return pvdc_policy

    def delete_pvdc_compute_policy(self, policy_name):
        """Remove a pvdc compute policy created by CSE with given name.

        :param str policy_name: name of the pvdc compute policy

        :return dictionary containing response text
        :rtype: dict
        :raises: EntityNotFoundException: if compute policy is not found
        """
        self._raise_error_if_not_supported()
        policy_info = self.get_pvdc_compute_policy(policy_name)
        resource_url_relative_path = \
            f"{cloudapi_constants.CloudApiResource.PVDC_COMPUTE_POLICIES}/" \
            f"{policy_info['id']}"
        return self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=self._cloudapi_version,
            resource_url_relative_path=resource_url_relative_path)

    def add_vdc_compute_policy(self, policy_name,
                               description=None, pvdc_compute_policy_id=None):
        """Add vdc compute policy with the given name and description.

        :param str policy_name: name of the vdc compute policy
        :param str description: description about the vdc compute policy
        :param str pvdc_compute_policy_id: pvdc compute policy id associated
            with the pvdc compute policy (Provided if the policy is a
            placement policy)

        :return: created policy information
        :rtype: dict
        :raises: HTTPError 400 if policy already exists
        """
        self._raise_error_if_not_supported()
        policy_info = {}
        resource = cloudapi_constants.CloudApiResource
        policy_info['name'] = policy_name
        if self._cloudapi_version == \
                cloudapi_constants.CloudApiVersion.VERSION_2_0_0:
            policy_info['policyType'] = VDC_VM_POLICY_NAME
        if description:
            policy_info['description'] = description
        if pvdc_compute_policy_id:
            policy_info['pvdcComputePolicy'] = {
                'id': pvdc_compute_policy_id
            }
        created_policy = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=self._cloudapi_version,
            resource_url_relative_path=resource.VDC_COMPUTE_POLICIES,
            payload=policy_info)

        created_policy['href'] = self._get_policy_href(created_policy['id'])
        return created_policy

    def delete_vdc_compute_policy(self, policy_name,
                                  is_placement_policy=False):
        """Delete the vdc compute policy created by CSE with the given name.

        :param str policy_name: name of the compute policy
        :param boolean is_placement_policy: True if the compute policy is a
            VDC placement policy

        :return: dictionary containing response text
        :rtype: dict
        :raises: EntityNotFoundException: if compute policy is not found
        """
        self._raise_error_if_not_supported()
        policy_info = self.get_vdc_compute_policy(policy_name,
                                                  is_placement_policy=is_placement_policy)  # noqa: E501
        resource_url_relative_path = \
            f"{cloudapi_constants.CloudApiResource.VDC_COMPUTE_POLICIES}/" \
            f"{policy_info['id']}"
        return self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=self._cloudapi_version,
            resource_url_relative_path=resource_url_relative_path)

    def update_vdc_compute_policy(self, policy_name, new_policy_info,
                                  is_placement_policy=False):
        """Update the existing vdc compute policy with new policy information.

        :param str policy_name: existing policy name
        :param dict new_policy_info: updated policy information with name and
            optional description.
            Example: {"name": "new_name", "description": "my policy"}
        :parma boolean is_placement_policy: True if the VCD compute policy is a
            placment policy

        :return: updated policy information
        :rtype: dict
        :raises: EntityNotFoundException: if compute policy is not found
        """
        self._raise_error_if_not_supported()
        policy_info = self.get_vdc_compute_policy(policy_name,
                                                  is_placement_policy=is_placement_policy) # noqa: E501
        if new_policy_info.get('name'):
            payload = {}
            payload['name'] = new_policy_info['name']
            if self._cloudapi_version == \
                    cloudapi_constants.CloudApiVersion.VERSION_2_0_0:
                payload['policyType'] = VDC_VM_POLICY_NAME
            if 'description' in new_policy_info:
                payload['description'] = new_policy_info['description']
            resource_url_relative_path = \
                f"{cloudapi_constants.CloudApiResource.VDC_COMPUTE_POLICIES}" \
                f"/{policy_info['id']}"

            updated_policy = self._cloudapi_client.do_request(
                method=RequestMethod.PUT,
                cloudapi_version=self._cloudapi_version,
                resource_url_relative_path=resource_url_relative_path,
                payload=payload)

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
        self._raise_error_if_not_supported()
        vdc = vcd_utils.get_vdc(self._sysadmin_client, vdc_id=vdc_id,
                                is_admin_operation=True)
        return vdc.add_compute_policy(compute_policy_href)

    def list_vdc_placement_policies_on_vdc(self, vdc_id, filters=None):
        """List all placement policies assigned to a given vdc.

        :param str vdc_id: id of the vdc for which policies need to be
         retrieved.

        :return: Generator that yields all placement policies associated with
            the vdc
        :rtype: Generator[Dict, None, None]
        """
        if filters is None:
            filters = {}
        sizing_filter = {'isSizingOnly': 'false'}
        filters.update(sizing_filter)
        return self.list_compute_policies_on_vdc(vdc_id, filters=filters)

    def list_vdc_sizing_policies_on_vdc(self, vdc_id, filters=None):
        """List all sizing policies created by CSE and assigned to a given vdc.

        :param str vdc_id: id of the vdc for which policies need to be
         retrieved

        :return: Generator that yields all placement policeis associated with
            the vdc
        :rtpe: Generator[Dict, None, None]
        """
        if filters is None:
            filters = {}
        sizing_filter = {'isSizingOnly': 'true'}
        filters.update(sizing_filter)
        return self.list_compute_policies_on_vdc(vdc_id, filters=filters)

    def list_compute_policies_on_vdc(self, vdc_id, filters=None):
        """List all compute policies currently assigned to a given vdc.

        :param str vdc_id: id of the vdc for which policies need to be
            retrieved.
        :param dict filters: dictionary of key value pairs for filtering

        :return: Generator that yields all vdc compute policies associated with
            the VDC after filtering
        :rtype: Generator[Dict, None, None]
        """
        self._raise_error_if_not_supported()
        vdc_urn = self._generate_vdc_urn_from_id(vdc_id=vdc_id)
        relative_path = f"vdcs/{vdc_urn}/computePolicies"
        filter_string = utils.construct_filter_string(filters)
        page_num = 0
        while True:
            page_num += 1
            # without the &sortAsc parameter, vCD returns unpredictable results
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=self._cloudapi_version,
                resource_url_relative_path=f"{relative_path}?{query_string}") # noqa: E501

            if len(response_body['values']) == 0:
                break
            for cp in response_body['values']:
                policy = {
                    'name': cp.get('name'),
                    'href': self._get_policy_href(cp.get('id')),
                    'id': cp.get('id')
                }
                yield policy

    def assign_vdc_placement_policy_to_vapp_template_vms(self,
                                                         compute_policy_href,
                                                         org_name,
                                                         catalog_name,
                                                         catalog_item_name):
        """Assign the compute policy to vms of given vapp template.

        :param str compute_policy_href: compute policy to be removed
        :param str org_name: name of the organization that has the catalog
        :param str catalog_name: name of the catalog
        :param str catalog_item_name: name of the catalog item that has vms

        :return: an object of type vcd_client.TASK XML which represents
        the asynchronous task that is updating virtual application template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        self._raise_error_if_not_supported()
        org = vcd_utils.get_org(self._sysadmin_client, org_name=org_name)
        return org.assign_placement_policy_to_vapp_template_vms(
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name,
            placement_policy_href=compute_policy_href,
            placement_policy_final=True)

    def assign_vdc_sizing_policy_to_vapp_template_vms(self,
                                                      compute_policy_href,
                                                      org_name,
                                                      catalog_name,
                                                      catalog_item_name):
        """Assign the compute policy to vms of given vapp template.

        :param str compute_policy_href: compute policy to be removed
        :param str org_name: name of the organization that has the catalog
        :param str catalog_name: name of the catalog
        :param str catalog_item_name: name of the catalog item that has vms

        :return: an object of type vcd_client.TASK XML which represents
        the asynchronous task that is updating virtual application template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        self._raise_error_if_not_supported()
        org = vcd_utils.get_org(self._sysadmin_client, org_name=org_name)
        # TODO shift to org.assign_sizing_policy_to_vapp_template_vms
        return org.assign_compute_policy_to_vapp_template_vms(
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name,
            compute_policy_href=compute_policy_href)

    def remove_vdc_compute_policy_from_vapp_template_vms(self,
                                                         compute_policy_href,
                                                         org_name,
                                                         catalog_name,
                                                         catalog_item_name):
        """Remove the compute policy from vms of given vapp template.

        :param str compute_policy_href: compute policy to be removed.
        :param str org_name: name of the organization that has the catalog.
        :param str catalog_name: name of the catalog.
        :param str catalog_item_name: name of the catalog item that has vms.

        :return: an object of type vcd_client.TASK XML which represents
            the asynchronous task that is updating virtual application
            template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        self._raise_error_if_not_supported()
        org = vcd_utils.get_org(self._sysadmin_client, org_name=org_name)
        return org.remove_compute_policy_from_vapp_template_vms(
            catalog_name,
            catalog_item_name,
            compute_policy_href)

    def remove_all_vdc_compute_policies_from_vapp_template_vms(self,
                                                               org_name,
                                                               catalog_name,
                                                               catalog_item_name): # noqa: E501
        """Remove all compute policies from vms of given vapp template.

        :param str org_name: name of the organization that has the catalog.
        :param str catalog_name: name of the catalog.
        :param str catalog_item_name: name of the catalog item that has vms.

        :return: an object of type EntityType.TASK XML which represents
            the asynchronous task that is updating virtual application
            template.

        :rtype: lxml.objectify.ObjectifiedElement
        """
        self._raise_error_if_not_supported()
        org = vcd_utils.get_org(self._sysadmin_client, org_name=org_name)
        return org.remove_all_compute_policies_from_vapp_template_vms(
            catalog_name, catalog_item_name)

    def _raise_error_if_not_supported(self):
        """Raise exception if operation is not supported."""
        if not self._is_operation_supported:
            msg = "Cloudapi endpoint unavailable at current api version."
            logger.SERVER_LOGGER.error(msg)
            raise OperationNotSupportedException(msg)

    def _raise_error_if_global_pvdc_compute_policy_not_supported(self):
        """Raise exception if higher api version is needed."""
        api_version = float(self._cloudapi_client.get_api_version())
        if api_version < GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION: # noqa: E501
            msg = f"Recieved api version {api_version}." \
                  f" But atleast {GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION} is required" # noqa: E501
            logger.SERVER_LOGGER.debug(msg)
            raise cse_exceptions.GlobalPvdcComputePolicyNotSupported(msg)

    def _get_policy_href(self, policy_id, is_pvdc_compute_policy=False):
        """Construct policy href from given policy id.

        :param str policy_id: policy id
        :param boolean is_pvdc_compute_policy: True if policy is a PVDC compute
            policy

        :return: policy href
        :rtype: str
        """
        href_prefix = f"{self._cloudapi_client.get_base_url()}" \
                      f"{self._cloudapi_version}/"
        cloudApiResource = cloudapi_constants.CloudApiResource
        if is_pvdc_compute_policy:
            return f"{href_prefix}" \
                   f"{cloudApiResource.PVDC_COMPUTE_POLICIES}/" \
                   f"{policy_id}"
        return f"{href_prefix}" \
               f"{cloudApiResource.VDC_COMPUTE_POLICIES}/" \
               f"{policy_id}"

    def _generate_vdc_urn_from_id(self, vdc_id):
        """Construct VDC URN from VDC ID.

        :param str vdc_id: VDC id

        :return: URN of the format - urn:vcloud:vdc:[VDC_ID]
        :rtype: str
        """
        prefix = f"{cloudapi_constants.CLOUDAPI_URN_PREFIX}:vdc"
        if prefix in vdc_id:
            return vdc_id
        return f"{prefix}:{vdc_id}"

    def _get_vm_placement_policy_id(self, vm) -> str:
        """Obtain VM's placement policy id if present.

        :param lxml.objectify.ObjectifiedElement vm: VM object
        :return: placement policy id of the vm
        :rtype: str
        """
        if hasattr(vm, 'ComputePolicy') and \
            hasattr(vm.ComputePolicy, 'VmPlacementPolicy') and \
                vm.ComputePolicy.VmPlacementPolicy.get('id'):
            return vm.ComputePolicy.VmPlacementPolicy.get('id')

    def _get_vm_sizing_policy_id(self, vm) -> str:
        """Obtain VM's sizing policy id if present.

        :param lxml.objectify.ObjectifiedElement vm: VM object
        :return: sizing policy id of the vm
        :rtype: str
        """
        if hasattr(vm, 'ComputePolicy') and \
            hasattr(vm.ComputePolicy, 'VmSizingPolicy') and \
                vm.ComputePolicy.VmSizingPolicy.get('id'):
            return vm.ComputePolicy.VmSizingPolicy.get('id')

    def remove_vdc_compute_policy_from_vdc(self, # noqa: E501
                                           ovdc_id,
                                           compute_policy_href,
                                           force=False): # noqa: E501
        """Delete the compute policy from the specified vdc.

        :param str ovdc_id: id of the vdc to assign the policy
        :param compute_policy_href: policy href to remove
        :param bool force: If True, will set affected
            VMs' compute policy to 'System Default'

        :return: dictionary containing 'task_href'.
        """
        vdc = vcd_utils.get_vdc(self._sysadmin_client, vdc_id=ovdc_id)

        # TODO the following org will be associated with 'System' org.
        # task created should be associated with the corresponding org of the
        # vdc object.
        org = vcd_utils.get_org(self._sysadmin_client)
        org.reload()
        user_name = self._session.get('user')
        user_href = org.get_user(user_name).get('href')

        task = Task(self._sysadmin_client)
        task_resource = task.update(
            status=vcd_client.TaskStatus.RUNNING.value,
            namespace='vcloud.cse',
            operation=f"Removing compute policy (href: {compute_policy_href})"
                      f" from org VDC (vdc id: {ovdc_id})",
            operation_name='Remove org VDC compute policy',
            details='',
            progress=None,
            owner_href=vdc.href,
            owner_name=vdc.name,
            owner_type=vcd_client.EntityType.VDC.value,
            user_href=user_href,
            user_name=user_name,
            org_href=org.href)

        task_href = task_resource.get('href')
        self._remove_compute_policy_from_vdc_async(
            ovdc_id=ovdc_id,
            compute_policy_href=compute_policy_href,
            task_resource=task_resource,
            force=force)

        return {
            'task_href': task_href
        }

    @thread_utils.run_async
    def _remove_compute_policy_from_vdc_async(self, *args,
                                              ovdc_id,
                                              compute_policy_href,
                                              task_resource,
                                              force=False):
        vdc = vcd_utils.get_vdc(self._sysadmin_client, vdc_id=ovdc_id,
                                is_admin_operation=True)
        task_href = task_resource.get('href')
        user_href = task_resource.User.get('href')
        org_href = task_resource.Organization.get('href')
        task = Task(client=self._sysadmin_client)
        try:
            self.remove_compute_policy_from_vdc_sync(
                vdc=vdc,
                compute_policy_href=compute_policy_href,
                task_resource=task_resource,
                force=force)

            task.update(
                status=vcd_client.TaskStatus.SUCCESS.value,
                namespace='vcloud.cse',
                operation=f"Removed compute policy (href: "
                          f"{compute_policy_href}) from org VDC '{vdc.name}'",  # noqa: E501
                operation_name='Updating VDC',
                details='',
                progress=None,
                owner_href=vdc.href,
                owner_name=vdc.name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=self._session.get('user'),
                task_href=task_href,
                org_href=org_href,
            )
        except Exception as err:
            msg = f'Failed to remove compute policy: {compute_policy_href} ' \
                  f'from the OVDC: {vdc.name}'
            logger.SERVER_LOGGER.error(msg)# noqa: E501
            task.update(
                status=vcd_client.TaskStatus.ERROR.value,
                namespace='vcloud.cse',
                operation=msg,
                operation_name='Remove org VDC compute policy',
                details='',
                progress=None,
                owner_href=vdc.href,
                owner_name=vdc.name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=self._session.get('user'),
                task_href=task_href,
                org_href=org_href,
                error_message=f"{err}",
                stack_trace='')

    def remove_compute_policy_from_vdc_sync(self,
                                            vdc, compute_policy_href,
                                            force=False,
                                            is_placement_policy=False,
                                            task_resource=None):
        """Remove compute policy from vdc.

        This method makes use of an umbrella task which can be used for
        tracking progress. If the umbrella task is not specified, it is
        created.

        :param pyvcloud.vcd.vdc.VDC vdc: VDC object
        :param str compute_policy_href: href of the compute policy to remove
        :param bool force: Force remove compute policy from vms in the VDC
            as well
        :param lxml.objectify.Element task_resource: Task resource for
            the umbrella task
        """
        user_name = self._session.get('user')

        task = Task(self._sysadmin_client)
        task_href = None
        is_umbrella_task = task_resource is not None
        # Create a task if not umbrella task
        if not is_umbrella_task:
            # TODO the following org will be associated with 'System' org.
            # task created should be associated with the corresponding org of
            # the vdc object.
            org = vcd_utils.get_org(self._sysadmin_client)
            org.reload()
            user_href = org.get_user(user_name).get('href')
            org_href = org.href
            task_resource = task.update(
                status=vcd_client.TaskStatus.RUNNING.value,
                namespace='vcloud.cse',
                operation=f"Removing compute policy (href: {compute_policy_href})" # noqa: E501
                          f" from org VDC (vdc id: {vdc.name})",
                operation_name='Remove org VDC compute policy',
                details='',
                progress=None,
                owner_href=vdc.href,
                owner_name=vdc.name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=user_name,
                org_href=org.href)
        else:
            user_href = task_resource.User.get('href')
            org_href = task_resource.Organization.get('href')

        task_href = task_resource.get('href')

        try:
            # remove the compute policy from VMs if force is True
            if force:
                compute_policy_id = retrieve_compute_policy_id_from_href(compute_policy_href) # noqa: E501
                vdc_id = vcd_utils.extract_id(vdc.get_resource().get('id'))
                vapps = vcd_utils.get_all_vapps_in_ovdc(
                    client=self._sysadmin_client,
                    ovdc_id=vdc_id)
                target_vms = []
                system_default_href = None
                operation_msg = None
                for cp_dict in self.list_compute_policies_on_vdc(vdc_id):
                    if cp_dict['name'] == _SYSTEM_DEFAULT_COMPUTE_POLICY:
                        system_default_href = cp_dict['href']
                        break
                if is_placement_policy:
                    for vapp in vapps:
                        target_vms += \
                            [vm for vm in vapp.get_all_vms()
                                if self._get_vm_placement_policy_id(vm) == compute_policy_id] # noqa: E501
                    vm_names = [vm.get('name') for vm in target_vms]
                    operation_msg = f"Removing placement policy from " \
                                    f"{len(vm_names)} VMs. " \
                                    f"Affected VMs: {vm_names}"
                else:
                    for vapp in vapps:
                        target_vms += \
                            [vm for vm in vapp.get_all_vms()
                                if self._get_vm_sizing_policy_id(vm) == compute_policy_id] # noqa: E501
                    vm_names = [vm.get('name') for vm in target_vms]
                    operation_msg = "Setting sizing policy to " \
                                    f"'{_SYSTEM_DEFAULT_COMPUTE_POLICY}' on " \
                                    f"{len(vm_names)} VMs. " \
                                    f"Affected VMs: {vm_names}"

                task.update(
                    status=vcd_client.TaskStatus.RUNNING.value,
                    namespace='vcloud.cse',
                    operation=operation_msg,
                    operation_name='Remove org VDC compute policy',
                    details='',
                    progress=None,
                    owner_href=vdc.href,
                    owner_name=vdc.name,
                    owner_type=vcd_client.EntityType.VDC.value,
                    user_href=user_href,
                    user_name=user_name,
                    task_href=task_href,
                    org_href=org_href)

                task_monitor = self._sysadmin_client.get_task_monitor()
                for vm_resource in target_vms:
                    vm = VM(self._sysadmin_client,
                            href=vm_resource.get('href'))
                    _task = None
                    operation_msg = None
                    if is_placement_policy:
                        if hasattr(vm_resource, 'ComputePolicy') and \
                                not hasattr(vm_resource.ComputePolicy, 'VmSizingPolicy'):  # noqa: E501
                            # Updating sizing policy for the VM
                            _task = vm.update_compute_policy(
                                compute_policy_href=system_default_href)
                            operation_msg = \
                                "Setting compute policy to " \
                                f"'{_SYSTEM_DEFAULT_COMPUTE_POLICY}' "\
                                f"on VM '{vm_resource.get('name')}'"
                            task.update(
                                status=vcd_client.TaskStatus.RUNNING.value,
                                namespace='vcloud.cse',
                                operation=operation_msg,
                                operation_name=f'Setting sizing policy to {_SYSTEM_DEFAULT_COMPUTE_POLICY}',  # noqa: E501
                                details='',
                                progress=None,
                                owner_href=vdc.href,
                                owner_name=vdc.name,
                                owner_type=vcd_client.EntityType.VDC.value,
                                user_href=user_href,
                                user_name=user_name,
                                task_href=task_href,
                                org_href=org_href)
                            task_monitor.wait_for_success(_task)
                        _task = vm.remove_placement_policy()
                        operation_msg = "Removing placement policy on VM " \
                                        f"'{vm_resource.get('name')}'"
                        task.update(
                            status=vcd_client.TaskStatus.RUNNING.value,
                            namespace='vcloud.cse',
                            operation=operation_msg,
                            operation_name='Remove org VDC compute policy',
                            details='',
                            progress=None,
                            owner_href=vdc.href,
                            owner_name=vdc.name,
                            owner_type=vcd_client.EntityType.VDC.value,
                            user_href=user_href,
                            user_name=user_name,
                            task_href=task_href,
                            org_href=org_href)
                        task_monitor.wait_for_success(_task)
                    else:
                        _task = vm.update_compute_policy(
                            compute_policy_href=system_default_href)
                        operation_msg = "Setting sizing policy to " \
                                        f"'{_SYSTEM_DEFAULT_COMPUTE_POLICY}' "\
                                        f"on VM '{vm_resource.get('name')}'"
                        task.update(
                            status=vcd_client.TaskStatus.RUNNING.value,
                            namespace='vcloud.cse',
                            operation=operation_msg,
                            operation_name='Remove org VDC compute policy',
                            details='',
                            progress=None,
                            owner_href=vdc.href,
                            owner_name=vdc.name,
                            owner_type=vcd_client.EntityType.VDC.value,
                            user_href=user_href,
                            user_name=user_name,
                            task_href=task_href,
                            org_href=org_href)
                        task_monitor.wait_for_success(_task)

            final_status = vcd_client.TaskStatus.RUNNING.value \
                if is_umbrella_task else vcd_client.TaskStatus.SUCCESS.value
            task.update(
                status=final_status,
                namespace='vcloud.cse',
                operation=f"Removing compute policy (href:"
                          f"{compute_policy_href}) from org VDC '{vdc.name}'",
                operation_name='Remove org VDC compute policy',
                details='',
                progress=None,
                owner_href=vdc.href,
                owner_name=vdc.name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=user_name,
                task_href=task_href,
                org_href=org_href)

            vdc.remove_compute_policy(compute_policy_href)
        except Exception as err:
            logger.SERVER_LOGGER.error(err, exc_info=True)
            # Set task to error if not an umbrella task
            if not is_umbrella_task:
                msg = 'Failed to remove compute policy: ' \
                      f'{compute_policy_href} from the OVDC: {vdc.name}'
                task.update(
                    status=vcd_client.TaskStatus.ERROR.value,
                    namespace='vcloud.cse',
                    operation=msg,
                    operation_name='Remove org VDC compute policy',
                    details='',
                    progress=None,
                    owner_href=vdc.href,
                    owner_name=vdc.name,
                    owner_type=vcd_client.EntityType.VDC.value,
                    user_href=user_href,
                    user_name=self._session.get('user'),
                    task_href=task_href,
                    org_href=org_href,
                    error_message=f"{err}",
                    stack_trace='')
            raise err


# cse utility methods
def get_cse_policy_display_name(policy_name):
    """Remove cse specific prefix from the given policy name.

    :param str policy_name: name of the policy

    :return: policy name after removing cse specific prefix
    :rtype: str
    """
    if policy_name and \
            policy_name.startswith(CSE_COMPUTE_POLICY_PREFIX):
        return policy_name.replace(CSE_COMPUTE_POLICY_PREFIX, '', 1)
    return policy_name


def get_cse_policy_name(policy_name):
    """Add a prefix to the compute policy name."""
    return f"{CSE_COMPUTE_POLICY_PREFIX}{policy_name}"


def get_cse_pvdc_compute_policy(cpm: ComputePolicyManager,
                                unprefixed_policy_name: str):
    policy_name = get_cse_policy_name(unprefixed_policy_name)
    policy = cpm.get_pvdc_compute_policy(policy_name)
    policy['display_name'] = get_cse_policy_display_name(policy['name'])
    return policy


def add_cse_pvdc_compute_policy(cpm: ComputePolicyManager,
                                unprefixed_policy_name: str,
                                policy_description: str):
    policy_name = get_cse_policy_name(unprefixed_policy_name)
    created_policy = cpm.add_pvdc_compute_policy(policy_name, policy_description)  # noqa: E501
    created_policy['display_name'] = \
        get_cse_policy_display_name(created_policy['name'])
    return created_policy


def add_cse_vdc_compute_policy(cpm: ComputePolicyManager,
                               unprefixed_policy_name: str,
                               policy_description: str = None,
                               pvdc_compute_policy_id: str = None):
    policy_name = get_cse_policy_name(unprefixed_policy_name)
    created_policy = cpm.add_vdc_compute_policy(
        policy_name,
        description=policy_description,
        pvdc_compute_policy_id=pvdc_compute_policy_id)
    created_policy['display_name'] = \
        get_cse_policy_display_name(created_policy['name'])
    return created_policy


def get_cse_vdc_compute_policy(cpm: ComputePolicyManager,
                               unprefixed_policy_name: str,
                               is_placement_policy: bool = False):
    policy_name = get_cse_policy_name(unprefixed_policy_name)
    policy = cpm.get_vdc_compute_policy(policy_name, is_placement_policy=is_placement_policy)  # noqa: E501
    policy['display_name'] = get_cse_policy_display_name(policy['name'])
    return policy


def delete_cse_vdc_compute_policy(cpm: ComputePolicyManager,
                                  unprefixed_policy_name: str,
                                  is_placement_policy: bool = False):
    policy_name = get_cse_policy_name(unprefixed_policy_name)
    return cpm.delete_vdc_compute_policy(policy_name, is_placement_policy=is_placement_policy)  # noqa: E501


def list_cse_sizing_policies_on_vdc(cpm: ComputePolicyManager, vdc_id: str):
    cse_policy_name_filter = \
        {'name': f'{CSE_COMPUTE_POLICY_PREFIX}*'}
    policy_list = list(cpm.list_vdc_sizing_policies_on_vdc(vdc_id, filters=cse_policy_name_filter))  # noqa: E501
    for policy in policy_list:
        policy['display_name'] = get_cse_policy_display_name(policy['name'])
    return policy_list


def list_cse_placement_policies_on_vdc(cpm: ComputePolicyManager, vdc_id: str):
    cse_policy_name_filter = \
        {'name': f'{CSE_COMPUTE_POLICY_PREFIX}*'}
    policy_list = list(cpm.list_vdc_placement_policies_on_vdc(vdc_id, filters=cse_policy_name_filter))  # noqa: E501
    for policy in policy_list:
        policy['display_name'] = get_cse_policy_display_name(policy['name'])
    return policy_list
