# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
from urllib.parse import parse_qsl

from container_service_extension.exception_handler import handle_exception
from container_service_extension.exceptions import BadRequestError
from container_service_extension.exceptions import MethodNotAllowedRequestError
from container_service_extension.exceptions import NotFoundRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_handlers.cluster_handler as cluster_handler # noqa: E501
import container_service_extension.request_handlers.ovdc_handler as ovdc_handler # noqa: E501
import container_service_extension.request_handlers.system_handler as system_handler # noqa: E501
import container_service_extension.request_handlers.template_handler as template_handler # noqa: E501
from container_service_extension.server_constants import CseOperation
from container_service_extension.shared_constants import RequestKey
from container_service_extension.shared_constants import RequestMethod
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY


"""Process incoming requests

Following are the valid api endpoints.

GET /cse/clusters?org={org name}&vdc={vdc name}
POST /cse/clusters
GET /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
PUT /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
DELETE /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
GET /cse/cluster/{cluster name}/config?org={org name}&vdc={vdc name}
GET /cse/cluster/{cluster name}/upgrade-plan?org={org name}&vdc={vdc name}
POST /cse/cluster/{cluster name}/action/upgrade


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
    CseOperation.CLUSTER_UPGRADE_PLAN: cluster_handler.cluster_upgrade_plan,
    CseOperation.CLUSTER_UPGRADE: cluster_handler.cluster_upgrade,
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
        raise BadRequestError(error_message='CSE service is disabled. Contact'
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
    # remove None values from request payload
    data = {k: v for k, v in request_data.items() if v is not None}

    # extract out the authorization token
    auth_header = body['headers'].get('Authorization')
    if auth_header:
        tokens = auth_header.split(" ")
        if len(tokens) == 2 and tokens[0].lower() == 'bearer':
            tenant_auth_token = tokens[1]
            is_jwt_token = True
    if not auth_header:
        tenant_auth_token = body['headers'].get('x-vcloud-authorization')
        is_jwt_token = False

    # process the request
    body_content = \
        OPERATION_TO_HANDLER[operation](data, tenant_auth_token, is_jwt_token)

    if not (isinstance(body_content, (list, dict))):
        body_content = {RESPONSE_MESSAGE_KEY: str(body_content)}

    reply = {
        'status_code': operation.ideal_response_code,
        'body': body_content
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
    tokens = url.split('/')
    num_tokens = len(tokens)

    if num_tokens < 4:
        raise NotFoundRequestError()

    operation_type = tokens[3].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == 'cluster':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.CLUSTER_LIST}
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.CLUSTER_CREATE}
            raise MethodNotAllowedRequestError()
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
            raise MethodNotAllowedRequestError()
        if num_tokens == 6:
            if method == RequestMethod.GET:
                if tokens[5] == 'config':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_CONFIG,
                        RequestKey.CLUSTER_NAME: tokens[4]
                    }
                if tokens[5] == 'upgrade-plan':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_UPGRADE_PLAN,
                        RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise MethodNotAllowedRequestError()
        if num_tokens == 7:
            if method == RequestMethod.POST:
                if tokens[5] == 'action' and tokens[6] == 'upgrade':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_UPGRADE,
                        RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise MethodNotAllowedRequestError()
    elif operation_type == 'node':
        if num_tokens == 4:
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.NODE_CREATE}
            if method == RequestMethod.DELETE:
                return {_OPERATION_KEY: CseOperation.NODE_DELETE}
            raise MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.NODE_INFO,
                    RequestKey.NODE_NAME: tokens[4]
                }
            raise MethodNotAllowedRequestError()

    elif operation_type == 'ovdc':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.OVDC_LIST}
            raise MethodNotAllowedRequestError()
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
            raise MethodNotAllowedRequestError()
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
            raise MethodNotAllowedRequestError()

    elif operation_type == 'system':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.SYSTEM_INFO}
            if method == RequestMethod.PUT:
                return {_OPERATION_KEY: CseOperation.SYSTEM_UPDATE}
            raise MethodNotAllowedRequestError()

    elif operation_type == 'template':
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.TEMPLATE_LIST}
            raise MethodNotAllowedRequestError()

    raise NotFoundRequestError()
