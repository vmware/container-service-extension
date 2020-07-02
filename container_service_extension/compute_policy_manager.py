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

import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.exceptions as cse_exceptions
import container_service_extension.logger as logger
import container_service_extension.operation_context as ctx
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.shared_constants import RequestMethod
import container_service_extension.utils as utils


_SYSTEM_DEFAULT_COMPUTE_POLICY = 'System Default'
GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION = 35.0


class ComputePolicyManager:
    """Manages creating, deleting, updating cloudapi compute policies.

    Also provides an interface to assign/remove/list compute policies to/from
    vapp templates and org vdcs.

    These operations are supposed to be performed by only sytem administrators.

    All policy names are prepended with CSE specific literal and restored to
    original names when returned back to the caller.
    """

    def __init__(self, sysadmin_client: vcd_client.Client, log_wire=True):
        vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
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
            # Since the /cloudapi endpoint was added before the compute policy
            # endpoint. Mere presence of the /cloudapi uri is not enough, we
            # need to make sure that this cloud api client will be of actual
            # use to us.
            self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{cloudapi_constants.CloudApiResource.VDC_COMPUTE_POLICIES}") # noqa: E501
        except requests.exceptions.HTTPError as err:
            logger.SERVER_LOGGER.error(err)
            self._is_operation_supported = False

    def get_all_pvdc_compute_policies(self, filters=None):
        """Get all pvdc compute policies in vCD.

        Note: This function returns PVDC compute policies
            not created by CSE as well.

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
        filter_string = None
        if filters:
            filter_string = ";".join([f"{key}=={value}" for (key, value) in filters.items()]) # noqa: E501
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
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{cloudapiResource.PVDC_COMPUTE_POLICIES}?{query_string}") # noqa: E501

            if len(response_body['values']) == 0:
                break
            for policy in response_body['values']:
                cp_name = policy['name']
                policy['display_name'] = self._get_policy_display_name(cp_name)
                yield policy

    def get_all_vdc_compute_policies(self, filters=None):
        """Get all compute policies in vCD.

        Note: This function also returns VDC compute policies not created
            by CSE as well.

        Returns a generator that when iterated over will yield all compute
        policies in vCD, making multiple requests when necessary.
        This is implemented with a generator because cloudapi paginates
        the `GET /vdcComputePolicies` endpoint.

        :param dict filters: key and value pairs to filter the results

        :return: Generator that yields all compute policies in vCD
        :rtype: Generator[Dict, None, None]
        """
        self._raise_error_if_not_supported()
        filter_string = None
        if filters:
            filter_string = ";".join([f"{key}=={value}" for (key, value) in filters.items()]) # noqa: E501
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
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{cloudapiResource.VDC_COMPUTE_POLICIES}?{query_string}") # noqa: E501

            if len(response_body['values']) == 0:
                break
            for policy in response_body['values']:
                cp_name = policy['name']
                policy['display_name'] = self._get_policy_display_name(cp_name)
                yield policy

    def get_pvdc_compute_policy(self, policy_name):
        """Get the CSE created PVDC compute policy by name.

        Note: This function can only be used to fetch PVDC compute policies
            created by CSE.

        :param str policy_name: name of the pvdc compute policy

        :return pvdc compute policy details
        :rtype: dict
        :raises: EntityNotFoundException if pvdc compute policy is not found
        """
        # NOTE if multiple pvdc compute policy exists, this function returns
        # the first one found.
        self._raise_error_if_not_supported()
        # CSE created policy will have a prefix
        filters = {'name': self._get_cse_policy_name(policy_name)}
        for policy_dict in self.get_all_pvdc_compute_policies(filters=filters):
            if policy_dict.get('display_name') == policy_name:
                policy_dict['href'] = self._get_policy_href(policy_dict['id'],
                                                            is_pvdc_compute_policy=True) # noqa: E501
                return policy_dict

        raise EntityNotFoundException(f"Compute policy '{policy_name}'"
                                      f" does not exist.")

    def get_vdc_compute_policy(self, policy_name, is_placement_policy=False):
        """Get CSE created VDC compute policy by name.

        Note: This function can only be used to fetch VDC compute policies
            created by CSE.

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
                'name': self._get_cse_policy_name(policy_name),
                'isSizingOnly': str(not is_placement_policy).lower()
            }
        for policy_dict in self.get_all_vdc_compute_policies(filters=filters):
            if policy_dict.get('display_name') == policy_name:
                policy_dict['href'] = self._get_policy_href(policy_dict['id'])
                return policy_dict

        raise EntityNotFoundException(f"Compute policy '{policy_name}'"
                                      f" does not exist.")

    def add_pvdc_compute_policy(self, name, description):
        """Add PVDC compute policy with given name and description.

        Note: The created PVDC compute policy will have a CSE specific prefix.

        :param str name: name of the PVDC compute policy
        :param str description: description for the PVDC compute policy

        :return created PVDC compute policy information
        :rtype dict
        :raises: HTTPError 400 Bad Request if policy already exists
        """
        self._raise_error_if_not_supported()
        self._raise_error_if_global_pvdc_compute_policy_not_supported()
        policy_info = {}
        # add cse related prefix to the policy name
        policy_info['name'] = self._get_cse_policy_name(name)
        policy_info['description'] = description
        resource = cloudapi_constants.CloudApiResource

        pvdc_policy = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=resource.PVDC_COMPUTE_POLICIES,
            payload=policy_info)
        pvdc_policy['display_name'] = self._get_policy_display_name(pvdc_policy['name']) # noqa: E501
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
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=resource_url_relative_path)

    def add_vdc_compute_policy(self, policy_name,
                               description=None, pvdc_compute_policy_id=None):
        """Add vdc compute policy with the given name and description.

        Note: The created VDC compute policy will have a CSE related prefix.

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
        # add cse related prefix to the policy name
        policy_info['name'] = self._get_cse_policy_name(policy_name)
        if description:
            policy_info['description'] = description
        if pvdc_compute_policy_id:
            policy_info['pvdcComputePolicy'] = {
                'id': pvdc_compute_policy_id
            }

        created_policy = self._cloudapi_client.do_request(
            method=RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=resource.VDC_COMPUTE_POLICIES,
            payload=policy_info)

        created_policy['display_name'] = self._get_policy_display_name(created_policy['name']) # noqa: E501
        created_policy['href'] = self._get_policy_href(created_policy['id'])
        return created_policy

    def delete_vdc_compute_policy(self, policy_name,
                                  is_placement_policy=False):
        """Delete the vdc compute policy created by CSE with the given name.

        Note: This function can only be used to fetch PVDC compute policies
            created by CSE.

        :param str policy_name: name of the compute policy
        :param boolean is_placement_policy: True if the compute policy is a
            VDC placement policy

        :return: dictionary containing response text
        :rtype: dict
        :raises: EntityNotFoundException: if compute policy is not found
        """
        self._raise_error_if_not_supported()
        policy_info = self.get_vdc_compute_policy(policy_name,
                                                  is_placement_policy=is_placement_policy) # noqa: E501
        resource_url_relative_path = \
            f"{cloudapi_constants.CloudApiResource.VDC_COMPUTE_POLICIES}/" \
            f"{policy_info['id']}"
        return self._cloudapi_client.do_request(
            method=RequestMethod.DELETE,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=resource_url_relative_path)

    def update_vdc_compute_policy(self, policy_name, new_policy_info,
                                  is_placement_policy=False):
        """Update the existing vdc compute policy with new policy information.

        Note: This function can only be used to update VDC compute policies
            created by CSE.

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
            # add cse related prefix to the policy name
            payload['name'] = \
                self._get_cse_policy_name(new_policy_info['name'])
            if 'description' in new_policy_info:
                payload['description'] = new_policy_info['description']
            resource_url_relative_path = \
                f"{cloudapi_constants.CloudApiResource.VDC_COMPUTE_POLICIES}" \
                f"/{policy_info['id']}"

            updated_policy = self._cloudapi_client.do_request(
                method=RequestMethod.PUT,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=resource_url_relative_path,
                payload=payload)

            updated_policy['display_name'] = \
                self._get_policy_display_name(updated_policy['name'])
            updated_policy['href'] = policy_info['href']
            return updated_policy

    def add_compute_policy_to_vdc(self, vdc_id, compute_policy_href):
        """Add compute policy to the given vdc.

        Note: The VDC compute policy need not be created by CSE.

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

    def list_vdc_placement_policies_on_vdc(self, vdc_id):
        """List all placement policies assigned to a given vdc.

        Note: This function returns only the policies which are created by CSE.

        :param str vdc_id: id of the vdc for which policies need to be
         retrieved.

        :return: Generator that yields all placement policies associated with
            the vdc
        :rtype: Generator[Dict, None, None]
        """
        # CSE created compute policies will be prefixed
        filters = {
            'isSizingOnly': 'false',
            'name': f'{cloudapi_constants.CSE_COMPUTE_POLICY_PREFIX}*'
        }
        self.list_compute_policies_on_vdc(vdc_id, filters=filters)

    def list_vdc_sizing_policies_on_vdc(self, vdc_id):
        """List all sizing policies created by CSE and assigned to a given vdc.

        Note: This function returns only the policies which are created by CSE.

        :param str vdc_id: id of the vdc for which policies need to be
         retrieved

        :return: Generator that yields all placement policeis associated with
            the vdc
        :rtpe: Generator[Dict, None, None]
        """
        # CSE created compute policies will be prefixed
        filters = {
            'isSizingOnly': 'true',
            'name': f'{cloudapi_constants.CSE_COMPUTE_POLICY_PREFIX}*'
        }
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
        filter_string = ""
        if filters:
            filter_string = ";".join([f"{key}=={value}" for (key, value) in filters.items()]) # noqa: E501
        response_body = self._cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=relative_path)
        page_num = 0
        while True:
            page_num += 1
            # without the &sortAsc parameter, vCD returns unpredictable results
            query_string = f"page={page_num}&sortAsc=name"
            if filter_string:
                query_string = f"filter={filter_string}&{query_string}"
            response_body = self._cloudapi_client.do_request(
                method=RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=f"{relative_path}?{query_string}") # noqa: E501

            if len(response_body['values']) == 0:
                break
            for cp in response_body['values']:
                policy = {
                    'name': self._get_policy_display_name(cp.get('name')),
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

        Note: The VDC placement policy need not be created by CSE.

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
            placement_policy_href=compute_policy_href)

    def assign_vdc_sizing_policy_to_vapp_template_vms(self,
                                                      compute_policy_href,
                                                      org_name,
                                                      catalog_name,
                                                      catalog_item_name):
        """Assign the compute policy to vms of given vapp template.

        Note: The VDC sizing policy need not be created by CSE.

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

        Note: The VDC compute policy need not be created by CSE.

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
        """Railse exception if higher api version is needed."""
        api_version = float(self._cloudapi_client.get_api_version())
        if api_version < GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION: # noqa: E501
            msg = f"Recieved api version {api_version}." \
                  f" But atleast {GLOBAL_PVDC_COMPUTE_POLICY_MIN_VERSION} is required" # noqa: E501
            logger.SERVER_LOGGER.debug(msg)
            raise cse_exceptions.GlobalPvdcComputePolicyNotSupported(msg)

    def _get_cse_policy_name(self, policy_name):
        """Add cse specific prefix to the policy name.

        :param str policy_name: name of the compute policy

        :return: policy name unique to cse
        :rtype: str
        """
        return f"{cloudapi_constants.CSE_COMPUTE_POLICY_PREFIX}{policy_name}"

    def _get_policy_display_name(self, policy_name):
        """Remove cse specific prefix from the given policy name.

        :param str policy_name: name of the policy

        :return: policy name after removing cse specific prefix
        :rtype: str
        """
        if policy_name and \
           policy_name.startswith(cloudapi_constants.CSE_COMPUTE_POLICY_PREFIX): # noqa: E501
            return policy_name.replace(cloudapi_constants.CSE_COMPUTE_POLICY_PREFIX, '', 1) # noqa: E501
        return policy_name

    def _get_policy_href(self, policy_id, is_pvdc_compute_policy=False):
        """Construct policy href from given policy id.

        :param str policy_id: policy id
        :param boolean is_pvdc_compute_policy: True if policy is a PVDC compute
            policy

        :return: policy href
        :rtype: str
        """
        href_prefix = f"{self._cloudapi_client.get_base_url()}" \
                      f"{cloudapi_constants.CLOUDAPI_VERSION_1_0_0}/"
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
        return f"{cloudapi_constants.CLOUDAPI_URN_PREFIX}:vdc:{vdc_id}"

    def remove_vdc_compute_policy_from_vdc(self, op_ctx: ctx.OperationContext, # noqa: E501
                                           ovdc_id,
                                           compute_policy_href,
                                           remove_compute_policy_from_vms=False): # noqa: E501
        """Delete the compute policy from the specified vdc.

        Note: The VDC compute policy need not be created by CSE.

        :param op_ctx: request context of remove compute policy
            request
        :param str ovdc_id: id of the vdc to assign the policy
        :param compute_policy_href: policy href to remove
        :param bool remove_compute_policy_from_vms: If True, will set affected
            VMs' compute policy to 'System Default'

        :return: dictionary containing 'task_href'.
        """
        # TODO find an efficient way without passing in request context
        vdc = vcd_utils.get_vdc(self._sysadmin_client, vdc_id=ovdc_id)

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
        op_ctx.is_async = True
        self._remove_compute_policy_from_vdc_async(
            op_ctx=op_ctx,
            task=task,
            task_href=task_href,
            user_href=user_href,
            org_href=org.href,
            ovdc_id=ovdc_id,
            compute_policy_href=compute_policy_href,
            remove_compute_policy_from_vms=remove_compute_policy_from_vms)

        return {
            'task_href': task_href
        }

    @utils.run_async
    def _remove_compute_policy_from_vdc_async(self, *args,
                                              op_ctx: ctx.OperationContext, # noqa: E501
                                              task,
                                              task_href,
                                              user_href,
                                              org_href,
                                              ovdc_id,
                                              compute_policy_href,
                                              remove_compute_policy_from_vms):
        user_name = self._session.get('user')
        vdc = vcd_utils.get_vdc(self._sysadmin_client, vdc_id=ovdc_id,
                                is_admin_operation=True)
        try:
            if remove_compute_policy_from_vms:
                cp_list = self.list_compute_policies_on_vdc(ovdc_id)
                system_default_href = None
                for cp_dict in cp_list:
                    if cp_dict['name'] == _SYSTEM_DEFAULT_COMPUTE_POLICY:
                        system_default_href = cp_dict['href']
                if system_default_href is None:
                    raise EntityNotFoundException(
                        f"Error: {_SYSTEM_DEFAULT_COMPUTE_POLICY} "
                        f"compute policy not found")

                compute_policy_id = retrieve_compute_policy_id_from_href(compute_policy_href) # noqa: E501
                vapps = vcd_utils.get_all_vapps_in_ovdc(self._sysadmin_client,
                                                        ovdc_id)
                target_vms = []
                for vapp in vapps:
                    vm_resources = vapp.get_all_vms()
                    for vm_resource in vm_resources:
                        if vm_resource.VdcComputePolicy.get('id') == compute_policy_id: # noqa: E501
                            target_vms.append(vm_resource)
                vm_names = [vm.get('name') for vm in target_vms]

                task.update(
                    status=vcd_client.TaskStatus.RUNNING.value,
                    namespace='vcloud.cse',
                    operation=f"Setting compute policy to "
                              f"'{_SYSTEM_DEFAULT_COMPUTE_POLICY}' on "
                              f"{len(vm_names)} affected VMs: {vm_names}",
                    operation_name='Remove org VDC compute policy',
                    details='',
                    progress=None,
                    owner_href=vdc.href,
                    owner_name=vdc.name,
                    owner_type=vcd_client.EntityType.VDC.value,
                    user_href=user_href,
                    user_name=user_name,
                    task_href=task_href,
                    org_href=org_href,
                )

                task_monitor = self._sysadmin_client.get_task_monitor()
                for vm_resource in target_vms:
                    vm = VM(self._sysadmin_client,
                            href=vm_resource.get('href'))
                    _task = vm.update_compute_policy(system_default_href)

                    task.update(
                        status=vcd_client.TaskStatus.RUNNING.value,
                        namespace='vcloud.cse',
                        operation=f"Setting compute policy to "
                                  f"'{_SYSTEM_DEFAULT_COMPUTE_POLICY}' on VM "
                                  f"'{vm_resource.get('name')}'",
                        operation_name='Remove org VDC compute policy',
                        details='',
                        progress=None,
                        owner_href=vdc.href,
                        owner_name=vdc.name,
                        owner_type=vcd_client.EntityType.VDC.value,
                        user_href=user_href,
                        user_name=user_name,
                        task_href=task_href,
                        org_href=org_href,
                    )
                    task_monitor.wait_for_success(_task)

            task.update(
                status=vcd_client.TaskStatus.RUNNING.value,
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
                org_href=org_href,
            )

            vdc.remove_compute_policy(compute_policy_href)

            task.update(
                status=vcd_client.TaskStatus.SUCCESS.value,
                namespace='vcloud.cse',
                operation=f"Removed compute policy (href: "
                          f"{compute_policy_href}) from org VDC '{vdc.name}'",
                operation_name='Updating VDC',
                details='',
                progress=None,
                owner_href=vdc.href,
                owner_name=vdc.name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=user_name,
                task_href=task_href,
                org_href=org_href,
            )
        except Exception as err:
            logger.SERVER_LOGGER.error(err, exc_info=True)
            task.update(
                status=vcd_client.TaskStatus.ERROR.value,
                namespace='vcloud.cse',
                operation='',
                operation_name='Remove org VDC compute policy',
                details='',
                progress=None,
                owner_href=vdc.href,
                owner_name=vdc.name,
                owner_type=vcd_client.EntityType.VDC.value,
                user_href=user_href,
                user_name=user_name,
                task_href=task_href,
                org_href=org_href,
                error_message=f"{err}")
        finally:
            if op_ctx.sysadmin_client:
                op_ctx.end()
