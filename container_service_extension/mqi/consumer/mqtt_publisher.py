import json
from threading import Lock

import requests

from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.mqi.consumer.constants as constants
import container_service_extension.mqi.consumer.utils as utils


class MQTTPublisher:
    def __init__(self, mqtt_client, respond_topic):
        self.mqtt_client = mqtt_client
        self.respond_topic = respond_topic
        self._publish_lock = Lock()

    def form_response_json(self, request_id, status_code, reply_body_str,
                           task_path=None):
        response_json = {
            "type": "API_RESPONSE",
            "headers": {
                "requestId": request_id,
            },
            "httpResponse": {
                "statusCode": status_code,
                "headers": {
                    "Content-Type": "application/json",
                    "Content-Length": len(reply_body_str)
                },
                "body": utils.format_response_body(reply_body_str,
                                                   self.fsencoding)
            }
        }

        # Add location header is appropriate status code
        if status_code in (requests.codes.created,
                           requests.codes.accepted,
                           requests.codes.found,
                           requests.codes.see_other) \
                and task_path is not None:
            response_json['httpResponse']['headers']['Location'] = task_path
        return response_json

    def form_behavior_response_json(self, task_id, entity_id, payload, status):
        response_json = {
            "type": "BEHAVIOR_RESPONSE",
            "headers": {
                "taskId": task_id,
                "entityId": entity_id,
                "status": status
            },
            "payload": payload
        }
        return response_json

    def send_response(self, response_json):
        self._publish_lock.acquire()
        try:
            pub_ret = self.mqtt_client.publish(topic=self.respond_topic,
                                               payload=json.dumps(
                                                   response_json),
                                               qos=constants.QOS_LEVEL,
                                               retain=False)
        finally:
            self._publish_lock.release()
        LOGGER.debug(f"publish return (rc, msg_id): {pub_ret}")
