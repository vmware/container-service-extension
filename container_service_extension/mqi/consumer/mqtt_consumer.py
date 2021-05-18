# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import ssl
import sys
from typing import Optional

import paho.mqtt.client as mqtt
import requests

from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.mqi.consumer.constants as constants
from container_service_extension.mqi.consumer.consumer_thread_pool_executor \
    import ConsumerThreadPoolExecutor
from container_service_extension.mqi.consumer.mqtt_publisher import MQTTPublisher  # noqa: E501
import container_service_extension.mqi.consumer.utils as utils
import container_service_extension.server.behavior_dispatcher as behavior_dispatcher  # noqa: E501


class MQTTConsumer:
    def __init__(self,
                 url,
                 listen_topic,
                 respond_topic,
                 verify_ssl,
                 token,
                 client_username,
                 num_processors):
        self.url = url
        self.listen_topic = listen_topic
        self.respond_topic = respond_topic
        self.verify_ssl = verify_ssl
        self.token = token
        self.client_username = client_username
        self.num_processors = num_processors
        self.fsencoding = sys.getfilesystemencoding()
        self._mqtt_client = None
        self._mqtt_publisher: Optional[MQTTPublisher] = None
        self._ctpe = ConsumerThreadPoolExecutor(self.num_processors)
        self._is_closing = False

    def process_behavior_message(self, msg_json):
        task_id: str = msg_json['headers']['taskId']
        entity_id: str = msg_json['headers']['entityId']
        behavior_id: str = msg_json['headers']['behaviorId']
        payload: dict = json.loads(msg_json['payload'])
        request_id: str = payload['_metadata']['requestId']
        LOGGER.debug(f"Received behavior invocation: {behavior_id} on "
                     f"entityId:{entity_id} with requestId: {request_id}")
        payload = behavior_dispatcher.process_behavior_request(
            msg_json, self._mqtt_publisher)

        response_json = self._mqtt_publisher.construct_behavior_response_json(
            task_id=task_id,
            entity_id=entity_id,
            payload=payload)
        self._mqtt_publisher.send_response(response_json)
        LOGGER.debug(f'MQTT response: {response_json}')

    def process_mqtt_message(self, msg):
        msg_json = json.loads(msg.payload.decode(self.fsencoding))
        if msg_json.get('type', None) == 'BEHAVIOR_INVOCATION':   # noqa: E501
            self.process_behavior_message(msg_json=msg_json)
        else:
            msg_json, reply_body, status_code, req_id = utils.get_response_fields(  # noqa: E501
                request_msg=msg,
                fsencoding=self.fsencoding,
                is_mqtt=True,
                mqtt_publisher=self._mqtt_publisher)

            LOGGER.debug(f"Received message with request_id: {req_id}, mid: "
                         f"{msg.mid}, and msg json: {msg_json}")

            task_path = utils.get_task_path_from_reply_body(reply_body)
            reply_body_str = json.dumps(reply_body)
            response_json = self._mqtt_publisher.construct_response_json(
                request_id=req_id,
                status_code=status_code,
                reply_body_str=reply_body_str,
                task_path=task_path)

            self._mqtt_publisher.send_response(response_json)
            LOGGER.debug(f'MQTT response: {response_json}')

    def send_too_many_requests_response(self, msg):
        payload_json = utils.str_to_json(msg.payload, self.fsencoding)
        request_id = payload_json["headers"]["requestId"]
        LOGGER.debug(f"Replying with 'too many requests response' for "
                     f"request_id: {request_id} and msg id: {msg.mid}")
        response_json = self._mqtt_publisher.construct_response_json(
            request_id=request_id,
            status_code=requests.codes.too_many_requests,
            reply_body_str=constants.TOO_MANY_REQUESTS_BODY)
        self._mqtt_publisher.send_response(response_json)

    def connect(self):
        def on_connect(mqtt_client, userdata, flags, rc):
            LOGGER.info(f'MQTT client connected with result code {rc} and '
                        f'flags {flags}')
            mqtt_client.subscribe(self.listen_topic, qos=constants.QOS_LEVEL)

        def on_message(mqtt_client, userdata, msg):
            # No longer processing messages if server is closing
            if self._is_closing:
                return
            if self._ctpe.max_threads_busy():
                self.send_too_many_requests_response(msg)
            else:
                self._ctpe.submit(lambda: self.process_mqtt_message(msg))

        def on_subscribe(mqtt_client, userdata, msg_id, given_qos):
            LOGGER.info(f'MQTT client subscribed with given_qos: {given_qos}')

        def on_disconnect(mqtt_client, userdata, rc):
            LOGGER.info(f'MQTT disconnect with reason: {rc}')

        self._mqtt_client = mqtt.Client(client_id=constants.MQTT_CLIENT_ID,
                                        transport=constants.TRANSPORT_WSS)
        self._mqtt_client.username_pw_set(username=self.client_username,
                                          password=self.token)
        cert_req = ssl.CERT_REQUIRED if self.verify_ssl else ssl.CERT_NONE
        self._mqtt_client.tls_set(cert_reqs=cert_req)
        self._mqtt_client.ws_set_options(path=constants.MQTT_BROKER_PATH)

        # Setup callbacks
        self._mqtt_client.on_connect = on_connect
        self._mqtt_client.on_message = on_message
        self._mqtt_client.on_disconnect = on_disconnect
        self._mqtt_client.on_subscribe = on_subscribe

        # Set the mqtt publisher
        self._mqtt_publisher = MQTTPublisher(mqtt_client=self._mqtt_client,
                                             respond_topic=self.respond_topic,
                                             fsencoding=self.fsencoding)

        try:
            self._mqtt_client.connect(self.url,
                                      port=constants.MQTT_CONNECT_PORT)
        except Exception as e:
            LOGGER.error(f'MQTT client connection error: {e}')
            raise
        self._mqtt_client.loop_forever()

    def run(self):
        self.connect()

    def stop(self):
        LOGGER.info("MQTT consumer stopping")
        self._is_closing = True
        self._ctpe.shutdown(wait=True)  # Let jobs finish before disconnecting
        if self._mqtt_client:
            self._mqtt_client.disconnect()

    def get_num_active_threads(self):
        return self._ctpe.get_num_active_threads()

    def get_num_total_threads(self):
        return self._ctpe.get_num_total_threads()
