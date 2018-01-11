# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import logging
import sys
import traceback

from pkg_resources import resource_string
import yaml

from container_service_extension.broker import get_new_broker

LOGGER = logging.getLogger('cse.processor')

OK = 200
CREATED = 201
ACCEPTED = 202
UNAUTHORIZED = 401
INTERNAL_SERVER_ERROR = 500


class ServiceProcessor(object):
    def __init__(self, config, verify, log):
        self.config = config
        self.verify = verify
        self.log = log
        self.fsencoding = sys.getfilesystemencoding()

    def process_request(self, body):
        LOGGER.debug('body: %s' % json.dumps(body))
        reply = {}
        tokens = body['requestUri'].split('/')
        cluster_name = None
        spec_request = False
        config_request = False
        template_request = False
        node_request = False
        info_request = False
        system_request = False
        if len(tokens) > 3:
            if tokens[3] in ['swagger', 'swagger.json', 'swagger.yaml']:
                spec_request = True
            elif tokens[3] == 'template':
                template_request = True
            elif tokens[3] == 'system':
                system_request = True
            elif tokens[3] != '':
                cluster_name = tokens[3]
        if len(tokens) > 4:
            if cluster_name is not None:
                if tokens[4] == 'config':
                    config_request = True
                elif tokens[4] == 'info':
                    info_request = True
                elif tokens[4] == 'node':
                    node_request = True
        if len(body['body']) > 0:
            try:
                request_body = json.loads(
                    base64.b64decode(body['body']).decode(self.fsencoding))
            except Exception:
                LOGGER.error(traceback.format_exc())
                request_body = None
        else:
            request_body = None
        LOGGER.debug('request body: %s' % json.dumps(request_body))
        from container_service_extension.service import Service
        service = Service()
        if not system_request and not service.is_enabled:
            raise Exception('CSE service is disabled. '
                            'Contact the System Administrator.')

        if body['method'] == 'GET':
            if spec_request:
                reply = self.get_spec(tokens[3])
            elif config_request:
                broker = get_new_broker(self.config)
                reply = broker.get_cluster_config(cluster_name,
                                                  body['headers'])
            elif template_request:
                result = {}
                templates = []
                for t in self.config['broker']['templates']:
                    is_default = \
                        t['name'] == self.config['broker']['default_template']
                    templates.append({
                        'name':
                        t['name'],
                        'is_default':
                        is_default,
                        'catalog':
                        self.config['broker']['catalog'],
                        'catalog_item':
                        t['catalog_item'],
                        'description':
                        t['description']
                    })
                result['body'] = templates
                result['status_code'] = 200
                reply = result
            elif info_request:
                broker = get_new_broker(self.config)
                reply = broker.get_cluster_info(cluster_name, body['headers'],
                                                request_body)
            elif system_request:
                result = {}
                result['body'] = service.info(body['headers'])
                result['status_code'] = OK
                reply = result
            elif cluster_name is None:
                broker = get_new_broker(self.config)
                reply = broker.list_clusters(body['headers'], request_body)
        elif body['method'] == 'POST':
            if cluster_name is None:
                broker = get_new_broker(self.config)
                reply = broker.create_cluster(body['headers'], request_body)
            else:
                if node_request:
                    broker = get_new_broker(self.config)
                    reply = broker.create_nodes(body['headers'], request_body)
        elif body['method'] == 'PUT':
            if system_request:
                reply = service.update_status(body['headers'], request_body)
        elif body['method'] == 'DELETE':
            if node_request:
                broker = get_new_broker(self.config)
                reply = broker.delete_nodes(body['headers'], request_body)
            else:
                broker = get_new_broker(self.config)
                on_the_fly_request_body = {'name': cluster_name}
                reply = broker.delete_cluster(body['headers'],
                                              on_the_fly_request_body)
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
                spec = yaml.load(file_name)
                result['body'] = json.loads(json.dumps(spec))
            result['status_code'] = OK
        except Exception:
            LOGGER.error(traceback.format_exc())
            result['body'] = []
            result['status_code'] = INTERNAL_SERVER_ERROR
            result['message'] = 'spec file not found: check installation.'
        return result
