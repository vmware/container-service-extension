# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Server utility methods used only by the CSE server."""

import enum
import math

import semantic_version

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.rde.models.common_models as common_models


def get_installed_cse_version() -> semantic_version.Version:
    """."""
    cse_version_raw = utils.get_cse_info()['version']
    # Cleanup version string. Strip dev version string segment.
    # e.g. convert '2.6.0.0b2.dev5' to '2.6.0'
    tokens = cse_version_raw.split('.')[:3]
    return semantic_version.Version('.'.join(tokens))


def get_server_runtime_config():
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
    return str(config['service']['rde_version_in_use'])


def get_registered_def_entity_type() -> common_models.DefEntityType:
    """Fetch the native cluster entity type loaded during server startup."""
    from container_service_extension.server.service import Service
    return Service().get_native_cluster_entity_type()


def get_registered_def_interface() -> common_models.DefInterface:
    """Fetch the native cluster interface loaded during server startup."""
    from container_service_extension.server.service import Service
    return Service().get_kubernetes_interface()


def get_default_k8_distribution():
    config = get_server_runtime_config()
    import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0
    return rde_1_0_0.Distribution(
        template_name=config['broker']['default_template_name'],
        template_revision=config['broker']['default_template_revision'])


def get_pks_cache():
    from container_service_extension.server.service import Service
    return Service().get_pks_cache()


def is_pks_enabled():
    from container_service_extension.server.service import Service
    return Service().is_pks_enabled()


# noinspection PyBroadException
def is_tkg_plus_enabled(config: dict = None):
    """
    Check if TKG plus is enabled by the provider in the config.

    :param dict config: configuration provided by the user.
    :rtype: bool
    """
    if not config:
        try:
            config = get_server_runtime_config()
        except Exception:
            return False
    service_section = config.get('service', {})
    tkg_plus_enabled = service_section.get('enable_tkg_plus', False)
    if isinstance(tkg_plus_enabled, bool):
        return tkg_plus_enabled
    elif isinstance(tkg_plus_enabled, str):
        return utils.str_to_bool(tkg_plus_enabled)
    return False


def should_use_mqtt_protocol(config):
    """Return true if should use the mqtt protocol; false otherwise.

    The MQTT protocol should be used if the config file contains "mqtt" key
        and the CSE server is not being run in legacy mode.

    :param dict config: config yaml file as a dictionary

    :return: whether to use the mqtt protocol
    :rtype: bool
    """
    return config.get('mqtt') is not None and \
        not utils.str_to_bool(config['service'].get('legacy_mode'))


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


def construct_paginated_response(values, result_total,
                                 page_number=shared_constants.CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                 page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE,  # noqa: E501
                                 page_count=None,
                                 next_page_uri=None,
                                 prev_page_uri=None):
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
        query_params=None):
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
