import base64
import json
import ssl
import sys
from threading import Lock

import paho.mqtt.client as mqtt
import requests

from container_service_extension.consumer.consumer_thread_pool_executor \
    import ConsumerThreadPoolExecutor
import container_service_extension.consumer.utils as utils
import container_service_extension.logger as logger


NUM_TPE_WORKERS = 4

BROKER_PATH = '/messaging/mqtt'
CLIENT_ID = 'pythonMQTT'
MQTT_CONNECT_PORT = 443
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

        self.ctpe = ConsumerThreadPoolExecutor(NUM_TPE_WORKERS)
        self.publish_lock = Lock()

    def form_response_json(self, request_id, status_code, reply_body):
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
                decode(self.fsencoding)
            }
        }
        return response_json

    def process_mqtt_message(self, msg):
        payload_json = utils.str_to_json(msg.payload, self.fsencoding)
        http_req_json = json.loads(base64.b64decode(
            payload_json['httpRequest']))
        message_json = http_req_json['message']
        reply_body, status_code = utils.get_reply_body_and_status_code(
            message_json)

        response_json = self.form_response_json(
            request_id=payload_json["headers"]["requestId"],
            status_code=status_code,
            reply_body=reply_body)

        self.send_response(response_json)

    def send_response(self, response_json):
        self.publish_lock.acquire()
        try:
            pub_ret = self.mqtt_client.publish(topic=self.respond_topic,
                                               payload=json.dumps(
                                                   response_json),
                                               qos=QOS_LEVEL,
                                               retain=False)
        finally:
            self.publish_lock.release()
        logger.SERVER_LOGGER.info(f"pub_ret (rc, msg_id): {pub_ret}")

    def send_too_many_requests_response(self, msg):
        payload_json = utils.str_to_json(msg.payload, self.fsencoding)
        response_json = self.form_response_json(
            request_id=payload_json["headers"]["requestId"],
            status_code=requests.codes.too_many_requests,
            reply_body='[{"Server is handling too many requests. '
                       'Please wait and try again.":""}]')
        self.send_response(response_json)

    def connect(self):
        def on_connect(client, userdata, flags, rc):
            logger.SERVER_LOGGER.info(f'MQTT client connected with result code'
                                      f' {rc} and flags {flags}')
            client.subscribe(self.listen_topic, qos=QOS_LEVEL)

        def on_message(client, userdata, msg):
            if self.ctpe.max_workers_busy():
                self.send_too_many_requests_response(msg)
            else:
                self.ctpe.submit(lambda: self.process_mqtt_message(msg))

        def on_subscribe(client, userdata, msg_id, given_qos):
            logger.SERVER_LOGGER.info(f'MQTT client subscribed with given_qos:'
                                      f'{given_qos}')

        def on_disconnect(client, userdata, rc):
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
            self.mqtt_client.connect(self.url,
                                     port=MQTT_CONNECT_PORT)
        except Exception as e:
            logger.SERVER_LOGGER.error(f'connection error: {e}')
            raise e
        self.mqtt_client.loop_forever()

    def run(self):
        self.connect()

    def stop(self):
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        self.ctpe.shutdown(wait=True)
