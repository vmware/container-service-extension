# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
from container_service_extension.broker import get_new_broker
import json
import logging
from pkg_resources import resource_string
import sys
import traceback
import yaml

LOGGER = logging.getLogger(__name__)

OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_SERVER_ERROR = 500


class ServiceProcessor(object):

    def __init__(self, config, verify, log):
        self.config = config
        self.verify = verify
        self.log = log
        self.broker = get_new_broker(config)
        self.fsencoding = sys.getfilesystemencoding()

    def process_request(self, body):
        LOGGER.debug('body: %s' % json.dumps(body))
        reply = {}
        tokens = body['requestUri'].split('/')
        cluster_name = None
        spec_request = False
        config_request = False
        if len(tokens) > 3:
            if tokens[3] in ['swagger', 'swagger.json', 'swagger.yaml']:
                spec_request = True
            elif tokens[3] != '':
                cluster_name = tokens[3]
        if len(tokens) > 4:
            if tokens[4] == 'config':
                config_request = True
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

        if body['method'] == 'GET':
            if spec_request:
                reply = self.get_spec(tokens[3])
            elif config_request:
                broker = get_new_broker(self.config)
                reply = broker.get_cluster_config(cluster_name,
                                                  body['headers'],
                                                  None)
            elif cluster_name is None:
                broker = get_new_broker(self.config)
                reply = broker.list_clusters(body['headers'],
                                             request_body)
        elif body['method'] == 'POST':
            if cluster_name is None:
                broker = get_new_broker(self.config)
                reply = broker.create_cluster(body['headers'],
                                              request_body)
        elif body['method'] == 'DELETE':
            broker = get_new_broker(self.config)
            reply = broker.delete_cluster(cluster_name,
                                          body['headers'],
                                          request_body)
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
