# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique
import platform
import signal
import sys
import threading
from threading import Thread
import time
import traceback

import click
import pkg_resources
import requests

from container_service_extension.config_validator import get_validated_config
from container_service_extension.configure_cse import check_cse_installation
from container_service_extension.consumer import MessageConsumer
from container_service_extension.exceptions import CseRequestError
from container_service_extension.logger import configure_server_logger
from container_service_extension.logger import SERVER_DEBUG_LOG_FILEPATH
from container_service_extension.logger import SERVER_INFO_LOG_FILEPATH
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pks_cache import PksCache
from container_service_extension.pyvcloud_utils import \
    connect_vcd_user_via_token
from container_service_extension.shared_constants import SERVER_ACTION_KEY
from container_service_extension.shared_constants import SERVER_DISABLE_ACTION
from container_service_extension.shared_constants import SERVER_ENABLE_ACTION
from container_service_extension.shared_constants import SERVER_STOP_ACTION


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
        LOGGER.info(f"About to start consumer_thread {c}.")
        c.run()
    except Exception:
        click.echo("About to stop consumer_thread.")
        LOGGER.error(traceback.format_exc())
        c.stop()


@unique
class ServerState(Enum):
    RUNNING = 'Running'
    DISABLED = 'Disabled'
    STOPPING = 'Shutting down'
    STOPPED = 'Stopped'


class Service(object, metaclass=Singleton):
    def __init__(self, config_file, should_check_config=True):
        self.config_file = config_file
        self.config = None
        self.should_check_config = should_check_config
        self.consumers = []
        self.threads = []
        self.pks_cache = None
        self._state = ServerState.STOPPED

    def get_service_config(self):
        return self.config

    def get_pks_cache(self):
        return self.pks_cache

    def is_pks_enabled(self):
        return bool(self.pks_cache)

    def active_requests_count(self):
        n = 0
        # TODO(request_count) Add support for PksBroker - VCDA-938
        for t in threading.enumerate():
            from container_service_extension.vcdbroker import VcdBroker
            if type(t) == VcdBroker:
                n += 1
        return n

    def get_status(self):
        return self._state.value

    def is_running(self):
        return self._state == ServerState.RUNNING

    def info(self, tenant_auth_token):
        tenant_client, _ = connect_vcd_user_via_token(
            tenant_auth_token=tenant_auth_token)
        result = Service.version()
        if tenant_client.is_sysadmin():
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
            'product': 'CSE',
            'description': 'Container Service Extension for VMware vCloud '
                           'Director',
            'version': ver,
            'python': platform.python_version()
        }
        return ver_obj

    def update_status(self, tenant_auth_token, req_spec):
        tenant_client, _ = connect_vcd_user_via_token(
            tenant_auth_token=tenant_auth_token)

        if not tenant_client.is_sysadmin():
            raise CseRequestError(status_code=requests.codes.unauthorized,
                                  error_message='Unauthorized to update CSE')

        action = req_spec.get(SERVER_ACTION_KEY)
        if self._state == ServerState.RUNNING:
            if action == SERVER_ENABLE_ACTION:
                raise CseRequestError(
                    status_code=requests.codes.bad_request,
                    error_message='CSE is already enabled and running.')
            elif action == SERVER_DISABLE_ACTION:
                self._state = ServerState.DISABLED
                message = 'CSE has been disabled.'
            elif action == SERVER_STOP_ACTION:
                raise CseRequestError(
                    status_code=requests.codes.bad_request,
                    error_message='Cannot stop CSE while it is enabled. '
                                  'Disable the service first')
        elif self._state == ServerState.DISABLED:
            if action == SERVER_ENABLE_ACTION:
                self._state = ServerState.RUNNING
                message = 'CSE has been enabled and is running.'
            elif action == SERVER_DISABLE_ACTION:
                raise CseRequestError(
                    status_code=requests.codes.bad_request,
                    error_message='CSE is already disabled.')
            elif action == 'stop':
                message = 'CSE graceful shutdown started.'
                n = self.active_requests_count()
                if n > 0:
                    message += f" CSE will finish processing {n} requests."
                self._state = ServerState.STOPPING
        elif self._state == ServerState.STOPPING:
            if action == SERVER_ENABLE_ACTION:
                raise CseRequestError(
                    status_code=requests.codes.bad_request,
                    error_message='Cannot enable CSE while it is being'
                                  'stopped.')
            elif action == SERVER_DISABLE_ACTION:
                raise CseRequestError(
                    status_code=requests.codes.bad_request,
                    error_message='Cannot disable CSE while it is being'
                                  ' stopped.')
            elif action == SERVER_STOP_ACTION:
                message = 'CSE graceful shutdown is in progress.'

        return message

    def run(self, msg_update_callback=None):
        self.config = get_validated_config(
            self.config_file, msg_update_callback=msg_update_callback)
        if self.should_check_config:
            check_cse_installation(
                self.config, msg_update_callback=msg_update_callback)

        configure_server_logger()

        message = f"Container Service Extension for vCloudDirector" \
                  f"\nServer running using config file: {self.config_file}" \
                  f"\nLog files: {SERVER_INFO_LOG_FILEPATH}, " \
                  f"{SERVER_DEBUG_LOG_FILEPATH}" \
                  f"\nwaiting for requests (ctrl+c to close)"

        signal.signal(signal.SIGINT, signal_handler)
        if msg_update_callback:
            msg_update_callback.general_no_color(message)
        LOGGER.info(message)

        if self.config.get('pks_config'):
            pks_config = self.config.get('pks_config')
            self.pks_cache = PksCache(
                pks_servers=pks_config.get('pks_api_servers', []),
                pks_accounts=pks_config.get('pks_accounts', []),
                pvdcs=pks_config.get('pvdcs', []),
                orgs=pks_config.get('orgs', []),
                nsxt_servers=pks_config.get('nsxt_servers', []))

        amqp = self.config['amqp']
        num_consumers = self.config['service']['listeners']
        for n in range(num_consumers):
            try:
                c = MessageConsumer(
                    amqp['host'], amqp['port'], amqp['ssl'], amqp['vhost'],
                    amqp['username'], amqp['password'], amqp['exchange'],
                    amqp['routing_key'])
                name = 'MessageConsumer-%s' % n
                t = Thread(name=name, target=consumer_thread, args=(c, ))
                t.daemon = True
                t.start()
                LOGGER.info("Started thread {t.ident}")
                self.threads.append(t)
                self.consumers.append(c)
                time.sleep(0.25)
            except KeyboardInterrupt:
                break
            except Exception:
                print(traceback.format_exc())

        LOGGER.info(f"Number of threads started: {len(self.threads)}")

        self._state = ServerState.RUNNING

        while True:
            try:
                time.sleep(1)
                if self._state == ServerState.STOPPING and \
                        self.active_requests_count() == 0:
                    break
            except KeyboardInterrupt:
                break
            except Exception:
                if msg_update_callback:
                    msg_update_callback.general_no_color(
                        traceback.format_exc())
                sys.exit(1)

        LOGGER.info("Stop detected")
        LOGGER.info("Closing connections...")
        for c in self.consumers:
            try:
                c.stop()
            except Exception:
                pass

        self._state = ServerState.STOPPED
        LOGGER.info("Done")
