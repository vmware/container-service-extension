# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
from copy import deepcopy
from enum import Enum
import json
import sys
import traceback
from urllib.parse import parse_qsl

from pkg_resources import resource_string
import yaml

from container_service_extension.exceptions import CseServerError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.utils import get_server_runtime_config

OK = 200
CREATED = 201
ACCEPTED = 202
BAD_REQUEST = 400
UNAUTHORIZED = 401
NOT_FOUND = 404
NOT_ACCEPTABLE = 406
INTERNAL_SERVER_ERROR = 500


class CseRequestType(Enum):
    CLUSTER_CREATE_REQUEST = 'create cluster'
    CLUSTER_CONFIG_REQUEST = 'get config of cluster'
    CLUSTER_DELETE_REQUEST = 'delete cluster'
    CLUSTER_INFO_REQUEST = 'get info of cluster'
    CLUSTER_LIST_REQUEST = 'list clusters'
    CLUSTER_RESIZE_REQUEST = 'resize cluster'
    NODE_CREATE_REQUEST = 'create node'
    NODE_DELETE_REQUEST = 'delete node'
    NODE_INFO_REQUEST = 'get info of node'
    OVDC_ENABLE_DISABLE_REQUEST = 'enable or disable ovdc for k8s'
    OVDC_INFO_REQUEST = 'get info of ovdc'
    OVDC_LIST_REQUEST = 'list ovdcs'
    SYSTEM_INFO_REQUEST = 'get info of system'
    SYSTEM_UPDATE_REQUEST = 'update system status'
    TEMPLATE_LIST_REQUEST = 'list all templates'
    # Error Request types
    BAD_REQUEST = '400'
    NOT_FOUND_REQUEST = '404'
    NOT_ACCEPTABLE_REQUEST = '406'


class ServiceProcessor(object):
    """Following are the valid api endpoints.

    GET /cse/cluster?org={org name}&vdc={vdc name}
    POST /cse/cluster
    GET /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
    PUT /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
    DELETE /cse/cluster/{cluster name}?org={org name}&vdc={vdc name}
    GET /cse/cluster/{cluster name}/config?org={org name}&vdc={vdc name}

    POST /cse/node
    DELETE /cse/node
    GET /cse/node/{node name}?cluster_name={cluster name}&org={org name}&vdc={vdc name}

    GET /cse/ovdc
    GET /cse/ovdc/{ovdc id}
    PUT /cse/ovdc/{ovdc id}

    GET /cse/system
    PUT /cse/system

    GET /cse/template
    """ ## noqa

    def _parse_request_url(self, url, method):
        is_cluster_request = False
        is_node_request = False
        is_ovdc_request = False
        is_system_request = False
        is_template_request = False
        result = {}

        tokens = url.split('/')
        if len(tokens) <= 3:
            result['request_type'] = CseRequestType.NOT_FOUND_REQUEST
        else:
            if tokens[3] == 'cluster':
                is_cluster_request = True
            elif tokens[3] == 'node':
                is_node_request = True
            elif tokens[3] == 'ovdc':
                is_ovdc_request = True
            elif tokens[3] == 'system':
                is_system_request = True
            elif tokens[3] == 'template':
                is_template_request = True

        if is_cluster_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['request_type'] = \
                        CseRequestType.CLUSTER_LIST_REQUEST
                elif method == 'POST':
                    result['request_type'] = \
                        CseRequestType.CLUSTER_CREATE_REQUEST
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST
            elif len(tokens) == 5:
                if method == 'GET':
                    result['request_type'] = \
                        CseRequestType.CLUSTER_INFO_REQUEST
                    result['cluster_name'] = tokens[4]
                elif method == 'PUT':
                    result['request_type'] = \
                        CseRequestType.CLUSTER_RESIZE_REQUEST
                    result['cluster_name'] = tokens[4]
                elif method == 'DELETE':
                    result['request_type'] = \
                        CseRequestType.CLUSTER_DELETE_REQUEST
                    result['cluster_name'] = tokens[4]
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST
            elif len(tokens) == 6:
                if method == 'GET':
                    if tokens[5] == 'config':
                        result['request_type'] = \
                            CseRequestType.CLUSTER_CONFIG_REQUEST
                        result['cluster_name'] = tokens[4]
                    else:
                        result['request_type'] = \
                            CseRequestType.NOT_FOUND_REQUEST
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST

        if is_node_request:
            if len(tokens) == 4:
                if method == 'POST':
                    result['request_type'] = CseRequestType.NODE_CREATE_REQUEST
                elif method == 'DELETE':
                    result['request_type'] = CseRequestType.NODE_DELETE_REQUEST
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST
            elif len(tokens) == 5:
                if method == 'GET':
                    result['request_type'] = CseRequestType.NODE_INFO_REQUEST
                    result['node_name'] = tokens[4]
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST

        if is_ovdc_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['request_type'] = \
                        CseRequestType.OVDC_LIST_REQUEST
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST
            elif len(tokens) == 5:
                if method == 'GET':
                    result['request_type'] = \
                        CseRequestType.OVDC_INFO_REQUEST
                    result['ovdc_id'] = tokens[4]
                elif method == 'PUT':
                    result['request_type'] = \
                        CseRequestType.OVDC_ENABLE_DISABLE_REQUEST
                    result['ovdc_id'] = tokens[4]
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST

        if is_system_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['request_type'] = \
                        CseRequestType.SYSTEM_INFO_REQUEST
                elif method == 'PUT':
                    result['request_type'] = \
                        CseRequestType.SYSTEM_UPDATE_REQUEST
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST

        if is_template_request:
            if len(tokens) == 4:
                if method == 'GET':
                    result['request_type'] = \
                        CseRequestType.TEMPLATE_LIST_REQUEST
                else:
                    result['request_type'] = \
                        CseRequestType.NOT_ACCEPTABLE_REQUEST

        if not result.get('request_type'):
            result['request_type'] = CseRequestType.NOT_FOUND_REQUEST

        return result

    def process_request(self, body):
        LOGGER.debug(f"body: {json.dumps(body)}")
        reply = {}

        parsed_request_url = self._parse_request_url(
            url = body['requestUri'], method = body['method'])

        if parsed_request_url['request_type'] == CseRequestType.BAD_REQUEST:
            reply['status_code'] = BAD_REQUEST
            return reply
        elif parsed_request_url['request_type'] == \
                CseRequestType.NOT_FOUND_REQUEST:
            reply['status_code'] = NOT_FOUND
            return reply
        elif parsed_request_url['request_type'] == \
                CseRequestType.NOT_ACCEPTABLE_REQUEST:
            reply['status_code'] = NOT_ACCEPTABLE
            return reply

        query_params = {}
        if body['queryString']:
            query_params = dict(parse_qsl(body['queryString']))

        if len(body['body']) > 0:
            try:
                request_body = json.loads(
                    base64.b64decode(body['body']).decode(
                        sys.getfilesystemencoding()))
                LOGGER.debug(f"request body: {json.dumps(request_body)}")
            except Exception:
                LOGGER.error(traceback.format_exc())
                request_body = {}
        else:
            request_body = {}

        reply['status_code'] = 200
        reply['body'] = str(parsed_request_url) + "," + str(query_params)
        return reply
        '''
        from container_service_extension.service import Service
        service = Service()
        if not is_system_request and not service.is_enabled:
            raise CseServerError('CSE service is disabled. '
                                 'Contact the System Administrator.')

        req_headers = deepcopy(body['headers'])
        req_query_params = deepcopy(query_params)
        req_spec = deepcopy(request_body)

        from container_service_extension.broker_manager import BrokerManager
        broker_manager = BrokerManager(req_headers, req_query_params, req_spec)
        from container_service_extension.broker_manager import Operation

        if body['method'] == 'GET':
            if ovdc_info_request:
                req_spec.update({'ovdc_id': ovdc_id})
                reply = broker_manager.invoke(Operation.INFO_OVDC)
            elif is_ovdc_request:
                reply = broker_manager.invoke(op=Operation.LIST_OVDCS)
            elif config_request:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.GET_CLUSTER_CONFIG)
            elif is_template_request:
                result = {}
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
                result['body'] = templates
                result['status_code'] = 200
                reply = result
            elif cluster_info_request:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.GET_CLUSTER)
            elif node_info_request:
                req_spec.update({'cluster_name': cluster_name})
                req_spec.update({'node_name': node_name})
                reply = broker_manager.invoke(Operation.GET_NODE_INFO)
            elif is_system_request:
                result = {}
                result['body'] = service.info(req_headers)
                result['status_code'] = OK
                reply = result
            elif cluster_name is None:
                reply = broker_manager.invoke(Operation.LIST_CLUSTERS)
        elif body['method'] == 'POST':
            if cluster_name is None:
                reply = broker_manager.invoke(Operation.CREATE_CLUSTER)
            else:
                if node_request:
                    reply = broker_manager.invoke(Operation.CREATE_NODE)
        elif body['method'] == 'PUT':
            if ovdc_info_request:
                reply = broker_manager.invoke(Operation.ENABLE_OVDC)
            elif is_system_request:
                reply = service.update_status(req_headers, req_spec)
            else:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.RESIZE_CLUSTER)
        elif body['method'] == 'DELETE':
            if node_request:
                reply = broker_manager.invoke(Operation.DELETE_NODE)
            else:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.DELETE_CLUSTER)

        LOGGER.debug(f"reply: {str(reply)}")
        return reply
        '''
