import json
from threading import Lock

import requests

from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.mqi.consumer.constants as constants
import container_service_extension.mqi.consumer.utils as utils
from container_service_extension.rde.behaviors.behavior_model import \
    BehaviorTaskStatus


class MQTTPublisher:
    """Publish messages to MQTT.

    It provides methods to construct and send traditional MQTT messages and
    Behavior type MQTT messages.

    It holds a lock to avoid concurrent message publishing to MQTT. Hence,
    there can only exist one instance of this class and it cannot be
    initialized outside of the MQTTConsumer. Locking mechanism needs to be
    changed if we ever decide to have more than one instance of MQTTConsumer.
    """

    def __init__(self, mqtt_client, respond_topic, fsencoding):
        self.mqtt_client = mqtt_client
        self.respond_topic = respond_topic
        self._publish_lock = Lock()
        self._fsencoding = fsencoding

    def construct_response_json(self, request_id, status_code, reply_body_str,
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
                                                   self._fsencoding)
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

    def construct_behavior_payload(self, message='Cluster operation',
                                   status=BehaviorTaskStatus.RUNNING.value,
                                   progress=None, error_details=None):
        """Construct the (task) payload portion of the Behavior Response.

        :param dict error_details: Dict form of type BehaviorError
        {'majorErrorCode':'500','minorErrorCode':None,'message':None}
        :param str message: Task update message
        :param str status: Status of the task to be updated.
        :param int progress:

        :return: The constructed task payload.
        :rtype: dict
        """
        payload = {
            "status": status
        }
        if status == 'running':
            payload['operation'] = message
            if progress:
                payload['progress'] = progress
        elif status == 'success':
            payload['result'] = {'resultContent': message}
        elif status == 'error':
            payload['error'] = error_details
        return payload

    def construct_behavior_response_json(self, task_id, entity_id, payload):
        """Construct the behavior response to be published onto MQTT.

        :param str task_id:
        :param str entity_id: Id of the entity
        :param dict payload: Payload could be of type task update (or) success
        (or) error payload.
        :return: Behavior response
        :rtype: dict
        """
        response_json = {
            "type": "BEHAVIOR_RESPONSE",
            "headers": {
                "taskId": task_id,
                "entityId": entity_id,
                "contentType": "application/vnd.vmware.vcloud.task+json",
            },
            "payload": json.dumps(payload)
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
