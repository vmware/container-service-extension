# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from enum import Enum
from enum import unique

from container_service_extension import shared_constants as shared_constants
from container_service_extension.cloudapi import constants as cloudapi_constants  # noqa: E501
from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
import container_service_extension.exceptions as excptn

# Defined Entity Framework related constants
DEF_CSE_VENDOR = 'cse'
DEF_VMWARE_VENDOR = 'vmware'
DEF_VMWARE_INTERFACE_NSS = 'k8s'
DEF_VMWARE_INTERFACE_VERSION = '1.0.0'
DEF_VMWARE_INTERFACE_NAME = 'Kubernetes'
DEF_TKG_ENTITY_TYPE_NSS = 'tkgcluster'
DEF_TKG_ENTITY_TYPE_VERSION = '1.0.0'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_NATIVE_ENTITY_TYPE_NAME = 'nativeClusterEntityType'
DEF_NATIVE_ENTITY_TYPE_RIGHT_BUNDLE = \
    f'{DEF_CSE_VENDOR}:{DEF_NATIVE_ENTITY_TYPE_NSS} Entitlement'

DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0
DEF_SCHEMA_DIRECTORY = 'cse_def_schema'
DEF_ENTITY_TYPE_SCHEMA_FILE = 'schema.json'
DEF_ERROR_MESSAGE_KEY = 'message'
DEF_RESOLVED_STATE = 'RESOLVED'
TKG_ENTITY_TYPE_NSS = 'tkgcluster'
TKG_ENTITY_TYPE_VERSION = '1.0.0'


@unique
class DefKey(str, Enum):
    INTERFACE_VENDOR = 'interface_vendor'
    INTERFACE_NSS = 'interface_nss'
    INTERFACE_VERSION = 'interface_version'
    INTERFACE_NAME = 'interface_name'
    ENTITY_TYPE_VENDOR = 'entity_type_vendor'
    ENTITY_TYPE_NAME = 'entity_type_name'
    ENTITY_TYPE_NSS = 'entity_type_nss'
    ENTITY_TYPE_VERSION = 'entity_type_version'
    ENTITY_TYPE_SCHEMA_VERSION = 'schema_version'


MAP_API_VERSION_TO_KEYS = {
    35.0: {
        DefKey.INTERFACE_VENDOR: DEF_VMWARE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_VMWARE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_VMWARE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_VMWARE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_VENDOR: DEF_CSE_VENDOR,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME,
        DefKey.ENTITY_TYPE_SCHEMA_VERSION: 'api_v35',
    }
}


class ClusterEntityFilterKey(Enum):
    """Keys to filter cluster entities in CSE (or) vCD.

    Below Keys are commonly used filters. An entity can be filtered by any of
    its properties.

    Usage examples:
    ..api/cse/internal/clusters?entity.kind=native
    ..api/cse/internal/clusters?entity.metadata.org_name=org1
    ..cloudapi/1.0.0/entities?filter=entity.metadata.org_name==org1
    """

    # TODO(DEF) CLI can leverage this enum for the filter implementation.
    CLUSTER_NAME = 'name'
    ORG_NAME = 'entity.metadata.org_name'
    OVDC_NAME = 'entity.metadata.ovdc_name'
    KIND = 'entity.kind'
    K8_DISTRIBUTION = 'entity.spec.k8_distribution.template_name'
    STATE = 'state'
    PHASE = 'entity.status.phase'


def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < DEF_API_MIN_VERSION:
        raise excptn.DefNotSupportedException("Defined entity framework is not"
                                              " supported for {cloudapi_client.get_api_version()}")  # noqa: E501


def get_registered_def_interface():
    """Fetch the native cluster interface loaded during server startup."""
    from container_service_extension.service import Service
    return Service().get_kubernetes_interface()


def get_registered_def_entity_type():
    """Fetch the native cluster entity type loaded during server startup."""
    from container_service_extension.service import Service
    return Service().get_native_cluster_entity_type()


def generate_interface_id(vendor, nss, version):
    """Generate defined entity interface id.

    By no means, id generation in this method, guarantees the actual
    entity type registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{DEF_INTERFACE_ID_PREFIX}:{vendor}:{nss}:{version}"


def generate_entity_type_id(vendor, nss, version):
    """Generate defined entity type id.

    By no means, id generation in this method, guarantees the actual
    interface registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{vendor}:{nss}:{version}"


def get_all_def_ent_acl(cloudapi_client, de_id):
    """Get all def entity acl values from all pages.

    :param str de_id: defined entity id

    :return dict of user id keys and a dictionary values containing the
        acl entry id and access level id
    """
    rel_url_path = f'entities/{de_id}/accessControls'
    user_acl_info = {}
    curr_page, page_cnt = 0, 1
    while curr_page < page_cnt:
        query_str = f'?{shared_constants.PAGE}={curr_page + 1}' \
                    f'&{shared_constants.PAGE_SIZE}=' \
                    f'{shared_constants.DEFAULT_PAGE_SZ}'
        de_acl_response = cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=(rel_url_path + query_str))
        for acl_entry in de_acl_response.get('values'):
            user_id = acl_entry[shared_constants.AccessControlKey.MEMBER_ID]  # noqa: E501
            user_acl_info[user_id] = {
                shared_constants.AccessControlKey.ID:
                    acl_entry[shared_constants.AccessControlKey.ID],
                shared_constants.AccessControlKey.ACCESS_LEVEL_ID:
                    acl_entry[shared_constants.AccessControlKey.ACCESS_LEVEL_ID]  # noqa: E501
            }
        curr_page = int(de_acl_response.get('page', 1))
        page_cnt = int(de_acl_response.get('pageCount', 1))
    return user_acl_info


def update_native_def_entity_acl(cloudapi_client, de_id, update_acl_entries,
                                 prev_user_acl_info):
    """Update native defined entity acl.

    :param CloudApiClient cloudapi_client: cloudapi vlient
    :param str de_id: defined entity id
    :param list update_acl_entries: list of dict entries containing the
        'memberId' and 'accessLevelId' fields
    :param list prev_user_acl_info: dict mapping user id to dict of
        acl entry id and acl level id

    :return: dictionary of memberId keys and access level values
    """
    own_prev_user_acl_info = prev_user_acl_info.copy()

    # Share defined entity
    user_acl_level_dict = {}
    access_controls_path = f'entities/{de_id}/accessControls'
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
        payload[shared_constants.AccessControlKey.ACCESS_LEVEL_ID] = acl_level
        user_acl_level_dict[user_id] = acl_level
        cloudapi_client.do_request(
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
        cloudapi_client.do_request(
            method=shared_constants.RequestMethod.DELETE,
            cloudapi_version=cloudapi_constants.CLOUDAPI_VERSION_1_0_0,
            resource_url_relative_path=delete_path)

    return user_acl_level_dict
