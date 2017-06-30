#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64, json, sys, logging, thread, time, os, traceback, signal
import pkg_resources
import yaml

LOGGER = logging.getLogger(__name__)

def print_help():
    print('Container Service Extension for vCloud Director, version %s'
        % pkg_resources.require("container-service-extension")[0].version)
    print('Usage:')
    print('  cse version')
    print('  cse <config.yml>')
    sys.exit(0)

def signal_handler(signal, frame):
    print('\nCrtl+C detected, exiting')
    sys.exit(0)

def main():
    global config
    if len(sys.argv)>0:
        if len(sys.argv)>1:
            if sys.argv[1] == 'version':
                version = pkg_resources.require("container-service-extension")\
                          [0].version
                print(version)
                sys.exit(0)
        else:
            print_help()
    try:
        with open(sys.argv[1], 'r') as f:
            config = yaml.load(f)
    except:
        tb = traceback.format_exc()
        print('config file \'%s\' not found or invalid' % sys.argv[1])
        print(tb)
        sys.exit(1)

    logging.basicConfig(filename='cse.log',
                        level=config['service']['logging_level'],
                        format=config['service']['logging_format'])

    print('Container Service Extension for vCloud Director running')
    print('see file \'cse.log\' for details')
    print('press Ctrl+C to finish')
    signal.signal(signal.SIGINT, signal_handler)

    LOGGER.info('Container Service Extension for vCloud Director')
    LOGGER.info('waiting for requests...')

    num_consumers = config['service']['listeners']
    consumers = []
    threads = []

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            LOGGER.info('interrupt detected')
            LOGGER.info('closing connections...')
            for c in consumers:
                try:
                    c.stop()
                except:
                    pass
            LOGGER.info('done')
            break

if __name__ == '__main__':
    main()
