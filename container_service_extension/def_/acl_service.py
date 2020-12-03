# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.cloudapi.cloudapi_client as cloudApiClient
import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.server_constants as server_constants
import container_service_extension.shared_constants as shared_constants


class ClusterACLService:
    """Manages retrieving and setting Cluster ACL information."""

    def __init__(self, cluster_id: str,
                 cloudapi_client: cloudApiClient.CloudApiClient):
        self._cloudapi_client = cloudapi_client
        self._cluster_id = cluster_id

    def get_all_def_ent_acl(self):
        """Get all def entity acl values from all pages.

        :return dict of user id keys and a dictionary values containing the
            acl entry id and access level id
        """
        access_controls_path = \
            f'{cloudapi_constants.CloudApiResource.ENTITIES}' \
            f'/{self._cluster_id}/{cloudapi_constants.CloudApiResource.ACL}'
        user_acl_info = {}
        curr_page, page_cnt = 0, 1
        while curr_page < page_cnt:
            query_str = f'?{shared_constants.PAGE}={curr_page + 1}' \
                        f'&{shared_constants.PAGE_SIZE}=' \
                        f'{shared_constants.DEFAULT_PAGE_SZ}'
            de_acl_response: dict = self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.GET,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=(access_controls_path + query_str))
            for acl_entry in de_acl_response.get('values'):
                user_id = acl_entry[
                    shared_constants.AccessControlKey.MEMBER_ID]  # noqa: E501
                user_acl_info[user_id] = {
                    shared_constants.AccessControlKey.ID:
                        acl_entry[shared_constants.AccessControlKey.ID],
                    shared_constants.AccessControlKey.ACCESS_LEVEL_ID:
                        acl_entry[shared_constants.AccessControlKey.ACCESS_LEVEL_ID]  # noqa: E501
                }
            curr_page = int(de_acl_response.get('page', 1))
            page_cnt = int(de_acl_response.get('pageCount', 1))
        return user_acl_info

    def update_native_def_entity_acl(self, update_acl_entries,
                                     prev_user_acl_info):
        """Update native defined entity acl.

        :param list update_acl_entries: list of dict entries containing the
            'memberId' and 'accessLevelId' fields
        :param list prev_user_acl_info: dict mapping user id to dict of
            acl entry id and acl level id

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
            user_id = acl_entry[shared_constants.AccessControlKey.MEMBER_ID]
            acl_level = acl_entry[
                shared_constants.AccessControlKey.ACCESS_LEVEL_ID]
            payload[shared_constants.AccessControlKey.MEMBER_ID] = user_id
            payload[
                shared_constants.AccessControlKey.ACCESS_LEVEL_ID] = acl_level
            user_acl_level_dict[user_id] = acl_level
            self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.POST,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=access_controls_path,
                payload=payload)

            # Remove entry from previous user acl info
            if own_prev_user_acl_info.get(user_id):
                del own_prev_user_acl_info[user_id]

        # Delete def entity acl entries not in update_acl_entries
        for _, acl_info in own_prev_user_acl_info.items():
            delete_path = access_controls_path + \
                f'/{acl_info[shared_constants.AccessControlKey.ID]}'
            self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
                resource_url_relative_path=delete_path)

        return user_acl_level_dict


def form_cluster_acl_entry(user_urn, username, access_level_urn):
    """Form ACL entry.

    :param str user_urn: user URN id, e.g., 'urn:vcloud:user:1234567'
    :param str access_level_urn: access level URN id, e.g.,
        'urn:vcloud:accessLevel:FullControl'

    :return acl entry
    """
    return {
        shared_constants.AccessControlKey.MEMBER_ID: user_urn,
        shared_constants.AccessControlKey.USERNAME: username,
        shared_constants.AccessControlKey.ACCESS_LEVEL_ID: access_level_urn
    }


def get_id_from_user_href(user_href):
    if user_href.startswith(server_constants.USER_PATH):
        return user_href.split(server_constants.USER_PATH)[-1]
    return None


def form_vapp_access_setting(access_level, name, href, user_id):
    vapp_access_setting = {
        shared_constants.AccessControlKey.ACCESS_LEVEL: access_level,
        shared_constants.AccessControlKey.SUBJECT: {
            shared_constants.AccessControlKey.NAME: name,
            shared_constants.AccessControlKey.HREF: href,
            shared_constants.AccessControlKey.ID: user_id
        }
    }
    return vapp_access_setting
