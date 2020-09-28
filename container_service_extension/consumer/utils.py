# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


import base64
import json
import traceback

import requests

from container_service_extension.exceptions import CseRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_processor as request_processor
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY


def get_response_fields(request_msg, fsencoding, is_mqtt):
    """Get the msg json and response fields request message."""
    try:
        # Parse the message
        if is_mqtt:
            payload_json = json.loads(request_msg.payload.decode(fsencoding))
            http_req_json = json.loads(base64.b64decode(
                payload_json['httpRequest']))
            request_id = payload_json["headers"]["requestId"]
            msg_json = http_req_json['message']

            # use api access token as authorization token
            msg_json['headers']['Authorization'] = \
                'Bearer ' + http_req_json['securityContext']['apiAccessToken']
        else:
            msg_json = json.loads(request_msg.decode(fsencoding))[0]
            request_id = msg_json['id']

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
    return msg_json, reply_body, status_code, request_id


def str_to_json(json_str, fsencoding):
    return json.loads(json_str.decode(fsencoding))


def format_response_body(body, fsencoding):
    return base64.b64encode(body.encode()).decode(fsencoding)
