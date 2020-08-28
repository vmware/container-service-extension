import base64
import json
import traceback

import requests

from container_service_extension.exceptions import CseRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_processor as request_processor
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY


def get_response_fields(msg, fsencoding, is_amqp):
    """Get the reply body, status code, and request id from the message."""
    try:
        # Parse the message
        if is_amqp:
            msg_json = json.loads(msg.decode(fsencoding))[0]
            request_id = msg_json['id']
        else:
            payload_json = json.loads(msg.payload.decode(fsencoding))
            http_req_json = json.loads(base64.b64decode(
                payload_json['httpRequest']))
            request_id = payload_json["headers"]["requestId"]
            msg_json = http_req_json['message']

        result = request_processor.process_request(msg_json)
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

    return reply_body, status_code, request_id
