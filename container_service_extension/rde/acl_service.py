# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from typing import Dict, List, Optional

import lxml
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.utils as pyvcloud_utils
import pyvcloud.vcd.vapp as vcd_vapp

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.lib.cloudapi.constants as cloudapi_constants
import container_service_extension.rde.common.entity_service as def_entity_svc
import container_service_extension.rde.constants as def_constants
import container_service_extension.rde.models.common_models as common_models


class ClusterACLService:
    """Manages retrieving and setting Cluster ACL information."""

    def __init__(self, cluster_id: str,
                 client: vcd_client.Client):
        self._client = client
        self._cloudapi_client = \
            vcd_utils.get_cloudapi_client_from_vcd_client(client)
        self._cluster_id = cluster_id
        self._def_entity: Optional[common_models.DefEntity] = None
        self._vapp: Optional[vcd_vapp.VApp] = None

    @property
    def def_entity(self):
        if self._def_entity is None:
            entity_svc = def_entity_svc.DefEntityService(self._cloudapi_client)
            self._def_entity = entity_svc.get_tkg_or_def_entity(self._cluster_id)  # noqa: E501
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
                yield common_models.ClusterAclEntry(**acl_entry)

    def create_user_id_to_acl_entry_dict(self):
        """Get all def entity acl values from all pages.

        :return dict of user id keys and def_models.ClusterAclEntry values
        """
        user_id_to_acl_entry = {}
        for acl_entry in self.list_def_entity_acl_entries():
            user_id_to_acl_entry[acl_entry.memberId] = acl_entry
        return user_id_to_acl_entry

    def share_def_entity(self, acl_entry: common_models.ClusterAclEntry):
        access_controls_path = \
            f'{cloudapi_constants.CloudApiResource.ENTITIES}/' \
            f'{self._cluster_id}/{cloudapi_constants.CloudApiResource.ACL}'
        ent_kind = self.def_entity.entity.kind \
            if hasattr(self.def_entity, 'entity') else self.def_entity.kind
        if ent_kind in \
                [shared_constants.ClusterEntityKind.NATIVE.value,
                 shared_constants.ClusterEntityKind.TKG_PLUS.value]:
            org_id = vcd_utils.extract_id(self.def_entity.org.id)
        elif ent_kind == shared_constants.ClusterEntityKind.TKG_S.value:
            vdc_name = self.def_entity.metadata.virtualDataCenterName
            org_id = vcd_utils.get_org_id_from_vdc_name(
                client=self._client,
                vdc_name=vdc_name)
        else:
            raise Exception(f"Invalid entity kind: {ent_kind}")

        payload = acl_entry.construct_filtered_dict(
            include=shared_constants.DEF_ENTITY_ACCESS_CONTROL_KEYS)
        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=access_controls_path,
            additional_request_headers={server_constants.TENANT_CONTEXT_HEADER: org_id},  # noqa: E501
            payload=payload)

    def unshare_def_entity(self, acl_id):
        delete_path = f'{cloudapi_constants.CloudApiResource.ENTITIES}/' \
            f'{self._cluster_id}/{cloudapi_constants.CloudApiResource.ACL}/' \
            f'{acl_id}'
        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.DELETE,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=delete_path)

    def update_native_def_entity_acl(self, update_acl_entries: List[common_models.ClusterAclEntry],  # noqa: E501
                                     prev_user_id_to_acl_entry: Dict[str, common_models.ClusterAclEntry]):  # noqa: E501
        """Update native defined entity acl.

        :param list update_acl_entries: list of def_models.ClusterAclEntry
        :param dict prev_user_id_to_acl_entry: dict mapping user id to
            def_models.ClusterAclEntry

        :return: dictionary of memberId keys and access level values
        """
        own_prev_user_id_to_acl_entry = prev_user_id_to_acl_entry.copy()

        # Share defined entity
        ent_org_user_id_names_dict = vcd_utils.create_org_user_id_to_name_dict(
            client=self._client,
            org_name=self.def_entity.org.name)
        user_acl_level_dict = {}
        share_acl_entry = common_models.ClusterAclEntry(
            grantType=shared_constants.MEMBERSHIP_GRANT_TYPE,
            memberId=None,
            accessLevelId=None)
        for acl_entry in update_acl_entries:
            user_id = acl_entry.memberId
            if ent_org_user_id_names_dict.get(user_id) is None:
                # This user must be from the system org and does not need
                # to be re-shared. Sharing can not happen from a tenant user
                # to a system user.
                del own_prev_user_id_to_acl_entry[user_id]
                continue
            acl_level = acl_entry.accessLevelId
            share_acl_entry.memberId = user_id
            share_acl_entry.accessLevelId = acl_level
            user_acl_level_dict[user_id] = acl_level
            self.share_def_entity(share_acl_entry)

            # Remove entry from previous user acl info
            if own_prev_user_id_to_acl_entry.get(user_id):
                del own_prev_user_id_to_acl_entry[user_id]

        # Delete def entity acl entries not in update_acl_entries
        for _, acl_entry in own_prev_user_id_to_acl_entry.items():
            self.unshare_def_entity(acl_entry.id)
        return user_acl_level_dict

    def native_get_vapp_settings_only_vapp_shared(self, def_entity_user_ids: set):  # noqa: E501
        """Get vapp settings in which the defined entity is not also shared.

        :param set def_entity_user_ids: set of user ids that have access to
            the defined entity

        :return: vapp settings in which only the vapp is shared
        :rtype: list
        """
        non_updated_access_settings = []
        vapp_access_settings: lxml.objectify.ObjectifiedElement = \
            self.vapp.get_access_settings()
        # Only add entries in which the defined entity is not shared
        if hasattr(vapp_access_settings, 'AccessSettings'):
            vapp_access_settings_attr = vapp_access_settings.AccessSettings
            for child_obj in vapp_access_settings_attr.getchildren():
                # Get user_urn
                child_obj_attrib = child_obj.getchildren()[0].attrib
                shared_href = child_obj_attrib.get('href')
                user_id = utils.extract_id_from_href(shared_href)
                user_urn = f'{shared_constants.USER_URN_PREFIX}{user_id}'

                # Add entries in which only vapp is shared
                if user_urn not in def_entity_user_ids:
                    user_name = child_obj_attrib.get('name')

                    curr_setting = form_vapp_access_setting_entry(
                        access_level=str(child_obj.AccessLevel),
                        name=user_name,
                        href=shared_href,
                        user_id=user_id)
                    non_updated_access_settings.append(curr_setting)
        return non_updated_access_settings

    def native_update_vapp_access_settings(self, prev_user_id_to_acl_entry_dict,  # noqa: E501
                                           update_cluster_acl_entries: List[
                                               common_models.ClusterAclEntry]):
        def_entity_user_ids = {acl_entry.memberId for _, acl_entry in
                               prev_user_id_to_acl_entry_dict.items()}
        total_vapp_access_settings = self.native_get_vapp_settings_only_vapp_shared(def_entity_user_ids)  # noqa: E501

        # Add updated access settings
        vapp_access_settings: lxml.objectify.ObjectifiedElement = \
            self.vapp.get_access_settings()
        api_uri = self._client.get_api_uri()
        system_user_names: Optional[set] = None
        if self._client.is_sysadmin():
            system_user_names = vcd_utils.get_org_user_names(
                client=self._client,
                org_name=shared_constants.SYSTEM_ORG_NAME)
        for acl_entry in update_cluster_acl_entries:
            user_name = acl_entry.username
            # Skip system users since sharing can't be outside an org
            if system_user_names and user_name in system_user_names:
                continue
            user_id = pyvcloud_utils.extract_id(acl_entry.memberId)
            access_level = pyvcloud_utils.extract_id(acl_entry.accessLevelId)

            # Use 'Change' instead of 'ReadWrite' for vApp access level
            if access_level == shared_constants.READ_WRITE:
                access_level = server_constants.CHANGE_ACCESS
            user_setting = form_vapp_access_setting_entry(
                access_level=access_level,
                name=user_name,
                href=f'{api_uri}{server_constants.ADMIN_USER_PATH}{user_id}',
                user_id=user_id)
            total_vapp_access_settings.append(user_setting)

        vapp_share_contents = {
            server_constants.VappAccessKey.IS_SHARED_TO_EVERYONE:
                bool(vapp_access_settings.IsSharedToEveryone),
            server_constants.VappAccessKey.ACCESS_SETTINGS:
                {server_constants.VappAccessKey.ACCESS_SETTING: total_vapp_access_settings}  # noqa: E501
        }

        org_id = pyvcloud_utils.extract_id(self.def_entity.org.id)
        org_name = self.def_entity.org.name
        extra_vapp_headers = {
            server_constants.TENANT_CONTEXT_HEADER: org_id,
            server_constants.AUTH_CONTEXT_HEADER: org_name,
            server_constants.VCLOUD_AUTHORIZATION_HEADER: org_name
        }
        self._client.post_resource(
            uri=f'{self.vapp.href}{def_constants.ACTION_CONTROL_ACCESS_PATH}',
            contents=vapp_share_contents,
            media_type='application/*+json',
            extra_headers=extra_vapp_headers)

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
