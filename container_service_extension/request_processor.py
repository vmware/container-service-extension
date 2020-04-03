# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import importlib
import json
import sys
from urllib.parse import parse_qsl

from container_service_extension.exception_handler import handle_exception
from container_service_extension.exceptions import BadRequestError
from container_service_extension.exceptions import HandlerNotFoundError
from container_service_extension.exceptions import MethodNotAllowedRequestError
from container_service_extension.exceptions import NotFoundRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.server_constants import CSE_SERVICE_NAME
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

# Map each operation type (cluster, node, ovdc..) to corresponding handler module  # noqa: E501
OPERATION_TYPE_TO_HANDLER_MODULE = {
    OperationType.CLUSTER: {
        CSE_SERVICE_NAME: 'container_service_extension.request_handlers.vcd_cluster_handler',  # noqa: E501
        PKS_SERVICE_NAME: 'container_service_extension.request_handlers.pks_cluster_handler'   # noqa: E501
    },
    OperationType.NODE: {
        CSE_SERVICE_NAME: 'container_service_extension.request_handlers.vcd_cluster_handler'  # noqa: E501
    },
    OperationType.OVDC: 'container_service_extension.request_handlers.ovdc_handler',  # noqa: E501
    OperationType.SYSTEM: 'container_service_extension.request_handlers.system_handler',  # noqa: E501
    OperationType.TEMPLATE: 'container_service_extension.request_handlers.template_handler'  # noqa: E501
}

# Map each CSE operation to corresponding handler method
OPERATION_TO_HANDLER_METHOD = {
    CseOperation.CLUSTER_CONFIG: 'cluster_config',
    CseOperation.CLUSTER_CREATE: 'cluster_create',
    CseOperation.CLUSTER_DELETE: 'cluster_delete',
    CseOperation.CLUSTER_INFO: 'cluster_info',
    CseOperation.CLUSTER_LIST: 'cluster_list',
    CseOperation.CLUSTER_RESIZE: 'cluster_resize',
    CseOperation.CLUSTER_UPGRADE_PLAN: 'cluster_upgrade_plan',
    CseOperation.CLUSTER_UPGRADE: 'cluster_upgrade',
    CseOperation.NODE_CREATE: 'node_create',
    CseOperation.NODE_DELETE: 'node_delete',
    CseOperation.NODE_INFO: 'node_info',
    CseOperation.OVDC_UPDATE: 'ovdc_update',
    CseOperation.OVDC_INFO: 'ovdc_info',
    CseOperation.OVDC_LIST: 'ovdc_list',
    CseOperation.OVDC_COMPUTE_POLICY_LIST: 'ovdc_compute_policy_list',
    CseOperation.OVDC_COMPUTE_POLICY_UPDATE: 'ovdc_compute_policy_update',
    CseOperation.SYSTEM_INFO: 'system_info',
    CseOperation.SYSTEM_UPDATE: 'system_update',
    CseOperation.TEMPLATE_LIST: 'template_list',
}


_OPERATION_KEY = 'operation'
_OPERATION_TYPE = 'operation_type'
_SERVICE_NAME = 'service_name'


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
    tenant_auth_token = body['headers'].get('x-vcloud-authorization')
    is_jwt_token = False
    auth_header = body['headers'].get('Authorization')
    if auth_header:
        tokens = auth_header.split(" ")
        if len(tokens) == 2 and tokens[0].lower() == 'bearer':
            tenant_auth_token = tokens[1]
            is_jwt_token = True

    # select the right module and method to process the request
    operation_type = url_data[_OPERATION_TYPE]
    service_name = url_data.get(_SERVICE_NAME)
    handler_method = _get_handler_method(operation_type=operation_type,
                                         service_name=service_name,
                                         operation=operation)

    # Process the request
    body_content = handler_method(data, tenant_auth_token, is_jwt_token)

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

    url_data = {_OPERATION_TYPE: operation_type}
    if operation_type == OperationType.CLUSTER:
        url_data[_SERVICE_NAME] = tokens[2]
        if num_tokens == 4:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.CLUSTER_LIST
                return url_data
            if method == RequestMethod.POST:
                url_data[_OPERATION_KEY] = CseOperation.CLUSTER_CREATE
                return url_data
            raise MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.CLUSTER_INFO
                url_data[RequestKey.CLUSTER_NAME] = tokens[4]
                return url_data
            if method == RequestMethod.PUT:
                url_data[_OPERATION_KEY] = CseOperation.CLUSTER_RESIZE
                url_data[RequestKey.CLUSTER_NAME] = tokens[4]
                return url_data
            if method == RequestMethod.DELETE:
                url_data[_OPERATION_KEY] = CseOperation.CLUSTER_DELETE
                url_data[RequestKey.CLUSTER_NAME] = tokens[4]
                return url_data
            raise MethodNotAllowedRequestError()
        if num_tokens == 6:
            if method == RequestMethod.GET:
                if tokens[5] == 'config':
                    url_data[_OPERATION_KEY] = CseOperation.CLUSTER_CONFIG
                    url_data[RequestKey.CLUSTER_NAME] = tokens[4]
                    return url_data
                if tokens[5] == 'upgrade-plan':
                    url_data[_OPERATION_KEY] = CseOperation.CLUSTER_UPGRADE_PLAN  # noqa: E501
                    url_data[RequestKey.CLUSTER_NAME] = tokens[4]
                    return url_data
            raise MethodNotAllowedRequestError()
        if num_tokens == 7:
            if method == RequestMethod.POST:
                if tokens[5] == 'action' and tokens[6] == 'upgrade':
                    url_data[_OPERATION_KEY] = CseOperation.CLUSTER_UPGRADE
                    url_data[RequestKey.CLUSTER_NAME] = tokens[4]
                    return url_data
            raise MethodNotAllowedRequestError()
    elif operation_type == OperationType.NODE:
        url_data[_SERVICE_NAME] = tokens[2]
        if num_tokens == 4:
            if method == RequestMethod.POST:
                url_data[_OPERATION_KEY] = CseOperation.NODE_CREATE
                return url_data
            if method == RequestMethod.DELETE:
                url_data[_OPERATION_KEY] = CseOperation.NODE_DELETE
                return url_data
            raise MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.NODE_INFO
                url_data[RequestKey.NODE_NAME] = tokens[4]
                return url_data

            raise MethodNotAllowedRequestError()

    elif operation_type == OperationType.OVDC:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.OVDC_LIST
                return url_data
            raise MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.OVDC_INFO
                url_data[RequestKey.OVDC_ID] = tokens[4]
                return url_data
            if method == RequestMethod.PUT:
                url_data[_OPERATION_KEY] = CseOperation.OVDC_UPDATE
                url_data[RequestKey.OVDC_ID] = tokens[4]
                return url_data

            raise MethodNotAllowedRequestError()
        if num_tokens == 6 and tokens[5] == 'compute-policies':
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.OVDC_COMPUTE_POLICY_LIST  # noqa: E501
                url_data[RequestKey.OVDC_ID] = tokens[4]
                return url_data
            if method == RequestMethod.PUT:
                url_data[_OPERATION_KEY] = CseOperation.OVDC_COMPUTE_POLICY_UPDATE  # noqa: E501
                url_data[RequestKey.OVDC_ID] = tokens[4]
                return url_data

            raise MethodNotAllowedRequestError()

    elif operation_type == OperationType.SYSTEM:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.SYSTEM_INFO
                return url_data
            if method == RequestMethod.PUT:
                url_data[_OPERATION_KEY] = CseOperation.SYSTEM_UPDATE
                return url_data
            raise MethodNotAllowedRequestError()

    elif operation_type == OperationType.TEMPLATE:
        if num_tokens == 4:
            if method == RequestMethod.GET:
                url_data[_OPERATION_KEY] = CseOperation.TEMPLATE_LIST
                return url_data
            raise MethodNotAllowedRequestError()

    raise NotFoundRequestError()


def _get_handler_method(operation_type, service_name, operation):
    """Get the handler method for given operation_type, service and operation.

    :param str operation_type: type of operation like cluster, node, ovdc
    :param str service_name: name of service like cse, pks
    :param <enum 'CseOperation'> operation: key that defines the operation

    :return: reference to the handler method
    :rtype: <class 'function'>

    :raises: NotFoundRequestError
    """
    try:
        if service_name:
            handler_module_name = OPERATION_TYPE_TO_HANDLER_MODULE[operation_type][service_name]  # noqa: E501
        else:
            handler_module_name = OPERATION_TYPE_TO_HANDLER_MODULE[operation_type]  # noqa: E501
        handler_module = importlib.import_module(handler_module_name)
        handler_method = getattr(handler_module, OPERATION_TO_HANDLER_METHOD[operation])  # noqa: E501
        return handler_method
    except Exception as err:
        LOGGER.debug(f"Error on getting handler method: {str(err)}")
        raise HandlerNotFoundError()
