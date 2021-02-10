# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Server utility methods used only by the CSE server."""

import math

import semantic_version

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.rde.models_.common_models
import container_service_extension.rde.models_.rde_1_0_0


def get_installed_cse_version():
    """."""
    cse_version_raw = utils.get_cse_info()['version']
    # Cleanup version string. Strip dev version string segment.
    # e.g. convert '2.6.0.0b2.dev5' to '2.6.0'
    tokens = cse_version_raw.split('.')[:3]
    cse_version = semantic_version.Version('.'.join(tokens))
    return cse_version


def get_server_runtime_config():
    import container_service_extension.server.service as cse_service
    return cse_service.Service().get_service_config()


def get_server_api_version():
    """Get the API version with which CSE server is running.

    :return: api version
    """
    config = get_server_runtime_config()
    return config['vcd']['api_version']


def get_default_storage_profile():
    config = get_server_runtime_config()
    return config['broker']['storage_profile']


def get_default_k8_distribution():
    config = get_server_runtime_config()
    import container_service_extension.rde.models_.rde_1_0_0 as rde_1_0_0
    return rde_1_0_0.Distribution(template_name=config['broker']['default_template_name'],
                                  template_revision=config['broker']['default_template_revision'])


def get_pks_cache():
    from container_service_extension.server.service import Service
    return Service().get_pks_cache()


def is_pks_enabled():
    from container_service_extension.server.service import Service
    return Service().is_pks_enabled()


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

    The MQTT protocol should be used if the config file contains an "mqtt" key
        and the api version is greater than or equal to the minimum mqtt
        api version.

    :param dict config: config yaml file as a dictionary

    :return: whether to use the mqtt protocol
    :rtype: str
    """
    return config.get('mqtt') is not None and \
        config.get('vcd') is not None and \
        config['vcd'].get('api_version') is not None and \
        float(config['vcd']['api_version']) >= server_constants.MQTT_MIN_API_VERSION  # noqa: E501


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


def create_links_and_construct_paginated_result(base_uri, values, result_total,
                                                page_number=shared_constants.CSE_PAGINATION_FIRST_PAGE_NUMBER,  # noqa: E501
                                                page_size=shared_constants.CSE_PAGINATION_DEFAULT_PAGE_SIZE,  # noqa: E501
                                                query_params=None):
    if query_params is None:
        query_params = {}
    next_page_uri: str = None
    if 0 < page_number * page_size < result_total:
        # TODO find a way to get the initial url part
        # ideally the request details should be passed down to each of the
        # handler funcions as request context
        next_page_uri = f"{base_uri}?page={page_number+1}&pageSize={page_size}"
        for q in query_params.keys():
            next_page_uri += f"&{q}={query_params[q]}"

    page_count = math.ceil(result_total / page_size)
    prev_page_uri: str = None
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
