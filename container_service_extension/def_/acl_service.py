# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from typing import Dict, List

import lxml
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.utils as pyvcloud_utils
import pyvcloud.vcd.vapp as vcd_vapp

import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.def_.constants as def_constants
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.models as def_models
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.server_constants as server_constants
import container_service_extension.shared_constants as shared_constants
import container_service_extension.utils as utils


class ClusterACLService:
    """Manages retrieving and setting Cluster ACL information."""

    def __init__(self, cluster_id: str,
                 client: vcd_client.Client):
        self._client = client
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(client)
        self._cluster_id = cluster_id
        self._def_entity: def_models.DefEntity = None
        self._vapp: vcd_vapp.VApp = None

    @property
    def def_entity(self):
        if self._def_entity is None:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            self._def_entity = entity_svc.get_entity(self._cluster_id)
        return self._def_entity

    @property
    def vapp(self):
        if self._vapp is None:
            self._vapp = vcd_vapp.VApp(self._client,
                                       href=self.def_entity.externalId)
        return self._vapp

    def get_def_entity_acl_response(self, page, page_size):
        acl_path = f'{cloudapi_constants.CloudApiResource.ENTITIES}/' \
                   f'{self._cluster_id}/' \
                   f'{cloudapi_constants.CloudApiResource.ACL}' \
                   f'?{shared_constants.PaginationKey.PAGE_NUMBER}={page}&' \
                   f'{shared_constants.PaginationKey.PAGE_SIZE}={page_size}'
        de_acl_response = self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=acl_path)
        return de_acl_response

    def list_def_entity_acl_entries(self):
        """List def entity acl.

        :return: Generator of cluster acl entries
        :rtype: Generator[ClusterAclEntry]
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self.get_def_entity_acl_response(
                page_num, shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE)
            values = response_body[shared_constants.PaginationKey.VALUES]
            if len(values) == 0:
                break
            for acl_entry in values:
                yield def_models.ClusterAclEntry(**acl_entry)

    def create_user_id_to_acl_entry_dict(self):
        """Get all def entity acl values from all pages.

        :return dict of user id keys and def_models.ClusterAclEntry values
        """
        user_id_to_acl_entry = {}
        for acl_entry in self.list_def_entity_acl_entries():
            user_id_to_acl_entry[acl_entry.memberId] = acl_entry
        return user_id_to_acl_entry

    def share_def_entity(self, payload):
        access_controls_path = \
            f'{cloudapi_constants.CloudApiResource.ENTITIES}/' \
            f'{self._cluster_id}/{cloudapi_constants.CloudApiResource.ACL}'
        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=access_controls_path,
            payload=payload)

    def update_native_def_entity_acl(self, update_acl_entries: List[def_models.ClusterAclEntry],  # noqa: E501
                                     prev_user_acl_info: Dict[str, def_models.ClusterAclEntry]):  # noqa: E501
        """Update native defined entity acl.

        :param list update_acl_entries: list of def_models.ClusterAclEntry
        :param dict prev_user_acl_info: dict mapping user id to
            def_models.ClusterAclEntry

        :return: dictionary of memberId keys and access level values
        """
        own_prev_user_acl_info = prev_user_acl_info.copy()

        # Share defined entity
        user_acl_level_dict = {}
        access_controls_path = \
            f'{cloudapi_constants.CloudApiResource.ENTITIES}/' \
            f'{self._cluster_id}/{cloudapi_constants.CloudApiResource.ACL}'
        payload = {
            shared_constants.AccessControlKey.GRANT_TYPE:
                shared_constants.MEMBERSHIP_GRANT_TYPE,
            shared_constants.AccessControlKey.MEMBER_ID: None,
            shared_constants.AccessControlKey.ACCESS_LEVEL_ID: None
        }
        for acl_entry in update_acl_entries:
            user_id = acl_entry.memberId
            acl_level = acl_entry.accessLevelId
            payload[shared_constants.AccessControlKey.MEMBER_ID] = user_id
            payload[shared_constants.AccessControlKey.ACCESS_LEVEL_ID] = acl_level  # noqa: E501
            user_acl_level_dict[user_id] = acl_level
            self.share_def_entity(payload)

            # Remove entry from previous user acl info
            if own_prev_user_acl_info.get(user_id):
                del own_prev_user_acl_info[user_id]

        # Delete def entity acl entries not in update_acl_entries
        for _, acl_entry in own_prev_user_acl_info.items():
            delete_path = access_controls_path + f'/{acl_entry.id}'
            self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                resource_url_relative_path=delete_path)

        return user_acl_level_dict

    def native_get_non_updated_vapp_settings(self,
                                             updated_user_acl_level_dict):
        non_updated_access_settings = []
        vapp_access_settings: lxml.objectify.ObjectifiedElement = \
            self.vapp.get_access_settings()
        if hasattr(vapp_access_settings, 'AccessSettings'):
            vapp_access_settings_attr = vapp_access_settings.AccessSettings
            for child_obj in vapp_access_settings_attr.getchildren():
                child_obj_attrib = child_obj.getchildren()[0].attrib
                shared_href = child_obj_attrib.get('href')
                user_id = utils.extract_id_from_href(shared_href)

                # Don't add current access setting if it will be updated
                user_urn = f'{shared_constants.USER_URN_PREFIX}{user_id}'
                if not updated_user_acl_level_dict.get(user_urn):
                    user_name = child_obj_attrib.get('name')

                    curr_setting = form_vapp_access_setting_entry(
                        access_level=str(child_obj.AccessLevel),
                        name=user_name,
                        href=shared_href,
                        user_id=user_id)
                    non_updated_access_settings.append(curr_setting)
        return non_updated_access_settings

    def native_update_vapp_access_settings(self, updated_user_acl_level_dict,
                                           update_cluster_acl_entries: List[def_models.ClusterAclEntry]):  # noqa: E501
        total_vapp_access_settings: list = self.\
            native_get_non_updated_vapp_settings(updated_user_acl_level_dict)

        # Add updated access settings
        vapp_access_settings: lxml.objectify.ObjectifiedElement = \
            self.vapp.get_access_settings()
        api_uri = self._client.get_api_uri()
        for acl_entry in update_cluster_acl_entries:
            user_id = pyvcloud_utils.extract_id(acl_entry.memberId)
            access_level = pyvcloud_utils.extract_id(acl_entry.accessLevelId)

            # Use 'Change' instead of 'ReadWrite' for vApp access level
            if access_level == shared_constants.READ_WRITE:
                access_level = server_constants.CHANGE_ACCESS
            user_setting = form_vapp_access_setting_entry(
                access_level=access_level,
                name=acl_entry.username,
                href=f'{api_uri}{server_constants.ADMIN_USER_PATH}{user_id}',  # noqa: E501
                user_id=user_id)
            total_vapp_access_settings.append(user_setting)

        vapp_share_contents = {
            server_constants.VappAccessKey.IS_SHARED_TO_EVERYONE:
                bool(vapp_access_settings.IsSharedToEveryone),
            server_constants.VappAccessKey.ACCESS_SETTINGS:
                {server_constants.VappAccessKey.ACCESS_SETTING: total_vapp_access_settings}  # noqa: E501
        }

        self._client.post_resource(
            uri=f'{self.vapp.href}{def_constants.ACTION_CONTROL_ACCESS_PATH}',
            contents=vapp_share_contents,
            media_type='application/*+json')

    def get_cluster_entity(self):
        return self.def_entity


def form_vapp_access_setting_entry(access_level, name, href, user_id):
    vapp_access_setting = {
        shared_constants.AccessControlKey.ACCESS_LEVEL: access_level,
        shared_constants.AccessControlKey.SUBJECT: {
            shared_constants.AccessControlKey.NAME: name,
            shared_constants.AccessControlKey.HREF: href,
            shared_constants.AccessControlKey.ID: user_id
        }
    }
    return vapp_access_setting
