# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import sys
import threading
import traceback

import pika
import requests

from container_service_extension.exceptions import CseRequestError
from container_service_extension.exceptions import NotAcceptableRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_processor as request_processor
from container_service_extension.server_constants import EXCHANGE_TYPE
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY


class MessageConsumer(object):
    def __init__(self,
                 host,
                 port,
                 ssl,
                 vhost,
                 username,
                 password,
                 exchange,
                 routing_key):
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self.host = host
        self.port = port
        self.ssl = ssl
        self.vhost = vhost
        self.username = username
        self.password = password
        self.exchange = exchange
        self.routing_key = routing_key
        self.queue = routing_key
        self.fsencoding = sys.getfilesystemencoding()

    def connect(self):
        LOGGER.info(f"Connecting to {self.host}:{self.port}")
        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            self.host,
            self.port,
            self.vhost,
            credentials,
            ssl=self.ssl,
            connection_attempts=3,
            retry_delay=2,
            socket_timeout=5)
        return pika.SelectConnection(
            parameters, self.on_connection_open, stop_ioloop_on_close=False)

    def on_connection_open(self, unused_connection):
        LOGGER.debug("Connection opened")
        self.add_on_connection_close_callback()
        self.open_channel()

    def add_on_connection_close_callback(self):
        LOGGER.debug("Adding connection close callback")
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            LOGGER.warning(f"Connection closed, reopening in 5 seconds: "
                           f"({reply_code}) {reply_text}")
            self._connection.add_timeout(5, self.reconnect)

    def reconnect(self):
        self._connection.ioloop.stop()

        if not self._closing:
            self._connection = self.connect()
            self._connection.ioloop.start()

    def open_channel(self):
        LOGGER.debug("Creating a new channel")
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        LOGGER.debug("Channel opened")
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.exchange)

    def add_on_channel_close_callback(self):
        LOGGER.debug("Adding channel close callback")
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        LOGGER.warning(f"Channel {channel} was closed: ({reply_code}) "
                       f"{reply_text}")
        self._connection.close()

    def setup_exchange(self, exchange_name):
        LOGGER.debug(f"Declaring exchange {exchange_name}")
        self._channel.exchange_declare(
            self.on_exchange_declareok,
            exchange=exchange_name,
            exchange_type=EXCHANGE_TYPE,
            passive=True,
            durable=True,
            auto_delete=False)

    def on_exchange_declareok(self, unused_frame):
        LOGGER.debug(f"Exchange declared: {unused_frame}")
        self.setup_queue(self.queue)

    def setup_queue(self, queue_name):
        LOGGER.debug(f"Declaring queue {queue_name}")
        self._channel.queue_declare(self.on_queue_declareok, queue_name)

    def on_queue_declareok(self, method_frame):
        LOGGER.debug(f"Binding {self.exchange} to {self.queue} with "
                     f"{self.routing_key}")
        self._channel.queue_bind(self.on_bindok, self.queue, self.exchange,
                                 self.routing_key)

    def on_bindok(self, unused_frame):
        LOGGER.debug("Queue bound")
        self.start_consuming()

    def start_consuming(self):
        LOGGER.debug("Issuing consumer related RPC commands")
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(
            self.on_message, self.queue)

    def add_on_cancel_callback(self):
        LOGGER.debug("Adding consumer cancellation callback")
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        LOGGER.debug(f"Consumer was cancelled remotely, shutting down: "
                     f"{method_frame}")
        if self._channel:
            self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        self.acknowledge_message(basic_deliver.delivery_tag)
        try:
            body_json = json.loads(body.decode(self.fsencoding))[0]
            LOGGER.debug(f"Received message # {basic_deliver.delivery_tag} "
                         f"from {properties.app_id} "
                         f"({threading.currentThread().ident}): "
                         f"{json.dumps(body_json)}, props: {properties}")

            response_format = None
            accept_header = body_json['headers']['Accept'].lower()
            accept_header = accept_header.split(';')[0]
            tokens = accept_header.split('/')
            if len(tokens) > 1:
                if tokens[0] in ('*', 'application'):
                    response_format = tokens[1]
            if not response_format:
                response_format = tokens[0]
            response_format = response_format.replace('*+', '')

            if not ('json' in response_format or '*' == response_format):
                raise NotAcceptableRequestError(
                    error_message="CSE can only serve response as json.")

            result = request_processor.process_request(body_json)

            status_code = result['status_code']
            reply_body = json.dumps(result['body'])
        except Exception as e:
            if isinstance(e, CseRequestError):
                status_code = e.status_code
            else:
                status_code = requests.codes.internal_server_error
            reply_body = json.dumps({RESPONSE_MESSAGE_KEY: str(e)})

            tb = traceback.format_exc()
            LOGGER.error(tb)

        if properties.reply_to is not None:
            reply_msg = {
                'id': body_json['id'],
                'headers': {
                    'Content-Type': 'application/json',
                    'Content-Length': len(reply_body)
                },
                'statusCode': status_code,
                'body': base64.b64encode(reply_body.encode()).decode(self.fsencoding), # noqa: E501
                'request': False
            }
            LOGGER.debug(f"reply: {reply_body}")

            reply_properties = pika.BasicProperties(
                correlation_id=properties.correlation_id)
            self._channel.basic_publish(
                exchange=properties.headers['replyToExchange'],
                routing_key=properties.reply_to,
                body=json.dumps(reply_msg),
                properties=reply_properties)

    def acknowledge_message(self, delivery_tag):
        LOGGER.debug(f"Acknowledging message {delivery_tag}")
        self._channel.basic_ack(delivery_tag)

    def stop_consuming(self):
        if self._channel:
            LOGGER.info("Sending a Basic.Cancel RPC command to RabbitMQ")
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def on_cancelok(self, unused_frame):
        LOGGER.debug("RabbitMQ acknowledged the cancellation of the consumer")
        self.close_channel()

    def close_channel(self):
        LOGGER.debug("Closing the channel")
        self._channel.close()

    def run(self):
        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):
        LOGGER.info("Stopping")
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()
        LOGGER.info("Stopped")

    def close_connection(self):
        LOGGER.info("Closing connection")
        self._connection.close()
