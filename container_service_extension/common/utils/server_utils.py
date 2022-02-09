# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Server utility methods used only by the CSE server."""

import enum
import math
from typing import Optional

import semantic_version

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
from container_service_extension.config.server_config import ServerConfig
import container_service_extension.rde.models.common_models as common_models
from container_service_extension.server.pks.pks_cache import PksCache


def get_server_runtime_config() -> ServerConfig:
    import container_service_extension.server.service as cse_service
    return cse_service.Service().get_service_config()


def get_rde_version_in_use() -> str:
    """Get the RDE version used by CSE server.

    :return: rde version
    :rtype: str
    """
    # TODO: Currently in many places, this method is used with expected
    #  return type is string. This should be changed to return semantic version
    #  with all dependencies changed as well.
    config = get_server_runtime_config()
    return str(config.get_value_at('service.rde_version_in_use'))


def get_registered_def_entity_type() -> common_models.DefEntityType:
    """Fetch the native cluster entity type loaded during server startup."""
    from container_service_extension.server.service import Service
    return Service().get_native_cluster_entity_type()


def get_pks_cache() -> PksCache:
    from container_service_extension.server.service import Service
    return Service().get_pks_cache()


def is_pks_enabled() -> bool:
    from container_service_extension.server.service import Service
    return Service().is_pks_enabled()


def is_tkg_plus_enabled(config: Optional[ServerConfig] = None) -> bool:
    """
    Check if TKG plus is enabled by the provider in the config.

    :param ServerConfig config: configuration provided by the user.

    :return: whether TKG+ is enabled or not.
    :rtype: bool
    """
    if not config:
        try:
            config = get_server_runtime_config()
        except Exception:
            return False
    try:
        tkg_plus_enabled = config.get_value_at('service.enable_tkg_plus')
    except KeyError:
        return False
    if isinstance(tkg_plus_enabled, bool):
        return tkg_plus_enabled
    elif isinstance(tkg_plus_enabled, str):
        return utils.str_to_bool(tkg_plus_enabled)
    return False


def should_use_mqtt_protocol(config: ServerConfig) -> bool:
    """Return true if should use the mqtt protocol; false otherwise.

    The MQTT protocol should be used if the config file contains "mqtt" key
        and the CSE server is not being run in legacy mode.

    :param dict config: config yaml file as a dictionary

    :return: whether to use the mqtt protocol
    :rtype: bool
    """
    return config.get_value_at('mqtt') is not None and \
        not utils.str_to_bool(config.get_value_at('service.legacy_mode'))


def is_no_vc_communication_mode(config: Optional[ServerConfig] = None) -> bool:  # noqa: E501
    """Check if TKGm only mode is enabled by the provider in the config.

    :param ServerConfig config: configuration provided by the user.

    :return: whether TKGm only mode is enabled or not.
    :rtype: bool
    """
    if not config:
        try:
            config = get_server_runtime_config()
        except Exception:
            return False
    try:
        is_no_vc_comm = config.get_value_at('service.no_vc_communication_mode')
    except KeyError:
        return False

    if isinstance(is_no_vc_comm, bool):
        return is_no_vc_comm
    elif isinstance(is_no_vc_comm, str):
        return utils.str_to_bool(is_no_vc_comm)
    return False


def is_test_mode(config: Optional[ServerConfig] = None) -> bool:
    """Check if test mode is enabled in the config.

    :param dict config: configuration provided by the user.

    :return: boolean indicating if test mode is enabled.
    :rtype: bool
    """
    if not config:
        try:
            config = get_server_runtime_config()
        except Exception:
            return False
    try:
        config.get_value_at('test')
        return True
    except KeyError:
        return False


def get_template_descriptor_keys(cookbook_version: semantic_version.Version) -> enum.EnumMeta:  # noqa: E501
    """Get template descriptor keys using the cookbook version."""
    # if cookbook version is None, use version 1.0
    if not cookbook_version:
        cookbook_version = \
            server_constants.RemoteTemplateCookbookVersion.Version1.value
    cookbook_version_to_template_descriptor_keys_map = {
        server_constants.RemoteTemplateCookbookVersion.Version1.value: server_constants.RemoteTemplateKeyV1,  # noqa: E501
        server_constants.RemoteTemplateCookbookVersion.Version2.value: server_constants.RemoteTemplateKeyV2  # noqa: E501
    }
    return cookbook_version_to_template_descriptor_keys_map[cookbook_version]


def construct_paginated_response(
        values,
        result_total,
        page_number=shared_constants.CSE_PAGINATION_FIRST_PAGE_NUMBER,
        page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE,
        page_count=None,
        next_page_uri=None,
        prev_page_uri=None
):
    if not page_count:
        extra_page = 1 if bool(result_total % page_size) else 0
        page_count = result_total // page_size + extra_page
    resp = {
        shared_constants.PaginationKey.RESULT_TOTAL: result_total,
        shared_constants.PaginationKey.PAGE_COUNT: page_count,
        shared_constants.PaginationKey.PAGE_NUMBER: page_number,
        shared_constants.PaginationKey.PAGE_SIZE: page_size,
        shared_constants.PaginationKey.NEXT_PAGE_URI: next_page_uri,
        shared_constants.PaginationKey.PREV_PAGE_URI: prev_page_uri,
        shared_constants.PaginationKey.VALUES: values
    }

    # Conditionally deleting instead of conditionally adding the entry
    # maintains the order for the response
    if not prev_page_uri:
        del resp[shared_constants.PaginationKey.PREV_PAGE_URI]
    if not next_page_uri:
        del resp[shared_constants.PaginationKey.NEXT_PAGE_URI]
    return resp


def create_links_and_construct_paginated_result(
        base_uri,
        values,
        result_total,
        page_number=shared_constants.CSE_PAGINATION_FIRST_PAGE_NUMBER,
        page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE,
        query_params=None
):
    if query_params is None:
        query_params = {}
    next_page_uri: str = ''
    if 0 < page_number * page_size < result_total:
        # TODO find a way to get the initial url part
        # ideally the request details should be passed down to each of the
        # handler functions as request context
        next_page_uri = f"{base_uri}?page={page_number+1}&pageSize={page_size}"
        for q in query_params.keys():
            next_page_uri += f"&{q}={query_params[q]}"

    page_count = math.ceil(result_total / page_size)
    prev_page_uri: str = ''
    if page_count >= page_number > 1:
        prev_page_uri = f"{base_uri}?page={page_number-1}&pageSize={page_size}"

    # add the rest of the query parameters
    for q in query_params.keys():
        if next_page_uri:
            next_page_uri += f"&{q}={query_params[q]}"
        if prev_page_uri:
            prev_page_uri += f"&{q}={query_params[q]}"

    return construct_paginated_response(values=values,
                                        result_total=result_total,
                                        page_number=page_number,
                                        page_size=page_size,
                                        page_count=page_count,
                                        next_page_uri=next_page_uri,
                                        prev_page_uri=prev_page_uri)
