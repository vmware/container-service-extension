# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64
import json
import ssl
import sys

import paho.mqtt.client as mqtt

import container_service_extension.consumer.utils as utils
import container_service_extension.logger as logger

BROKER_PATH = '/messaging/mqtt'
CLIENT_ID = 'pythonMQTT'
CONNECT_PORT = 443
TRANSPORT_WSS = 'websockets'
QOS_LEVEL = 2  # No duplicate messages


class MQTTConsumer:
    def __init__(self,
                 url,
                 listen_topic,
                 respond_topic,
                 verify_ssl,
                 token,
                 client_username):
        self.url = url
        self.listen_topic = listen_topic
        self.respond_topic = respond_topic
        self.verify_ssl = verify_ssl
        self.token = token
        self.client_username = client_username
        self.fsencoding = sys.getfilesystemencoding()
        self.mqtt_client = None

    def connect(self):
        def on_connect(mqtt_client, userdata, flags, rc):
            logger.SERVER_LOGGER.info(f'MQTT mqtt_client connected with '
                                      f'result code {rc} and flags {flags}')
            mqtt_client.subscribe(self.listen_topic, qos=QOS_LEVEL)

        def on_message(mqtt_client, userdata, msg):
            reply_body, status_code, request_id = utils.get_response_fields(
                msg=msg,
                fsencoding=self.fsencoding,
                is_amqp=False)

            response_json = {
                "type": "API_RESPONSE",
                "headers": {
                    "requestId": request_id,
                },
                "httpResponse": {
                    "statusCode": status_code,
                    "headers": {
                        "Content-Type": "application/json",
                        'Content-Length': len(reply_body)
                    },
                    "body": base64.b64encode(reply_body.encode()).
                    decode(sys.getfilesystemencoding())
                }
            }

            pub_ret = mqtt_client.publish(topic=self.respond_topic,
                                          payload=json.dumps(response_json),
                                          qos=QOS_LEVEL,
                                          retain=False)
            logger.SERVER_LOGGER.info(f"pub_ret (rc, msg_id): {pub_ret}")

        def on_subscribe(mqtt_client, userdata, msg_id, given_qos):
            logger.SERVER_LOGGER.info(f'MQTT mqtt_client subscribed with '
                                      f'given_qos: {given_qos}')

        def on_disconnect(mqtt_client, userdata, rc):
            logger.SERVER_LOGGER.info(f'MQTT disconnect with reason: {rc}')

        self.mqtt_client = mqtt.Client(client_id=CLIENT_ID,
                                       transport=TRANSPORT_WSS)
        self.mqtt_client.username_pw_set(username=self.client_username,
                                         password=self.token)
        cert_req = ssl.CERT_REQUIRED if self.verify_ssl else ssl.CERT_NONE
        self.mqtt_client.tls_set(cert_reqs=cert_req)
        self.mqtt_client.ws_set_options(path=BROKER_PATH)

        # Setup callbacks
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_subscribe = on_subscribe

        try:
            self.mqtt_client.connect(self.url, port=CONNECT_PORT)
        except Exception as e:
            logger.SERVER_LOGGER.error(f'connection error: {e}')
            raise e
        self.mqtt_client.loop_forever()

    def run(self):
        self.connect()

    def stop(self):
        if self.mqtt_client:
            self.mqtt_client.disconnect()
