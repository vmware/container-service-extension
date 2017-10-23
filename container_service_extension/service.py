# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from container_service_extension.config import check_config
from container_service_extension.config import get_config
from container_service_extension.consumer import MessageConsumer
from container_service_extension.pv_provisioner import PVProvisioner
import logging
import signal
import sys
from threading import Thread
import time
import traceback


LOGGER = logging.getLogger(__name__)


def signal_handler(signal, frame):
    print('\nCrtl+C detected, exiting')
    raise KeyboardInterrupt()


def consumer_thread(c):
    try:
        LOGGER.info('about to start consumer_thread %s', c)
        c.run()
    except Exception:
        click.echo('about to stop consumer_thread')
        print(traceback.format_exc())
        c.stop()


class Service(object):

    def __init__(self, config_file, check_config=True):
        self.config_file = config_file
        self.config = None
        self.check_config = check_config

    def run(self):
        if self.check_config:
            self.config = check_config(self.config_file)
        else:
            self.config = get_config(self.config_file)
        logging.basicConfig(filename='cse.log',
                            level=self.config['service']['logging_level'],
                            format=self.config['service']['logging_format'])

        click.echo('Container Service Extension for vCloud Director running')
        click.echo('see file ''cse.log'' for details')
        click.echo('press Ctrl+C to finish')

        signal.signal(signal.SIGINT, signal_handler)

        LOGGER.info('Container Service Extension for vCloud Director')
        LOGGER.info('waiting for requests...')

        amqp = self.config['amqp']
        num_consumers = self.config['service']['listeners']
        consumers = []
        threads = []

        for n in range(num_consumers):
            try:
                if amqp['ssl']:
                    scheme = 'amqps'
                else:
                    scheme = 'amqp'
                c = MessageConsumer('%s://%s:%s@%s:%s/?socket_timeout=5' %
                                    (scheme,
                                     amqp['username'],
                                     amqp['password'],
                                     amqp['host'],
                                     amqp['port']),
                                    amqp['exchange'],
                                    amqp['routing_key'],
                                    self.config,
                                    self.config['vcd']['verify'],
                                    self.config['vcd']['log'])
                t = Thread(target=consumer_thread, args=(c,))
                t.daemon = True
                t.start()
                LOGGER.info('started thread %s', t.ident)
                threads.append(t)
                consumers.append(c)
                time.sleep(0.25)
            except KeyboardInterrupt:
                break
            except Exception:
                print(traceback.format_exc())

        LOGGER.info('num of threads started: %s', len(threads))

        pv_provisioner = PVProvisioner(self.config)
        pv_provisioner.start()

        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                LOGGER.info('interrupt detected')
                LOGGER.info('closing connections...')
                for c in consumers:
                    try:
                        c.stop()
                    except Exception:
                        pass
                LOGGER.info('done')
                break
            except Exception:
                click.secho(traceback.format_exc())
                sys.exit(1)
