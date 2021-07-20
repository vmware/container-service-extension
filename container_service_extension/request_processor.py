# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
from urllib.parse import parse_qsl

from pyvcloud.vcd.client import ApiVersion as VcdApiVersion

from container_service_extension.exception_handler import handle_exception
import container_service_extension.exceptions as cse_exception
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.operation_context as ctx
import container_service_extension.request_handlers.native_cluster_handler as native_cluster_handler  # noqa: E501
import container_service_extension.request_handlers.ovdc_handler as ovdc_handler  # noqa: E501
import container_service_extension.request_handlers.pks_cluster_handler as pks_cluster_handler  # noqa: E501
import container_service_extension.request_handlers.pks_ovdc_handler as pks_ovdc_handler  # noqa: E501
import container_service_extension.request_handlers.system_handler as system_handler  # noqa: E501
import container_service_extension.request_handlers.template_handler as template_handler  # noqa: E501 E501
import container_service_extension.request_handlers.v35.def_cluster_handler as v35_cluster_handler # noqa: E501
import container_service_extension.request_handlers.v35.ovdc_handler as v35_ovdc_handler # noqa: E501
from container_service_extension.server_constants import CseOperation
import container_service_extension.shared_constants as shared_constants
import container_service_extension.utils as utils


"""Process incoming requests

Following are the valid api endpoints.

API version 33.0 and 34.0
--------------------------
GET /cse/nativeclusters
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
GET /cse/orgvdcs
GET /cse/ovdc/{ovdc id}
PUT /cse/ovdc/{ovdc id}
GET /cse/ovdc/{ovdc_id}/compute-policies
PUT /cse/ovdc/{ovdc_id}/compute-policies


API version 35.0
----------------
GET /cse/3.0/nativeclusters
GET /cse/3.0/clusters
Entities can be filtered by nested properties as defined per the schema
GET /cse/3.0/clusters?entity.kind={native}&entity.metadata.org_name={org name}
POST /cse/3.0/clusters
GET /cse/3.0/cluster/{cluster id}
PUT /cse/3.0/cluster/{cluster id}
DELETE /cse/3.0/cluster/{cluster id}
GET /cse/3.0/cluster/{cluster id}/config
GET /cse/3.0/cluster/{cluster id}/upgrade-plan
POST /cse/3.0/cluster/{cluster id}/action/upgrade
DELETE /cse/3.0/cluster/{cluster id}/nfs/{node-name}

GET /cse/3.0/ovdcs  (for response which is not paginated.
                     This will be deprecated soon)
GET /cse/3.0/orgvdcs  (for paginated response)
GET /cse/3.0/ovdc/{ovdc_id}
PUT /cse/3.0/ovdc/{ovdc_id}


Not dependent on API version
----------------------------
GET /cse/system
PUT /cse/system

GET /cse/templates

GET /pks/clusters?org={org name}&vdc={vdc name}
POST /pks/clusters
GET /pks/cluster/{cluster name}?org={org name}&vdc={vdc name}
PUT /pks/cluster/{cluster name}?org={org name}&vdc={vdc name}
DELETE /pks/cluster/{cluster name}?org={org name}&vdc={vdc name}
GET /pks/cluster/{cluster name}/config?org={org name}&vdc={vdc name}
GET /pks/ovdcs  (This endpoint returns non paginated response)
GET /pks/orgvdcs  (This endpoint returns paginated response)
GET /pks/ovdc/{ovdc_id}
PUT /pks/ovdc/{ovdc_id}
"""  # noqa: E501

OPERATION_TO_HANDLER = {
    CseOperation.CLUSTER_CONFIG: native_cluster_handler.cluster_config,
    CseOperation.CLUSTER_CREATE: native_cluster_handler.cluster_create,
    CseOperation.CLUSTER_DELETE: native_cluster_handler.cluster_delete,
    CseOperation.CLUSTER_INFO: native_cluster_handler.cluster_info,
    CseOperation.NATIVE_CLUSTER_LIST: native_cluster_handler.native_cluster_list,  # noqa: E501
    CseOperation.CLUSTER_LIST: native_cluster_handler.cluster_list,
    CseOperation.CLUSTER_RESIZE: native_cluster_handler.cluster_resize,
    CseOperation.CLUSTER_UPGRADE_PLAN: native_cluster_handler.cluster_upgrade_plan,  # noqa: E501
    CseOperation.CLUSTER_UPGRADE: native_cluster_handler.cluster_upgrade,
    CseOperation.NODE_CREATE: native_cluster_handler.node_create,
    CseOperation.NODE_DELETE: native_cluster_handler.node_delete,
    CseOperation.NODE_INFO: native_cluster_handler.node_info,

    CseOperation.V35_CLUSTER_CONFIG: v35_cluster_handler.cluster_config,
    CseOperation.V35_CLUSTER_CREATE: v35_cluster_handler.cluster_create,
    CseOperation.V35_CLUSTER_DELETE: v35_cluster_handler.cluster_delete,
    CseOperation.V35_CLUSTER_INFO: v35_cluster_handler.cluster_info,
    CseOperation.V35_NATIVE_CLUSTER_LIST: v35_cluster_handler.native_cluster_list,  # noqa: E501
    CseOperation.V35_CLUSTER_LIST: v35_cluster_handler.cluster_list,
    CseOperation.V35_CLUSTER_RESIZE: v35_cluster_handler.cluster_resize,
    CseOperation.V35_CLUSTER_UPGRADE_PLAN: v35_cluster_handler.cluster_upgrade_plan,  # noqa: E501
    CseOperation.V35_CLUSTER_UPGRADE: v35_cluster_handler.cluster_upgrade,
    CseOperation.V35_NODE_DELETE: v35_cluster_handler.nfs_node_delete,
    CseOperation.V35_NODE_CREATE: v35_cluster_handler.node_create,
    CseOperation.V35_NODE_INFO: v35_cluster_handler.node_info,

    CseOperation.V35_OVDC_LIST: v35_ovdc_handler.ovdc_list,
    CseOperation.V35_ORG_VDC_LIST: v35_ovdc_handler.org_vdc_list,
    CseOperation.V35_OVDC_INFO: v35_ovdc_handler.ovdc_info,
    CseOperation.V35_OVDC_UPDATE: v35_ovdc_handler.ovdc_update,

    CseOperation.OVDC_UPDATE: ovdc_handler.ovdc_update,
    CseOperation.OVDC_INFO: ovdc_handler.ovdc_info,
    CseOperation.OVDC_LIST: ovdc_handler.ovdc_list,
    CseOperation.ORG_VDC_LIST: ovdc_handler.org_vdc_list,
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
    CseOperation.PKS_CLUSTER_RESIZE: pks_cluster_handler.cluster_resize,
    CseOperation.PKS_OVDC_LIST: pks_ovdc_handler.ovdc_list,
    CseOperation.PKS_ORG_VDC_LIST: pks_ovdc_handler.org_vdc_list,
    CseOperation.PKS_OVDC_INFO: pks_ovdc_handler.ovdc_info,
    CseOperation.PKS_OVDC_UPDATE: pks_ovdc_handler.ovdc_update
}

_OPERATION_KEY = 'operation'


def _parse_accept_header(accept_header: str):
    """Parse accept headers and select one that fits CSE.

    CSE is looking for headers like
    * application/json;version=33.0
    * *;version=33.0
    * */*;version=33.0
    * application/*+json;version=33.0
    If multiple matches are found, Will pick the first match.

    :param str accept_header: value of 'Accept' header sent by client

    :returns: accept header that is servicable by CSE

    :raises NotAcceptableRequestError: If none of the accept headers matches
        what CSE is looking for.
    """
    accept_header = accept_header.lower()
    accept_headers = accept_header.split(",")
    processed_headers = {}

    for header in accept_headers:
        # break the header into a tuple that follows the following structure
        # "application/json;version=33.0" ->
        #     ('application', 'json', 'version', '33.0')
        # "application/*;version=33.0" ->
        #     ('application', '*', 'version', '33.0')
        # "application/*+json;version=33.0" ->
        #     ('application', '*+json', 'version', '33.0')
        # "*/*;version=33.0" -> ('*', '*', 'version', '33.0')
        # "*;version=33.0" -> ('*', '', 'version', '33.0')

        tokens = header.split(';')
        application_fragment = ''
        version_fragment = ''
        if len(tokens) >= 1:
            application_fragment = tokens[0]
        if len(tokens) >= 2:
            version_fragment = tokens[1]

        tokens = application_fragment.split("/")
        val0 = ''
        val1 = ''
        if len(tokens) >= 1:
            val0 = tokens[0]
        if len(tokens) >= 2:
            val1 = tokens[1]

        tokens = version_fragment.split("=")
        val2 = ''
        val3 = ''
        if len(tokens) >= 1:
            val2 = tokens[0]
        if len(tokens) >= 2:
            val3 = tokens[1]

        processed_headers[header] = (val0, val1, val2, val3)

    selected_header = None
    for header, value in processed_headers.items():
        val0 = value[0]
        val1 = value[1]
        val2 = value[2]

        # * -> */*
        if val0 == '*' and not val1:
            val1 = '*'

        if val0 == '*':
            val0 = 'application'

        # *+json -> json
        val1 = val1.replace('*+', '')
        if val1 == '*':
            val1 = 'json'

        if (val0, val1, val2) == ('application', 'json', 'version'):
            selected_header = header
            break

    if not selected_header:
        raise cse_exception.NotAcceptableRequestError(
            error_message="CSE can only serve response as json.")

    return selected_header


def _get_api_version_from_accept_header(api_version_header: str):
    api_version = '0.0'
    if api_version_header:
        tokens = api_version_header.split(";")
        if len(tokens) == 2:
            tokens = tokens[1].split("=")
            if len(tokens) == 2:
                api_version = tokens[1]
    return api_version


@handle_exception
def process_request(message):
    from container_service_extension.service import Service
    LOGGER.debug(f"Incoming request message: {json.dumps(message)}")

    api_version_header = _parse_accept_header(
        accept_header=message['headers'].get('Accept'))
    api_version = _get_api_version_from_accept_header(
        api_version_header=api_version_header)
    url_data = _get_url_data(method=message['method'],
                             url=message['requestUri'],
                             api_version=api_version)  # noqa: E501
    operation = url_data[_OPERATION_KEY]

    # Check api version and if server is disabled or not
    # /system operations are excluded from these checks
    if operation not in (CseOperation.SYSTEM_INFO, CseOperation.SYSTEM_UPDATE):
        if not Service().is_running():
            raise cse_exception.BadRequestError(
                error_message='CSE service is disabled. '
                              'Contact the System Administrator.')
        else:
            server_api_version = utils.get_server_api_version()
            if api_version != server_api_version:
                raise cse_exception.NotAcceptableRequestError(
                    error_message="Invalid api version specified. Expected "
                                  f"api version '{server_api_version}'.")

    # create request data dict from incoming message data
    request_data = {}
    is_cse_3_0_request = _is_cse_3_0_endpoint(message['requestUri'])
    if len(message['body']) > 0:
        raw_body = base64.b64decode(message['body']).decode(sys.getfilesystemencoding())  # noqa: E501
        request_body = json.loads(raw_body)
        if is_cse_3_0_request:
            request_data[shared_constants.RequestKey.V35_SPEC] = request_body
        else:
            request_data.update(request_body)
        LOGGER.debug(f"request body: {request_data}")
    # update request data dict with query params data
    if message['queryString']:
        query_params = dict(parse_qsl(message['queryString']))
        if is_cse_3_0_request:
            request_data[shared_constants.RequestKey.V35_QUERY] = query_params
        else:
            request_data.update(query_params)
        LOGGER.debug(f"query parameters: {query_params}")
    # update request spec with operation specific data in the url
    request_data.update(url_data)
    # remove None values from request payload
    data = {k: v for k, v in request_data.items() if v is not None}
    # extract out the authorization token
    tenant_auth_token = message['headers'].get('x-vcloud-authorization')
    is_jwt_token = False
    auth_header = message['headers'].get('Authorization')
    if auth_header:
        tokens = auth_header.split(" ")
        if len(tokens) == 2 and tokens[0].lower() == 'bearer':
            tenant_auth_token = tokens[1]
            is_jwt_token = True

    # create operation context
    operation_ctx = ctx.OperationContext(tenant_auth_token,
                                         is_jwt=is_jwt_token,
                                         request_id=message['id'])

    try:
        body_content = OPERATION_TO_HANDLER[operation](data, operation_ctx)
    finally:
        if not operation_ctx.is_async:
            operation_ctx.end()

    if not isinstance(body_content, (list, dict)):
        body_content = \
            {shared_constants.RESPONSE_MESSAGE_KEY: str(body_content)}
    response = {
        'status_code': operation.ideal_response_code,
        'body': body_content,
    }
    LOGGER.debug(f"Outgoing response: {str(response)}")
    return response


def _is_cse_3_0_endpoint(url: str):
    tokens = url.split('/')
    if len(tokens) >= 4:
        return tokens[3] == shared_constants.CSE_3_0_URL_FRAGMENT
    return False


def _is_pks_endpoint(url: str):
    tokens = url.split('/')
    if len(tokens) >= 3:
        return tokens[2] == shared_constants.PKS_URL_FRAGMENT
    return False


def _get_url_data(method: str, url: str, api_version: str):
    """Parse url and http method to get desired CSE operation and url data.

    Url is processed like a tree to find the desired operation as fast as
    possible. These explicit checks allow any invalid urls or http methods to
    fall through and trigger the appropriate exception.

    Returns a data dictionary with 'operation' key and also any relevant url
    data.

    :param shared_constants.RequestMethod method:
    :param str url:

    :rtype: dict
    """
    tokens = url.split('/')
    num_tokens = len(tokens)

    if num_tokens < 4:
        raise cse_exception.NotFoundRequestError()

    if _is_pks_endpoint(url):
        return _get_pks_url_data(method, url)

    if _is_cse_3_0_endpoint(url):
        return _get_v35_url_data(method, url, api_version)

    return _get_legacy_url_data(method, url, api_version)


def _get_pks_url_data(method: str, url: str):
    """Parse url and http method to get desired PKS operation and url data.

    Returns a data dictionary with 'operation' key and also any relevant url
    data.

    :param shared_constants.RequestMethod method:
    :param str url:

    :rtype: dict
    """
    tokens = url.split('/')
    num_tokens = len(tokens)

    operation_type = tokens[3].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == shared_constants.OperationType.CLUSTER:
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.PKS_CLUSTER_LIST}
            if method == shared_constants.RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.PKS_CLUSTER_CREATE}
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == shared_constants.RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.PKS_CLUSTER_INFO,
                    shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == shared_constants.RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.PKS_CLUSTER_RESIZE,
                    shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == shared_constants.RequestMethod.DELETE:
                return {
                    _OPERATION_KEY: CseOperation.PKS_CLUSTER_DELETE,
                    shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                }
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 6:
            if method == shared_constants.RequestMethod.GET:
                if tokens[5] == 'config':
                    return {
                        _OPERATION_KEY: CseOperation.PKS_CLUSTER_CONFIG,
                        shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise cse_exception.MethodNotAllowedRequestError()
    elif operation_type == shared_constants.OperationType.OVDC:
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.PKS_OVDC_LIST}
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == shared_constants.RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.PKS_OVDC_INFO,
                    shared_constants.RequestKey.OVDC_ID: tokens[4]
                }
            if method == shared_constants.RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.PKS_OVDC_UPDATE,
                    shared_constants.RequestKey.OVDC_ID: tokens[4]
                }
            raise cse_exception.MethodNotAllowedRequestError()
    elif operation_type == shared_constants.OperationType.ORG_VDCS:
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.PKS_ORG_VDC_LIST}
            raise cse_exception.MethodNotAllowedRequestError()
    raise cse_exception.NotFoundRequestError()


def _get_v35_url_data(method: str, url: str, api_version: str):
    """Parse url and http method to get CSE v35 data.

    Returns a dictionary with operation and url data.

    :param RequestMethod method: http verb
    :param str url: http url

    :rtype: dict
    """
    if api_version != VcdApiVersion.VERSION_35.value:
        raise cse_exception.NotFoundRequestError()

    tokens = url.split('/')
    num_tokens = len(tokens)

    if num_tokens < 5:
        raise cse_exception.NotFoundRequestError()

    operation_type = tokens[4].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == shared_constants.OperationType.CLUSTER:
        return _get_v35_cluster_url_data(method, tokens)

    if operation_type == shared_constants.OperationType.NATIVE_CLUSTER:
        return _get_v35_native_cluster_url_data(method, tokens)

    if operation_type == shared_constants.OperationType.OVDC:
        return _get_v35_ovdc_url_data(method, tokens)

    if operation_type == shared_constants.OperationType.ORG_VDCS:
        return _get_v35_org_vdc_url_data(method, tokens)

    raise cse_exception.NotFoundRequestError()


def _get_v35_native_cluster_url_data(method: str, tokens: list):
    """Parse tokens from url and http method to get v35 native cluster data.

    Returns a dictionary with operation and url data.

    :param RequestMethod method: http verb
    :param str[] tokens: http url

    :rtype: dict
    """
    num_tokens = len(tokens)
    if num_tokens == 5:
        if method == shared_constants.RequestMethod.GET:
            return {_OPERATION_KEY: CseOperation.V35_NATIVE_CLUSTER_LIST}
        raise cse_exception.MethodNotAllowedRequestError()


def _get_v35_cluster_url_data(method: str, tokens: list):
    """Parse tokens from url and http method to get v35 cluster specific data.

    Returns a dictionary with operation and url data.

    :param RequestMethod method: http verb
    :param str[] tokens: http url

    :rtype: dict
    """
    num_tokens = len(tokens)
    if num_tokens == 5:
        if method == shared_constants.RequestMethod.GET:
            return {_OPERATION_KEY: CseOperation.V35_CLUSTER_LIST}
        if method == shared_constants.RequestMethod.POST:
            return {_OPERATION_KEY: CseOperation.V35_CLUSTER_CREATE}
        raise cse_exception.MethodNotAllowedRequestError()
    if num_tokens == 6:
        if method == shared_constants.RequestMethod.GET:
            return {
                _OPERATION_KEY: CseOperation.V35_CLUSTER_INFO,
                shared_constants.RequestKey.CLUSTER_ID: tokens[5]
            }
        if method == shared_constants.RequestMethod.PUT:
            return {
                _OPERATION_KEY: CseOperation.V35_CLUSTER_RESIZE,
                shared_constants.RequestKey.CLUSTER_ID: tokens[5]
            }
        if method == shared_constants.RequestMethod.DELETE:
            return {
                _OPERATION_KEY: CseOperation.V35_CLUSTER_DELETE,
                shared_constants.RequestKey.CLUSTER_ID: tokens[5]
            }
        raise cse_exception.MethodNotAllowedRequestError()
    if num_tokens == 7:
        if method == shared_constants.RequestMethod.GET:
            if tokens[6] == 'config':
                return {
                    _OPERATION_KEY: CseOperation.V35_CLUSTER_CONFIG,
                    shared_constants.RequestKey.CLUSTER_ID: tokens[5]
                }
            if tokens[6] == 'upgrade-plan':
                return {
                    _OPERATION_KEY: CseOperation.V35_CLUSTER_UPGRADE_PLAN,  # noqa: E501
                    shared_constants.RequestKey.CLUSTER_ID: tokens[5]
                }
        raise cse_exception.MethodNotAllowedRequestError()
    if num_tokens == 8:
        if method == shared_constants.RequestMethod.POST:
            if tokens[6] == 'action' and tokens[7] == 'upgrade':
                return {
                    _OPERATION_KEY: CseOperation.V35_CLUSTER_UPGRADE,
                    shared_constants.RequestKey.CLUSTER_ID: tokens[5]
                }
        if method == shared_constants.RequestMethod.DELETE:
            if tokens[6] == 'nfs':
                return {
                    _OPERATION_KEY: CseOperation.V35_NODE_DELETE,
                    shared_constants.RequestKey.CLUSTER_ID: tokens[5],
                    shared_constants.RequestKey.NODE_NAME: tokens[7]
                }
        raise cse_exception.MethodNotAllowedRequestError()


def _get_v35_ovdc_url_data(method: str, tokens: list):
    """Parse tokens from url and http method to get v35 ovdc specific data.

    Returns a dictionary with operation and url data.

    :param shared_constants.RequestMethod method: http verb
    :param str[] tokens: http url

    :rtype: dict
    """
    num_tokens = len(tokens)
    if num_tokens == 5:
        if method == shared_constants.RequestMethod.GET:
            return {_OPERATION_KEY: CseOperation.V35_OVDC_LIST}
        raise cse_exception.MethodNotAllowedRequestError()
    if num_tokens == 6:
        if method == shared_constants.RequestMethod.PUT:
            return {
                _OPERATION_KEY: CseOperation.V35_OVDC_UPDATE,
                shared_constants.RequestKey.OVDC_ID: tokens[5]
            }
        if method == shared_constants.RequestMethod.GET:
            return {
                _OPERATION_KEY: CseOperation.V35_OVDC_INFO,
                shared_constants.RequestKey.OVDC_ID: tokens[5]
            }
        raise cse_exception.MethodNotAllowedRequestError()


def _get_v35_org_vdc_url_data(method: str, tokens: list):
    """Parse tokens from url and http method to get v35 ovdc specific data.

    Returns a dictionary with operation and url data.

    :param shared_constants.RequestMethod method: http verb
    :param str[] tokens: http url

    :rtype: dict
    """
    num_tokens = len(tokens)
    if num_tokens == 5:
        if method == shared_constants.RequestMethod.GET:
            return {_OPERATION_KEY: CseOperation.V35_ORG_VDC_LIST}
        raise cse_exception.MethodNotAllowedRequestError()
    raise cse_exception.NotFoundRequestError()


def _get_legacy_url_data(method: str, url: str, api_version: str):
    tokens = url.split('/')
    num_tokens = len(tokens)

    operation_type = tokens[3].lower()
    if operation_type.endswith('s'):
        operation_type = operation_type[:-1]

    if operation_type == shared_constants.OperationType.NATIVE_CLUSTER:
        if api_version not in (VcdApiVersion.VERSION_33.value,
                               VcdApiVersion.VERSION_34.value):
            raise cse_exception.NotFoundRequestError()
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.NATIVE_CLUSTER_LIST}
            raise cse_exception.MethodNotAllowedRequestError()

    if operation_type == shared_constants.OperationType.CLUSTER:
        if api_version not in (VcdApiVersion.VERSION_33.value,
                               VcdApiVersion.VERSION_34.value):
            raise cse_exception.NotFoundRequestError()

        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.CLUSTER_LIST}
            if method == shared_constants.RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.CLUSTER_CREATE}
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == shared_constants.RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_INFO,
                    shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == shared_constants.RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_RESIZE,
                    shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                }
            if method == shared_constants.RequestMethod.DELETE:
                return {
                    _OPERATION_KEY: CseOperation.CLUSTER_DELETE,
                    shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                }
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 6:
            if method == shared_constants.RequestMethod.GET:
                if tokens[5] == 'config':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_CONFIG,
                        shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                    }
                if tokens[5] == 'upgrade-plan':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_UPGRADE_PLAN,
                        shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 7:
            if method == shared_constants.RequestMethod.POST:
                if tokens[5] == 'action' and tokens[6] == 'upgrade':
                    return {
                        _OPERATION_KEY: CseOperation.CLUSTER_UPGRADE,
                        shared_constants.RequestKey.CLUSTER_NAME: tokens[4]
                    }
            raise cse_exception.MethodNotAllowedRequestError()
    elif operation_type == shared_constants.OperationType.NODE:
        if api_version not in (VcdApiVersion.VERSION_33.value,
                               VcdApiVersion.VERSION_34.value):
            raise cse_exception.NotFoundRequestError()

        if num_tokens == 4:
            if method == shared_constants.RequestMethod.POST:
                return {_OPERATION_KEY: CseOperation.NODE_CREATE}
            if method == shared_constants.RequestMethod.DELETE:
                return {_OPERATION_KEY: CseOperation.NODE_DELETE}
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == shared_constants.RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.NODE_INFO,
                    shared_constants.RequestKey.NODE_NAME: tokens[4]
                }
            raise cse_exception.MethodNotAllowedRequestError()
    elif operation_type == shared_constants.OperationType.OVDC:
        if api_version not in (VcdApiVersion.VERSION_33.value,
                               VcdApiVersion.VERSION_34.value):
            raise cse_exception.NotFoundRequestError()

        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.OVDC_LIST}
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 5:
            if method == shared_constants.RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_INFO,
                    shared_constants.RequestKey.OVDC_ID: tokens[4]
                }
            if method == shared_constants.RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_UPDATE,
                    shared_constants.RequestKey.OVDC_ID: tokens[4]
                }
            raise cse_exception.MethodNotAllowedRequestError()
        if num_tokens == 6 and tokens[5] == 'compute-policies':
            if method == shared_constants.RequestMethod.GET:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_COMPUTE_POLICY_LIST,
                    shared_constants.RequestKey.OVDC_ID: tokens[4]
                }
            if method == shared_constants.RequestMethod.PUT:
                return {
                    _OPERATION_KEY: CseOperation.OVDC_COMPUTE_POLICY_UPDATE,
                    shared_constants.RequestKey.OVDC_ID: tokens[4]
                }
            raise cse_exception.MethodNotAllowedRequestError()
    elif operation_type == shared_constants.OperationType.ORG_VDCS:
        if api_version not in (VcdApiVersion.VERSION_33.value,
                               VcdApiVersion.VERSION_34.value):
            raise cse_exception.NotFoundRequestError()
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.ORG_VDC_LIST}
            raise cse_exception.NotFoundRequestError()
    elif operation_type == shared_constants.OperationType.SYSTEM:
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.SYSTEM_INFO}
            if method == shared_constants.RequestMethod.PUT:
                return {_OPERATION_KEY: CseOperation.SYSTEM_UPDATE}
            raise cse_exception.MethodNotAllowedRequestError()
    elif operation_type == shared_constants.OperationType.TEMPLATE:
        if num_tokens == 4:
            if method == shared_constants.RequestMethod.GET:
                return {_OPERATION_KEY: CseOperation.TEMPLATE_LIST}
            raise cse_exception.MethodNotAllowedRequestError()

    raise cse_exception.NotFoundRequestError()
