# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
from urllib.parse import parse_qsl

import requests

from container_service_extension.exception_handler import handle_exception
from container_service_extension.exceptions import CseRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_handlers.cluster_handler as cluster_handler # noqa: E501
import container_service_extension.request_handlers.ovdc_handler as ovdc_handler # noqa: E501
import container_service_extension.request_handlers.system_handler as system_handler # noqa: E501
import container_service_extension.request_handlers.template_handler as template_handler # noqa: E501
from container_service_extension.server_constants import CseOperation
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RequestMethod


"""Process incoming requests

Following are the valid api endpoints.

GET /cse/clusters?org={org name}&vdc={vdc name}
POST /cse/clusters
GET /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
PUT /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
DELETE /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
GET /cse/cluster/{cluster name}/config?org={org name}&vdc={vdc name}

POST /cse/nodes
DELETE /cse/nodes
GET /cse/node/{node name}?cluster_name={cluster name}&org={org name}&vdc={vdc name}

GET /cse/ovdcs
GET /cse/ovdc/{ovdc id}
PUT /cse/ovdc/{ovdc id}
GET /cse/ovdc/{ovdc_id}/compute-policies
PUT /cse/ovdc/{ovdc_id}/compute-policies

GET /cse/system
PUT /cse/system

GET /cse/template
""" # noqa: E501

OPERATION_TO_HANDLER = {
    CseOperation.CLUSTER_CONFIG: cluster_handler.cluster_config,
    CseOperation.CLUSTER_CREATE: cluster_handler.cluster_create,
    CseOperation.CLUSTER_DELETE: cluster_handler.cluster_delete,
    CseOperation.CLUSTER_INFO: cluster_handler.cluster_info,
    CseOperation.CLUSTER_LIST: cluster_handler.cluster_list,
    CseOperation.CLUSTER_RESIZE: cluster_handler.cluster_resize,
    CseOperation.NODE_CREATE: cluster_handler.node_create,
    CseOperation.NODE_DELETE: cluster_handler.node_delete,
    CseOperation.NODE_INFO: cluster_handler.node_info,
    CseOperation.OVDC_UPDATE: ovdc_handler.ovdc_update,
    CseOperation.OVDC_INFO: ovdc_handler.ovdc_info,
    CseOperation.OVDC_LIST: ovdc_handler.ovdc_list,
    CseOperation.OVDC_COMPUTE_POLICY_LIST: ovdc_handler.ovdc_compute_policy_list, # noqa: E501
    CseOperation.OVDC_COMPUTE_POLICY_UPDATE: ovdc_handler.ovdc_compute_policy_update, # noqa: E501
    CseOperation.SYSTEM_INFO: system_handler.system_info,
    CseOperation.SYSTEM_UPDATE: system_handler.system_update,
    CseOperation.TEMPLATE_LIST: template_handler.template_list,
}

_OPERATION_KEY = 'operation'


@handle_exception
def process_request(body):
    from container_service_extension.service import Service
    LOGGER.debug(f"body: {json.dumps(body)}")
    url = body['requestUri']

    # url_data = _parse_request_url(method=body['method'], url=body['requestUri']) # noqa: E501
    url_data = _get_url_data(body['method'], url)
    operation = url_data[_OPERATION_KEY]

    # check if server is disabled
    if operation not in (CseOperation.SYSTEM_INFO, CseOperation.SYSTEM_UPDATE)\
            and not Service().is_running():
        raise CseRequestError(status_code=requests.codes.bad_request,
                              error_message='CSE service is disabled. Contact'
                                            ' the System Administrator.')

    # create request data dict from request body data
    request_data = {}
    if len(body['body']) > 0:
        raw_body = base64.b64decode(body['body']).decode(sys.getfilesystemencoding()) # noqa: E501
        request_data = json.loads(raw_body)
        LOGGER.debug(f"request body: {request_data}")
    # update request data dict with query params data
    if body['queryString']:
        query_params = dict(parse_qsl(body['queryString']))
        request_data.update(query_params)
        LOGGER.debug(f"query parameters: {query_params}")
    # update request spec with operation specific data in the url
    request_data.update(url_data)

    # process the request
    tenant_auth_token = body['headers']['x-vcloud-authorization']
    reply = {
        'status_code': operation.ideal_response_code,
        'body': OPERATION_TO_HANDLER[operation](request_data, tenant_auth_token) # noqa: E501
    }
    LOGGER.debug(f"reply: {str(reply)}")
    return reply


def _get_url_data(method, url):
    """Parse url and http method to get desired CSE operation and url data.

    Url is processed like a tree to find the desired operation as fast as
    possible. These explicit checks allow any invalid urls or http methods to
    fall through and trigger the appropriate exception.

    Returns a data dictionary with 'operation' key and also any relevant url
    data.

    :param RequestMethod method:
    :param str url:

    :rtype: dict
    """
    invalid_url_msg = "Invalid url - not found"
    bad_method_msg = "Method not allowed"
    tokens = url.split('/')
    num_tokens = len(tokens)

    if num_tokens < 4:
        raise CseRequestError(requests.codes.not_found,
                              error_message=invalid_url_msg)

    operation_type = tokens[3].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == 'cluster':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.CLUSTER_LIST}
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.CLUSTER_CREATE}
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_INFO,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_RESIZE,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == RequestMethod.DELETE:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_DELETE,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)
        if num_tokens == 6 and tokens[5] == 'config':
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_CONFIG,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)

    elif operation_type == 'node':
        if num_tokens == 4:
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.NODE_CREATE}
            if method == RequestMethod.DELETE:
                return {_OPERATION_KEY: CseOperation.NODE_DELETE}
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.NODE_INFO,
                    RequestKey.NODE_NAME: tokens[4]
                }
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)

    elif operation_type == 'ovdc':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.OVDC_LIST}
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_INFO,
                    RequestKey.OVDC_ID: tokens[4]
                }
            if method == RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_UPDATE,
                    RequestKey.OVDC_ID: tokens[4]
                }
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)
        if num_tokens == 6 and tokens[5] == 'compute-policies':
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_COMPUTE_POLICY_LIST,
                    RequestKey.OVDC_ID: tokens[4]
                }
            if method == RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_COMPUTE_POLICY_UPDATE,
                    RequestKey.OVDC_ID: tokens[4]
                }
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)

    elif operation_type == 'system':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.SYSTEM_INFO}
            if method == RequestMethod.PUT:
                return {_OPERATION_KEY: CseOperation.SYSTEM_UPDATE}
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)

    elif operation_type == 'template':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.TEMPLATE_LIST}
            raise CseRequestError(requests.codes.method_not_allowed,
                                  error_message=bad_method_msg)

    raise CseRequestError(requests.codes.not_found,
                          error_message=invalid_url_msg)
