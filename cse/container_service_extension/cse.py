#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from consumer import MessageConsumer
import logging
import os
import pkg_resources
import signal
import sys
from threading import Thread
import time
import traceback
import yaml
import pika
from pyvcloud.vcloudair import VCA


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
    default_config = """
    rabbitmq:
    host: rmq.vmware.com
    port: 5672
    user: 'guest'
    password: 'guest'
    exchange: vcdext
    routing_key: cse

vcd:
    host: vcd.vmware.com
    port: 443
    username: 'administrator'
    password: 'enter_your_password'
    api_version: '5.6'
    verify: False
    log: True

service:
    listeners: 2
    logging_level: 20
    logging_format: '%(levelname) -8s %(asctime)s %(name) -40s %(funcName)\
-35s %(lineno) -5d: %(message)s'
    key_filename: 'id_rsa_cse'
    key_filename_pub: 'id_rsa_cse.pub'
    catalog: 'cse-catalog'
    template_master: 'kubernetes.ova'
    template_node: 'kubernetes.ova'
    """
    if os.path.isfile(file_name):
        print('file %s already exist, aborting' % file_name)
        sys.exit(1)
    with open(file_name, 'w') as f:
        f.write(default_config)
    print('default config saved to file \'%s\'' % file_name)


def bool_to_unicode(value):
    if value:
        return u'\u2714'
    else:
        return u'\u2718'


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
        print('Connection to RabbitMQ (%s:%s): %s' % (rmq['host'], rmq['port'],
              bool_to_unicode(connection.is_open)))
        connection.close()
        vca_system = VCA(host=config['vcd']['host'],
                         username=config['vcd']['username'],
                         service_type='standalone',
                         version=config['vcd']['api_version'],
                         verify=config['vcd']['verify'],
                         log=config['vcd']['log'])

        org_url = 'https://%s/cloud' % config['vcd']['host']
        r = vca_system.login(password=config['vcd']['password'],
                             org='System',
                             org_url=org_url)
        print('Connection to vCloud Director (%s:%s): %s' %
              (config['vcd']['host'], config['vcd']['port'],
               bool_to_unicode(r)))
        if r:
            r = vca_system.login(token=vca_system.token,
                                 org='System',
                                 org_url=vca_system.vcloud_session.org_url)
            print('  login to \'System\' org: %s' % (bool_to_unicode(r)))
            found_master = False
            found_node = False
            catalogs = vca_system.get_catalogs()
            for catalog in catalogs:
                if catalog.name == config['service']['catalog']:
                    if catalog.CatalogItems and \
                       catalog.CatalogItems.CatalogItem:
                        for item in catalog.CatalogItems.CatalogItem:
                            if item.name == \
                               config['service']['template_master']:
                                found_master = True
                            if item.name == \
                               config['service']['template_node']:
                                found_node = True
            print('  found master template (%s, %s): %s' %
                  (config['service']['catalog'],
                   config['service']['template_master'],
                   bool_to_unicode(found_master)))
            print('  found node template (%s, %s): %s' %
                  (config['service']['catalog'],
                   config['service']['template_node'],
                   bool_to_unicode(found_node)))
    except:
        tb = traceback.format_exc()
        print('failed to validate configuration from file %s' % file_name)
        print(tb)
        sys.exit(1)


def signal_handler(signal, frame):
    print('\nCrtl+C detected, exiting')
    raise KeyboardInterrupt()


def consumer_thread(c):
    try:
        LOGGER.info('about to start consumer_thread %s', c)
        c.run()
    except:
        print('about to stop consumer_thread')
        print(traceback.format_exc())
        c.stop()


def main():
    global config
    if len(sys.argv) > 0:
        if len(sys.argv) > 1:
            if sys.argv[1] == 'version':
                version = pkg_resources.\
                          require("container-service-extension")[0].version
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

    rmq = config['rabbitmq']
    num_consumers = config['service']['listeners']
    consumers = []
    threads = []

    for n in range(num_consumers):
        try:
            c = MessageConsumer('amqp://%s:%s@%s:%s/' %
                                (rmq['user'],
                                 rmq['password'],
                                 rmq['host'],
                                 rmq['port']),
                                rmq['exchange'],
                                rmq['routing_key'],
                                config,
                                config['vcd']['verify'],
                                config['vcd']['log'])
            t = Thread(target=consumer_thread, args=(c,))
            t.daemon = True
            t.start()
            LOGGER.info('started thread %s', t.ident)
            threads.append(t)
            consumers.append(c)
            time.sleep(0.25)
        except KeyboardInterrupt:
            break
        except:
            print(traceback.format_exc())

    LOGGER.info('num of threads started: %s', len(threads))

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
        except:
            print(traceback.format_exc())
            sys.exit(1)


if __name__ == '__main__':
    main()
