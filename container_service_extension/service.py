# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
from logging.handlers import RotatingFileHandler
import platform
import signal
import sys
import threading
from threading import Thread
import time
import traceback

import click
import pkg_resources
from pyvcloud.vcd.client import Client

from container_service_extension.broker import DefaultBroker
from container_service_extension.config import check_config
from container_service_extension.config import get_config
from container_service_extension.consumer import MessageConsumer

LOGGER = logging.getLogger('cse.service')


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs)
        return cls._instances[cls]


def signal_handler(signal, frame):
    print('\nCrtl+C detected, exiting')
    raise KeyboardInterrupt()


def consumer_thread(c):
    try:
        LOGGER.info('about to start consumer_thread %s', c)
        c.run()
    except Exception:
        click.echo('about to stop consumer_thread')
        LOGGER.error(traceback.format_exc())
        c.stop()


class Service(object, metaclass=Singleton):
    def __init__(self, config_file, should_check_config=True):
        self.config_file = config_file
        self.config = None
        self.should_check_config = should_check_config
        self.is_enabled = False
        self.consumers = []
        self.threads = []
        self.should_stop = False

    def connect_tenant(self, headers):
        token = headers.get('x-vcloud-authorization')
        accept_header = headers.get('Accept')
        version = accept_header.split('version=')[1]
        client_tenant = Client(
            uri=self.config['vcd']['host'],
            api_version=version,
            verify_ssl_certs=self.config['vcd']['verify'],
            log_headers=True,
            log_bodies=True)
        session = client_tenant.rehydrate_from_token(token)
        return (
            client_tenant,
            session,
        )

    def active_requests_count(self):
        n = 0
        for t in threading.enumerate():
            if type(t) == DefaultBroker:
                n += 1
        return n

    def get_status(self):
        if self.is_enabled:
            return 'Running'
        else:
            if self.should_stop:
                return 'Shutting down'
            else:
                return 'Disabled'

    def info(self, headers):
        client_tenant, session = self.connect_tenant(headers)
        result = Service.version()
        if session.get('org') == 'System':
            result['consumer_threads'] = len(self.threads)
            result['all_threads'] = threading.activeCount()
            result['requests_in_progress'] = self.active_requests_count()
            result['config_file'] = self.config_file
            result['status'] = self.get_status()
        else:
            del result['python']
        return result

    @classmethod
    def version(cls):
        ver = pkg_resources.require('container-service-extension')[0].version
        ver_obj = {
            'product':
            'CSE',
            'description':
            'Container Service Extension for VMware vCloud Director',
            'version':
            ver,
            'python':
            platform.python_version()
        }
        return ver_obj

    def update_status(self, headers, body):
        client_tenant, session = self.connect_tenant(headers)
        reply = {}
        if session.get('org') == 'System':
            if 'enabled' in body:
                if body['enabled'] and self.should_stop:
                    reply['body'] = {
                        'message': 'Cannot enable while being stopped.'
                    }
                    reply['status_code'] = 500
                else:
                    self.is_enabled = body['enabled']
                    reply['body'] = {'message': 'Updated'}
                    reply['status_code'] = 200
            elif 'stopped' in body:
                if self.is_enabled:
                    reply['body'] = {
                        'message':
                        'Cannot stop CSE while is enabled.'
                        ' Disable the service first.'
                    }
                    reply['status_code'] = 500
                else:
                    message = 'CSE graceful shutdown started.'
                    n = self.active_requests_count()
                    if n > 0:
                        message += ' CSE will finish processing %s requests.' \
                            % n
                    reply['body'] = {'message': message}
                    reply['status_code'] = 200
                    self.should_stop = True
            else:
                reply['body'] = {'message': 'Unknown status'}
                reply['status_code'] = 500
        else:
            reply['body'] = {'message': 'Unauthorized'}
            reply['status_code'] = 401
        return reply

    def run(self):
        if self.should_check_config:
            self.config = check_config(self.config_file)
        else:
            self.config = get_config(self.config_file)
        log_file = 'cse.log'
        handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=10)
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(lineno)s '
            '%(levelname)-8s %(message)s',
            datefmt='%m-%d %H:%M:%S',
            handlers=(handler, ))
        logging.getLogger("pika").setLevel(logging.WARNING)

        message = """
Container Service Extension for vCloud Director running
config file: {config_file}
see file log file for details: {log_file}
waiting for requests, press Ctrl+C to finish
""".format(config_file=self.config_file, log_file=log_file)

        signal.signal(signal.SIGINT, signal_handler)
        click.secho(message)
        LOGGER.info(message)

        amqp = self.config['amqp']
        num_consumers = self.config['service']['listeners']

        for n in range(num_consumers):
            try:
                if amqp['ssl']:
                    scheme = 'amqps'
                else:
                    scheme = 'amqp'
                c = MessageConsumer(
                    '%s://%s:%s@%s:%s/?socket_timeout=5' %
                    (scheme, amqp['username'], amqp['password'], amqp['host'],
                     amqp['port']), amqp['exchange'], amqp['routing_key'],
                    self.config, self.config['vcd']['verify'],
                    self.config['vcd']['log'])
                name = 'MessageConsumer-%s' % n
                t = Thread(name=name, target=consumer_thread, args=(c, ))
                t.daemon = True
                t.start()
                LOGGER.info('started thread %s', t.ident)
                self.threads.append(t)
                self.consumers.append(c)
                time.sleep(0.25)
            except KeyboardInterrupt:
                break
            except Exception:
                print(traceback.format_exc())

        LOGGER.info('num of threads started: %s', len(self.threads))

        self.is_enabled = True

        while True:
            try:
                time.sleep(1)
                if self.should_stop and self.active_requests_count() == 0:
                    break
            except KeyboardInterrupt:
                break
            except Exception:
                click.secho(traceback.format_exc())
                sys.exit(1)

        LOGGER.info('stop detected')
        LOGGER.info('closing connections...')
        for c in self.consumers:
            try:
                c.stop()
            except Exception:
                pass
        LOGGER.info('done')
