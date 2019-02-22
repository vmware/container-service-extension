# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
import traceback

from pkg_resources import resource_string
import yaml

from container_service_extension.broker_selector import get_new_broker
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
        LOGGER.debug('body: %s' % json.dumps(body))
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
                request_body = None
        else:
            request_body = None
        LOGGER.debug('request body: %s' % json.dumps(request_body))

        from container_service_extension.service import Service
        service = Service()
        if not system_request and not service.is_enabled:
            raise CseServerError('CSE service is disabled. '
                                 'Contact the System Administrator.')

        if body['method'] == 'GET':
            if ovdc_info_request:
                on_the_fly_request_body = {'ovdc_id': ovdc_id}
                broker = get_new_broker(body['headers'],
                                        on_the_fly_request_body)
                reply = broker.ovdc_info_for_kubernetes()

            elif spec_request:
                reply = self.get_spec(tokens[3])
            elif config_request:
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.get_cluster_config(cluster_name)
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
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.get_cluster_info(cluster_name)
            elif node_info_request:
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.get_node_info(cluster_name, node_name)
            elif system_request:
                result = {}
                result['body'] = service.info(body['headers'])
                result['status_code'] = OK
                reply = result
            elif cluster_name is None:
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.list_clusters()
        elif body['method'] == 'POST':
            if cluster_name is None:
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.create_cluster()
            else:
                if node_request:
                    broker = get_new_broker(body['headers'], request_body)
                    reply = broker.create_nodes()
        elif body['method'] == 'PUT':
            if ovdc_info_request:
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.enable_ovdc_for_kubernetes()
            elif system_request:
                reply = service.update_status(body['headers'], request_body)
        elif body['method'] == 'DELETE':
            if node_request:
                broker = get_new_broker(body['headers'], request_body)
                reply = broker.delete_nodes()
            else:
                on_the_fly_request_body = {'name': cluster_name}
                broker = get_new_broker(body['headers'],
                                        on_the_fly_request_body)
                reply = broker.delete_cluster()

        LOGGER.debug('reply: %s' % str(reply))
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
