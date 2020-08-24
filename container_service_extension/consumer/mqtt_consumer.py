from asyncio import Lock
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import ssl
import sys

import paho.mqtt.client as mqtt

import container_service_extension.consumer.constants as constants
import container_service_extension.consumer.utils as utils
import container_service_extension.logger as logger


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

        self.tpe = ThreadPoolExecutor(constants.NUM_TPE_WORKERS)
        self.futures = []
        self.publish_lock = Lock()

    async def process_mqtt_message(self, msg):
        payload_json = json.loads(msg.payload.decode())
        http_req_json = json.loads(base64.b64decode(
            payload_json['httpRequest']))
        message_json = http_req_json['message']
        reply_body, status_code = utils.get_reply_body_and_status_code(
            message_json)

        response_json = {
            "type": "API_RESPONSE",
            "headers": {
                "requestId": payload_json["headers"]["requestId"],
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

        await self.publish_lock.acquire()
        try:
            pub_ret = self.mqtt_client.publish(topic=self.respond_topic,
                                               payload=json.dumps(response_json),  # noqa: E501
                                               qos=constants.QOS_LEVEL,
                                               retain=False)
        finally:
            self.publish_lock.release()
        logger.SERVER_LOGGER.info(f"pub_ret (rc, msg_id): {pub_ret}")

    def connect(self):
        def on_connect(client, userdata, flags, rc):
            logger.SERVER_LOGGER.info(f'MQTT client connected with result code'
                                      f' {rc} and flags {flags}')
            client.subscribe(self.listen_topic, qos=constants.QOS_LEVEL)

        def on_message(client, userdata, msg):
            future = self.tpe.submit(self.process_mqtt_message, msg)
            self.futures.append(future)
            debug_check = future.done()  # TODO: remove
            logger.SERVER_LOGGER.info(f'debug_check: {debug_check}')

        def on_subscribe(client, userdata, msg_id, given_qos):
            logger.SERVER_LOGGER.info(f'MQTT client subscribed with given_qos:'
                                      f'{given_qos}')

        def on_disconnect(client, userdata, rc):
            logger.SERVER_LOGGER.info(f'MQTT disconnect with reason: {rc}')

        self.mqtt_client = mqtt.Client(client_id=constants.CLIENT_ID,
                                       transport=constants.TRANSPORT_WSS)
        self.mqtt_client.username_pw_set(username=self.client_username,
                                         password=self.token)
        cert_req = ssl.CERT_REQUIRED if self.verify_ssl else ssl.CERT_NONE
        self.mqtt_client.tls_set(cert_reqs=cert_req)
        self.mqtt_client.ws_set_options(path=constants.BROKER_PATH)

        # Setup callbacks
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_subscribe = on_subscribe

        try:
            self.mqtt_client.connect(self.url,
                                     port=constants.MQTT_CONNECT_PORT)
        except Exception as e:
            logger.SERVER_LOGGER.error(f'connection error: {e}')
            raise e
        self.mqtt_client.loop_forever()

    def run(self):
        self.connect()

    def stop(self):
        if self.mqtt_client:
            self.mqtt_client.disconnect()
