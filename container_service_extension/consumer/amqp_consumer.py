# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import sys
from threading import Lock

import pika
import requests

import container_service_extension.consumer.constants as constants
from container_service_extension.consumer.consumer_thread_pool_executor \
    import ConsumerThreadPoolExecutor
import container_service_extension.consumer.utils as utils
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.server_constants import EXCHANGE_TYPE


class AMQPConsumer(object):
    def __init__(self,
                 host,
                 port,
                 ssl,
                 vhost,
                 username,
                 password,
                 exchange,
                 routing_key,
                 num_processors):
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
        self.num_processors = num_processors
        self.fsencoding = sys.getfilesystemencoding()
        self._ctpe = ConsumerThreadPoolExecutor(self.num_processors)
        self._publish_lock = Lock()

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

    def form_response_json(self, request_id, status_code, reply_body):
        response_json = {
            'id': request_id,
            'headers': {
                'Content-Type': 'application/json',
                'Content-Length': len(reply_body)
            },
            'statusCode': status_code,
            'body': utils.format_response_body(reply_body, self.fsencoding),
            'request': False
        }
        return response_json

    def process_amqp_message(self, properties, body, basic_deliver):
        msg_json, reply_body, status_code, req_id = utils.get_response_fields(
            request_msg=body,
            fsencoding=self.fsencoding,
            is_mqtt=False)

        if properties.reply_to is not None:
            reply_msg = self.form_response_json(
                request_id=req_id,
                status_code=status_code,
                reply_body=reply_body)
            LOGGER.debug(f"reply: {reply_body}")

            self.send_response(reply_msg, properties)

    def send_response(self, reply_msg, properties):
        reply_properties = pika.BasicProperties(
            correlation_id=properties.correlation_id)
        self._publish_lock.acquire()
        try:
            self._channel.basic_publish(
                exchange=properties.headers['replyToExchange'],
                routing_key=properties.reply_to,
                body=json.dumps(reply_msg),
                properties=reply_properties)
        finally:
            self._publish_lock.release()

    def send_too_many_requests_response(self, properties, body):
        if properties.reply_to is not None:
            body_json = utils.str_to_json(body, self.fsencoding)[0]
            reply_msg = self.form_response_json(
                request_id=body_json['id'],
                status_code=requests.codes.too_many_requests,
                reply_body=constants.TOO_MANY_REQUESTS_BODY)
            LOGGER.debug(f"reply: {constants.TOO_MANY_REQUESTS_BODY}")
            self.send_response(reply_msg, properties)

    def on_message(self, unused_channel, basic_deliver, properties, body):
        # No longer processing messages if server is closing
        if self._closing:
            return

        self.acknowledge_message(basic_deliver.delivery_tag)
        if self._ctpe.max_threads_busy():
            self.send_too_many_requests_response(properties, body)
        else:
            self._ctpe.submit(lambda: self.process_amqp_message(properties,
                                                                body,
                                                                basic_deliver))

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
        self._ctpe.shutdown(wait=True)
        if self._connection:
            self._connection.ioloop.start()
        LOGGER.info("Stopped")

    def close_connection(self):
        LOGGER.info("Closing connection")
        self._connection.close()

    def get_num_active_threads(self):
        return self._ctpe.get_num_active_threads()

    def get_num_total_threads(self):
        return self._ctpe.get_num_total_threads()
