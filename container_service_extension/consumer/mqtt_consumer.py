import base64
import json
import ssl
import sys

import paho.mqtt.client as mqtt

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

    def connect(self):
        def on_connect(client, userdata, flags, rc):
            logger.SERVER_LOGGER.info(f'MQTT client connected with result code'
                                      f' {rc} and flags {flags}')
            client.subscribe(self.listen_topic, qos=2)

        def on_message(client, userdata, msg):
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

            pub_ret = client.publish(topic=self.respond_topic,
                                     payload=json.dumps(response_json),
                                     qos=2, retain=False)
            logger.SERVER_LOGGER.info(f"pub_ret (rc, msg_id): {pub_ret}")

        def on_subscribe(client, userdata, msg_id, given_qos):
            logger.SERVER_LOGGER.info(f'MQTT client subscribed with given_qos:'
                                      f'{given_qos}')

        def on_disconnect(client, userdata, rc):
            logger.SERVER_LOGGER.info(f'MQTT disconnect with reason: {rc}')

        client_id = 'PythonMQTT' # TODO: try other client id
        mqtt_client = mqtt.Client(client_id=client_id, transport='websockets')
        mqtt_client.username_pw_set(username=self.client_username,
                                    password=self.token)
        cert_req = ssl.CERT_REQUIRED if self.verify_ssl else ssl.CERT_NONE
        mqtt_client.tls_set(cert_reqs=cert_req)
        mqtt_client.ws_set_options(headers={}, path='/messaging/mqtt')

        # Setup callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_subscribe = on_subscribe

        try:
            mqtt_client.connect(self.url, port=443)
        except Exception as e:
            logger.SERVER_LOGGER.error(f'connection error: {e}')
            raise e
        mqtt_client.loop_forever()

    def run(self):
        self.connect()

    def stop(self):
        pass
