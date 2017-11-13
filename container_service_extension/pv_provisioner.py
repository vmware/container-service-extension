# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import logging
import os
from random import randint
import threading
import time

LOGGER = logging.getLogger(__name__)

class PVProvisioner(threading.Thread):

    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config
        self.nodes = ['c2-n1', 'c2-n2']

    def run(self):
        LOGGER.debug('PV provisioner thread started')
        print('PV provisioner thread started, cse_msg_dir: %s' % self.config['broker']['cse_msg_dir'])
        request_directory = os.path.join(self.config['broker']['cse_msg_dir'], 'req')
        response_directory = os.path.join(self.config['broker']['cse_msg_dir'], 'res')
        if not os.path.isdir(request_directory):
            print('directory \'%s\' not found, PV provisioner stopped' % request_directory)
            return
        if not os.path.isdir(response_directory):
            print('directory \'%s\' not found, PV provisioner stopped' % response_directory)
            return
        while True:
            time.sleep(1)
            files = os.scandir(request_directory)
            for request_file in files:
                print('processing %s ' % request_file.path)
                request_msg = {}
                with open(request_file, 'r') as f:
                    request_msg = json.load(f)
                response_msg = self.process_request(request_msg)
                response_file = os.path.join(response_directory, request_file.name)
                with open(response_file, 'w') as f:
                    json.dump(response_msg, f)
                os.remove(request_file)

    def process_request(self, request_msg):
        next_node = randint(0, len(self.nodes)-1)
        response_msg = {
            'PVName': request_msg['PVName'],
            'Node': self.nodes[next_node]
        }
        print(json.dumps(response_msg))
        return response_msg
