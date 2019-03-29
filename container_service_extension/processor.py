# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
from copy import deepcopy
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
UNAUTHORIZED = 401
INTERNAL_SERVER_ERROR = 500


class ServiceProcessor(object):
    def process_request(self, body):
        LOGGER.debug(f"body: {json.dumps(body)}")
        reply = {}
        tokens = body['requestUri'].split('/')
        cluster_name = None
        node_name = None
        spec_request = False
        config_request = False
        template_request = False
        node_request = False
        cluster_info_request = False
        node_info_request = False
        system_request = False
        ovdc_request = False
        ovdc_id = None
        ovdc_info_request = False

        if len(tokens) > 3:
            if tokens[3] in ['swagger', 'swagger.json', 'swagger.yaml']:
                spec_request = True
            elif tokens[3] == 'template':
                template_request = True
            elif tokens[3] == 'system':
                system_request = True
            elif tokens[3] == 'ovdc':
                ovdc_request = True
            elif tokens[3] != '':
                cluster_name = tokens[3]
        if len(tokens) > 4:
            if cluster_name is not None:
                if tokens[4] == 'config':
                    config_request = True
                elif tokens[4] == 'info':
                    cluster_info_request = True
                elif tokens[4] == 'node':
                    node_request = True
                elif tokens[4] != '':
                    node_name = tokens[4]
            elif ovdc_request:
                ovdc_id = tokens[4]

        if len(tokens) > 5:
            if node_name is not None:
                if tokens[5] == 'info':
                    node_info_request = True
            elif ovdc_request:
                if tokens[5] == 'info':
                    ovdc_info_request = True
        if len(body['body']) > 0:
            try:
                request_body = json.loads(
                    base64.b64decode(body['body']).decode(
                        sys.getfilesystemencoding()))
            except Exception:
                LOGGER.error(traceback.format_exc())
                request_body = {}
        else:
            request_body = {}
        LOGGER.debug(f"request body: {json.dumps(request_body)}")

        query_params = {}
        if body['queryString']:
            query_params = dict(parse_qsl(body['queryString']))

        from container_service_extension.service import Service
        service = Service()
        if not system_request and not service.is_enabled:
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
            elif ovdc_request:
                reply = broker_manager.invoke(op=Operation.LIST_OVDCS)
            elif spec_request:
                reply = self.get_spec(tokens[3])
            elif config_request:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.GET_CLUSTER_CONFIG)
            elif template_request:
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
                broker = broker_manager.get_broker_based_on_vdc()
                reply = broker.get_node_info(cluster_name, node_name)
            elif system_request:
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
                    broker = broker_manager.get_broker_based_on_vdc()
                    reply = broker.create_nodes()
        elif body['method'] == 'PUT':
            if ovdc_info_request:
                reply = broker_manager.invoke(Operation.ENABLE_OVDC)
            elif system_request:
                reply = service.update_status(req_headers, req_spec)
            else:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.RESIZE_CLUSTER)
        elif body['method'] == 'DELETE':
            if node_request:
                broker = broker_manager.get_broker_based_on_vdc()
                reply = broker.delete_nodes()
            else:
                req_spec.update({'cluster_name': cluster_name})
                reply = broker_manager.invoke(Operation.DELETE_CLUSTER)

        LOGGER.debug(f"reply: {str(reply)}")
        return reply

    def get_spec(self, format):
        result = {}
        try:
            file_name = resource_string('container_service_extension',
                                        'swagger/swagger.yaml')
            if format == 'swagger.yaml':
                result['body'] = file_name
            else:
                spec = yaml.safe_load(file_name)
                result['body'] = json.loads(json.dumps(spec))
            result['status_code'] = OK
        except Exception:
            LOGGER.error(traceback.format_exc())
            result['body'] = []
            result['status_code'] = INTERNAL_SERVER_ERROR
            result['message'] = 'spec file not found: check installation.'
        return result
