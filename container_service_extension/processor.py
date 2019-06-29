# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
from copy import deepcopy
import json
import sys
import traceback
from urllib.parse import parse_qsl

import requests

from container_service_extension.broker_manager import BrokerManager
from container_service_extension.exception_handler import handle_exception
from container_service_extension.exceptions import CseRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_request_handler import OvdcRequestHandler
from container_service_extension.server_constants import CseOperation
from container_service_extension.utils import get_server_runtime_config


class ServiceProcessor(object):
    """Process incoming REST request.

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

    GET /cse/system
    PUT /cse/system

    GET /cse/template
    """ ## noqa

    def _parse_request_url(self, method, url):
        """Determine the operation that the REST request represent.

        Additionally parse the url for data that might be needed while
        processing the request.

        :param str url: Incoming REST request url.
        :param str method: HTTP method of the REST request.

        :return: the type of operation the incoming REST request corresponds
            to, plus associated parsed data from the url.

        :rtype: dict
        """
        is_cluster_request = False
        is_node_request = False
        is_ovdc_request = False
        is_system_request = False
        is_template_request = False
        result = {}

        tokens = url.split('/')
        if len(tokens) > 3:
            if tokens[3] in ('cluster', 'clusters'):
                is_cluster_request = True
            elif tokens[3] in ('node', 'nodes'):
                is_node_request = True
            elif tokens[3] in('ovdc', 'ovdcs'):
                is_ovdc_request = True
            elif tokens[3] == 'system':
                is_system_request = True
            elif tokens[3] == 'templates':
                is_template_request = True

        if is_cluster_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['operation'] = CseOperation.CLUSTER_LIST
                elif method == 'POST':
                    result['operation'] = CseOperation.CLUSTER_CREATE
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")
            elif len(tokens) == 5:
                if method == 'GET':
                    result['operation'] = CseOperation.CLUSTER_INFO
                    result['cluster_name'] = tokens[4]
                elif method == 'PUT':
                    result['operation'] = CseOperation.CLUSTER_RESIZE
                    result['cluster_name'] = tokens[4]
                elif method == 'DELETE':
                    result['operation'] = CseOperation.CLUSTER_DELETE
                    result['cluster_name'] = tokens[4]
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")
            elif len(tokens) == 6:
                if method == 'GET':
                    if tokens[5] == 'config':
                        result['operation'] = CseOperation.CLUSTER_CONFIG
                        result['cluster_name'] = tokens[4]
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")

        if is_node_request:
            if len(tokens) == 4:
                if method == 'POST':
                    result['operation'] = CseOperation.NODE_CREATE
                elif method == 'DELETE':
                    result['operation'] = CseOperation.NODE_DELETE
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")
            elif len(tokens) == 5:
                if method == 'GET':
                    result['operation'] = CseOperation.NODE_INFO
                    result['node_name'] = tokens[4]
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")

        if is_ovdc_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['operation'] = CseOperation.OVDC_LIST
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")
            elif len(tokens) == 5:
                if method == 'GET':
                    result['operation'] = CseOperation.OVDC_INFO
                    result['ovdc_id'] = tokens[4]
                elif method == 'PUT':
                    result['operation'] = CseOperation.OVDC_ENABLE_DISABLE
                    result['ovdc_id'] = tokens[4]
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")

        if is_system_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['operation'] = CseOperation.SYSTEM_INFO
                elif method == 'PUT':
                    result['operation'] = CseOperation.SYSTEM_UPDATE
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")

        if is_template_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['operation'] = CseOperation.TEMPLATE_LIST
                else:
                    raise CseRequestError(
                        status=requests.codes.method_not_allowed,
                        error_message="Method not allowed")

        if not result.get('operation'):
            raise CseRequestError(
                status=requests.codes.not_found,
                error_message="Invalid Url. Not found.")
        return result

    @handle_exception
    def process_request(self, body):
        LOGGER.debug(f"body: {json.dumps(body)}")
        reply = {}

        # parse url
        request_url_parse_result = self._parse_request_url(
            method=body['method'], url=body['requestUri'])

        # check for disabled server
        operation = request_url_parse_result['operation']
        if operation not in (CseOperation.SYSTEM_INFO,
                             CseOperation.SYSTEM_UPDATE):
            from container_service_extension.service import Service
            if not Service().is_running():
                raise CseRequestError(
                    status_code=requests.codes.bad_request,
                    error_message='CSE service is disabled. Contact the'
                                  ' System Administrator.')

        # parse query params
        query_params = {}
        if body['queryString']:
            query_params = dict(parse_qsl(body['queryString']))

        # parse body
        if len(body['body']) > 0:
            try:
                request_body = json.loads(
                    base64.b64decode(
                        body['body']).decode(sys.getfilesystemencoding()))
                LOGGER.debug(f"request body: {json.dumps(request_body)}")
            except Exception:
                LOGGER.error(traceback.format_exc())
                request_body = {}
        else:
            request_body = {}

        # compose request spec for further processing
        tenant_auth_token = body['headers']['x-vcloud-authorization']
        req_spec = deepcopy(request_body)
        for key, val in query_params.items():
            req_spec[key] = val

        # update request spec with operation specific data in the url
        if operation in \
                (CseOperation.CLUSTER_CONFIG, CseOperation.CLUSTER_DELETE,
                 CseOperation.CLUSTER_INFO, CseOperation.CLUSTER_RESIZE):
            req_spec.update(
                {'cluster_name': request_url_parse_result.get('cluster_name')})
        elif operation == CseOperation.NODE_INFO:
            req_spec.update(
                {'node_name': request_url_parse_result.get('node_name')})
        elif operation in \
                (CseOperation.OVDC_ENABLE_DISABLE, CseOperation.OVDC_INFO):
            req_spec.update(
                {'ovdc_id': request_url_parse_result.get('ovdc_id')})

        # process the request
        reply['status_code'] = operation.ideal_response_code
        if operation == CseOperation.SYSTEM_INFO:
            from container_service_extension.service import Service
            reply['body'] = Service().info(tenant_auth_token)
        elif operation == CseOperation.SYSTEM_UPDATE:
            from container_service_extension.service import Service
            reply['body'] = {
                'message':
                Service().update_status(tenant_auth_token, req_spec)}
        elif operation == CseOperation.TEMPLATE_LIST:
            templates = []
            server_config = get_server_runtime_config()
            default_template_name = \
                server_config['broker']['default_template']
            for t in server_config['broker']['templates']:
                is_default = t['name'] == default_template_name
                templates.append({
                    'name': t['name'],
                    'is_default': is_default,
                    'catalog': server_config['broker']['catalog'],
                    'catalog_item': t['catalog_item'],
                    'description': t['description']
                })
            reply['body'] = templates
        elif operation in (CseOperation.OVDC_ENABLE_DISABLE,
                           CseOperation.OVDC_INFO, CseOperation.OVDC_LIST):
            ovdc_request_handler = \
                OvdcRequestHandler(tenant_auth_token, req_spec)
            reply['body'] = ovdc_request_handler.invoke(op=operation)
        else:
            broker_manager = BrokerManager(tenant_auth_token, req_spec)
            reply['body'] = broker_manager.invoke(op=operation)

        LOGGER.debug(f"reply: {str(reply)}")
        return reply
