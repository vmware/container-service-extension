# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
from urllib.parse import parse_qsl

import container_service_extension.def_.utils as def_utils
from container_service_extension.exception_handler import handle_exception
import container_service_extension.exceptions as e
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_context as ctx
import container_service_extension.request_handlers.native_cluster_handler as native_cluster_handler  # noqa: E501
import container_service_extension.request_handlers.ovdc_handler as ovdc_handler  # noqa: E501
import container_service_extension.request_handlers.pks_cluster_handler as pks_cluster_handler  # noqa: E501
import container_service_extension.request_handlers.system_handler as system_handler  # noqa: E501
import container_service_extension.request_handlers.template_handler as template_handler  # noqa: E501 E501
import container_service_extension.request_handlers.v35.def_cluster_handler as def_handler # noqa: E501
from container_service_extension.server_constants import CseOperation
from container_service_extension.server_constants import PKS_SERVICE_NAME
from container_service_extension.shared_constants import OperationType
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

GET /cse/internal/clusters
Entities can be filtered by nested properties as defined per the schema
GET /cse/internal/clusters?entity.kind={native}&entity.metadata.org_name={org name}
POST /cse/internal/clusters
GET /cse/internal/cluster/{cluster id}
PUT /cse/internal/cluster/{cluster id}
DELETE /cse/internal/cluster/{cluster id}
GET /cse/internal/cluster/{cluster id}/config
GET /cse/internal/cluster/{cluster id}/upgrade-plan
POST /cse/internal/cluster/{cluster id}/action/upgrade

# Yet to be finalized.
POST /cse/internal/nodes
DELETE /cse/internal/nodes
GET /cse/internal/{cluster id}/node

GET /cse/ovdcs
GET /cse/ovdc/{ovdc id}
PUT /cse/ovdc/{ovdc id}
GET /cse/ovdc/{ovdc_id}/compute-policies
PUT /cse/ovdc/{ovdc_id}/compute-policies

GET /cse/system
PUT /cse/system

GET /cse/template

GET /pks/clusters?org={org name}&vdc={vdc name}
POST /pks/clusters
GET /pks/cluster/{cluster name}?org={org name}&vdc={vdc name}
PUT /pks/cluster/{cluster name}?org={org name}&vdc={vdc name}
DELETE /pks/cluster/{cluster name}?org={org name}&vdc={vdc name}
GET /pks/cluster/{cluster name}/config?org={org name}&vdc={vdc name}
"""  # noqa: E501

OPERATION_TO_HANDLER = {
    CseOperation.CLUSTER_CONFIG: native_cluster_handler.cluster_config,
    CseOperation.CLUSTER_CREATE: native_cluster_handler.cluster_create,
    CseOperation.CLUSTER_DELETE: native_cluster_handler.cluster_delete,
    CseOperation.CLUSTER_INFO: native_cluster_handler.cluster_info,
    CseOperation.CLUSTER_LIST: native_cluster_handler.cluster_list,
    CseOperation.CLUSTER_RESIZE: native_cluster_handler.cluster_resize,
    CseOperation.CLUSTER_UPGRADE_PLAN: native_cluster_handler.cluster_upgrade_plan,  # noqa: E501
    CseOperation.CLUSTER_UPGRADE: native_cluster_handler.cluster_upgrade,
    CseOperation.NODE_CREATE: native_cluster_handler.node_create,
    CseOperation.NODE_DELETE: native_cluster_handler.node_delete,
    CseOperation.NODE_INFO: native_cluster_handler.node_info,
    CseOperation.OVDC_UPDATE: ovdc_handler.ovdc_update,
    CseOperation.OVDC_INFO: ovdc_handler.ovdc_info,
    CseOperation.OVDC_LIST: ovdc_handler.ovdc_list,
    CseOperation.OVDC_COMPUTE_POLICY_LIST: ovdc_handler.ovdc_compute_policy_list,  # noqa: E501
    CseOperation.OVDC_COMPUTE_POLICY_UPDATE: ovdc_handler.ovdc_compute_policy_update,  # noqa: E501
    CseOperation.SYSTEM_INFO: system_handler.system_info,
    CseOperation.SYSTEM_UPDATE: system_handler.system_update,
    CseOperation.TEMPLATE_LIST: template_handler.template_list,

    CseOperation.PKS_CLUSTER_CONFIG: pks_cluster_handler.cluster_config,
    CseOperation.PKS_CLUSTER_CREATE: pks_cluster_handler.cluster_create,
    CseOperation.PKS_CLUSTER_DELETE: pks_cluster_handler.cluster_delete,
    CseOperation.PKS_CLUSTER_INFO: pks_cluster_handler.cluster_info,
    CseOperation.PKS_CLUSTER_LIST: pks_cluster_handler.cluster_list,
    CseOperation.PKS_CLUSTER_RESIZE: pks_cluster_handler.cluster_resize
}

_OPERATION_KEY = 'operation'


def _is_def_endpoint(url: str):
    tokens = url.split('/')
    return tokens[3] == def_utils.DEF_END_POINT_DISCRIMINATOR


@handle_exception
def process_request(body):
    LOGGER.debug(f"Incoming request body: {json.dumps(body)}")
    http_verb = body['method']
    url = body['requestUri']
    # create request data dict from request body data
    request_data = {}
    request_body = None
    if len(body['body']) > 0:
        raw_body = base64.b64decode(body['body']).decode(sys.getfilesystemencoding())  # noqa: E501
        request_body = json.loads(raw_body)
        request_data.update(request_body)
        LOGGER.debug(f"request body: {request_data}")
    # update request data dict with query params data
    query_params = None
    if body['queryString']:
        query_params = dict(parse_qsl(body['queryString']))
        request_data.update(query_params)
        LOGGER.debug(f"query parameters: {query_params}")

    # extract out the authorization token
    tenant_auth_token = body['headers'].get('x-vcloud-authorization')
    is_jwt_token = False
    auth_header = body['headers'].get('Authorization')
    if auth_header:
        tokens = auth_header.split(" ")
        if len(tokens) == 2 and tokens[0].lower() == 'bearer':
            tenant_auth_token = tokens[1]
            is_jwt_token = True

    # process the request
    req_ctx = ctx.RequestContext(tenant_auth_token, is_jwt=is_jwt_token,
                                 request_body=request_body,
                                 request_url=url,
                                 request_verb=http_verb,
                                 request_query_params=query_params,
                                 request_id=body['id'])

    is_def_request = def_utils.is_def_supported_by_cse_server() and _is_def_endpoint(body['requestUri'])  # noqa: E501

    try:
        if is_def_request:
            body_content, operation = def_handler.invoke(req_ctx)
        else:
            body_content, operation = _invoke_legacy_handlers(req_ctx,
                                                              request_data)
    finally:
        if not req_ctx.is_async:
            req_ctx.end()

    if not isinstance(body_content, (list, dict)):
        body_content = {RESPONSE_MESSAGE_KEY: str(body_content)}
    response = {
        'status_code': operation.ideal_response_code,
        'body': body_content,
    }
    LOGGER.debug(f"Outgoing response: {str(response)}")
    return response


def _invoke_legacy_handlers(req_ctx: ctx.RequestContext, request_data: dict):
    from container_service_extension.service import Service
    url_data = _get_url_data(req_ctx.verb, req_ctx.url)
    operation = url_data[_OPERATION_KEY]
    # update request spec with operation specific data in the url
    request_data.update(url_data)
    # remove None values from request payload
    data = {k: v for k, v in request_data.items() if v is not None}
    # check if server is disabled
    if operation not in (
            CseOperation.SYSTEM_INFO, CseOperation.SYSTEM_UPDATE) \
            and not Service().is_running():
        raise e.BadRequestError(
            error_message='CSE service is disabled. '
                          'Contact the System Administrator.')
    body_content = OPERATION_TO_HANDLER[operation](data, req_ctx)
    return body_content, operation


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
    #url = url.replace(f"/{def_utils.DEF_END_POINT_DISCRIMINATOR}", '')
    tokens = url.split('/')
    num_tokens = len(tokens)

    if num_tokens < 4:
        raise e.NotFoundRequestError()

    if tokens[2] == PKS_SERVICE_NAME:
        return _get_pks_url_data(method, url)

    operation_type = tokens[3].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == OperationType.CLUSTER:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.CLUSTER_LIST}
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.CLUSTER_CREATE}
            raise e.MethodNotAllowedRequestError()
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
            raise e.MethodNotAllowedRequestError()
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
            raise e.MethodNotAllowedRequestError()
        if num_tokens == 7:
            if method == RequestMethod.POST:
                if tokens[5] == 'action' and tokens[6] == 'upgrade':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_UPGRADE,
                        RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise e.MethodNotAllowedRequestError()
    elif operation_type == OperationType.NODE:
        if num_tokens == 4:
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.NODE_CREATE}
            if method == RequestMethod.DELETE:
                return {_OPERATION_KEY: CseOperation.NODE_DELETE}
            raise e.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.NODE_INFO,
                    RequestKey.NODE_NAME: tokens[4]
                }
            raise e.MethodNotAllowedRequestError()

    elif operation_type == OperationType.OVDC:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.OVDC_LIST}
            raise e.MethodNotAllowedRequestError()
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
            raise e.MethodNotAllowedRequestError()
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
            raise e.MethodNotAllowedRequestError()

    elif operation_type == OperationType.SYSTEM:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.SYSTEM_INFO}
            if method == RequestMethod.PUT:
                return {_OPERATION_KEY: CseOperation.SYSTEM_UPDATE}
            raise e.MethodNotAllowedRequestError()

    elif operation_type == OperationType.TEMPLATE:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.TEMPLATE_LIST}
            raise e.MethodNotAllowedRequestError()

    raise e.NotFoundRequestError()


def _get_pks_url_data(method, url):
    """Parse url and http method to get desired PKS operation and url data.

    Returns a data dictionary with 'operation' key and also any relevant url
    data.

    :param RequestMethod method:
    :param str url:

    :rtype: dict
    """
    tokens = url.split('/')
    num_tokens = len(tokens)
    operation_type = tokens[3].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == OperationType.CLUSTER:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.PKS_CLUSTER_LIST}
            if method == RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.PKS_CLUSTER_CREATE}
            raise e.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.PKS_CLUSTER_INFO,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.PKS_CLUSTER_RESIZE,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == RequestMethod.DELETE:
                return {
                    _OPERATION_KEY: CseOperation.PKS_CLUSTER_DELETE,
                    RequestKey.CLUSTER_NAME: tokens[4]
                }
            raise e.MethodNotAllowedRequestError()
        if num_tokens == 6:
            if method == RequestMethod.GET:
                if tokens[5] == 'config':
                    return {
                        _OPERATION_KEY: CseOperation.PKS_CLUSTER_CONFIG,
                        RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise e.MethodNotAllowedRequestError()
    raise e.MethodNotAllowedRequestError()
