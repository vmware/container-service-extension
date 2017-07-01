#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64, json, sys, logging, thread, time, os, traceback, signal
import pkg_resources
import yaml
import pika
from pyvcloud.vcloudair import VCA
from pyvcloud.task import Task
from pyvcloud.system import System

LOGGER = logging.getLogger(__name__)
config = {}

def print_help():
    print('Container Service Extension for vCloud Director, version %s'
        % pkg_resources.require("container-service-extension")[0].version)
    print("""
Usage: cse COMMAND [ARGS]

Commands:
  help                  Prints this messages
  version               Shows version
  init [config.yml]     Creates config.yml file with default values
  check <config.yml>    Checks configuration in config.yml (RabbitMQ and vCD)
  run <config.yml>      Run cse with options from config.yml
""")
    sys.exit(0)

def init(file_name='config.yml'):
    default_config = \
"""rabbitmq:
    host: vcd.eng.vmware.com
    port: 5672
    user: 'guest'
    password: 'guest'
    exchange: vcdext
    routing_key: cse

vcd:
    host: vcd.eng.vmware.com
    port: 443
    username: 'administrator'
    password: 'enter_your_password'
    api_version: '5.7'
    verify: False
    log: True

service:
    listeners: 2
    logging_level: 20
    logging_format: '%(levelname) -8s %(asctime)s %(name) -8s %(funcName) -8s %(lineno) -5d: %(message)s'
    key_filename: 'id_rsa_cse'
    key_filename_pub: 'id_rsa_cse.pub'
    catalog: 'cse-catalog'
    template_master: 'kube-m.ova'
    template_node: 'kube-n.ova'
"""
    if os.path.isfile(file_name):
        print('file %s already exist, aborting' % file_name)
        sys.exit(1)
    with open(file_name, 'w') as f:
        f.write(default_config)
    print('default config saved to file \'%s\'' % file_name)

def check_config(file_name):
    config = {}
    try:
        with open(file_name, 'r') as f:
            config = yaml.load(f)
    except:
        print('config file \'%s\' not found or invalid' % file_name)
        sys.exit(1)
    try:
        rmq = config['rabbitmq']
        credentials = pika.PlainCredentials(rmq['user'], rmq['password'])
        parameters = pika.ConnectionParameters(rmq['host'], rmq['port'],
                                               '/',
                                               credentials)
        connection = pika.BlockingConnection(parameters)
        print('Connection to RabbitMQ (%s:%s): %s' % (rmq['host'], rmq['port'], connection.is_open))
        connection.close()
        vca_system = VCA(host=config['vcd']['host'], username=config['vcd']['username'],
                        service_type='standalone', version=config['vcd']['api_version'],
                        verify=config['vcd']['verify'], log=config['vcd']['log'])

        org_url = 'https://%s/cloud' % config['vcd']['host']
        r = vca_system.login(password=config['vcd']['password'], org='System', org_url=org_url)
        print('Connection to vCloud Director (%s:%s): %s' % (config['vcd']['host'], config['vcd']['port'], r))
        if r:
            r = vca_system.login(token=vca_system.token, org='System', org_url=vca_system.vcloud_session.org_url)
            print('  login to \'System\' org: %s' % (r))
    except:
        tb = traceback.format_exc()
        print('failed to validate configuration from file %s' % file_name)
        print(tb)
        sys.exit(1)

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
            elif sys.argv[1] == 'help':
                print_help()
                sys.exit(0)
            elif sys.argv[1] == 'init':
                if len(sys.argv) > 2:
                    init(sys.argv[2])
                else:
                    init()
                sys.exit(0)
            elif sys.argv[1] == 'check':
                check_config(sys.argv[2])
                sys.exit(0)
            elif sys.argv[1] == 'run':
                pass
        else:
            print_help()
    try:
        with open(sys.argv[2], 'r') as f:
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
