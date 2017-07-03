# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import logging

LOGGER = logging.getLogger(__name__)

OK                      = 200
CREATED                 = 201
ACCEPTED                = 202
INTERNAL_SERVER_ERROR   = 500


class ServiceProcessor(object):

    def __init__(self):
        pass

    def process_request(self, body):
        LOGGER.debug(json.dumps(body))
        reply = {}
        reply['body'] = []
        reply['status_code'] = OK
        return reply
