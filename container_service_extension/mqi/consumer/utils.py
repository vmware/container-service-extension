# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


import base64
import json
import re
import traceback

import requests

from container_service_extension.common.constants.server_constants import ThreadLocalData  # noqa: E501
from container_service_extension.common.constants.shared_constants import RESPONSE_MESSAGE_KEY  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501
from container_service_extension.exception.exceptions import CseRequestError
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
from container_service_extension.rde.models.common_models import DefEntity
import container_service_extension.server.request_dispatcher as request_dispatcher  # noqa: E501


# Note : Only being used by AMQP to reject request that has been already
# processed, or are being currently processed.
def get_request_id(request_msg, fsencoding):
    """."""
    request_id = None
    try:
        msg_json = json.loads(request_msg.decode(fsencoding))[0]
        request_id = msg_json['id']
    except Exception:
        LOGGER.error(traceback.format_exc())
    return request_id


def get_response_fields(request_msg, fsencoding, is_mqtt, mqtt_publisher=None):
    """Get the msg json and response fields request message."""
    msg_json, request_id = None, None
    try:
        # Parse the message
        if is_mqtt:
            payload_json = json.loads(request_msg.payload.decode(fsencoding))
            http_req_json = json.loads(base64.b64decode(
                payload_json['httpRequest']))
            request_id = payload_json["headers"]["requestId"]
            msg_json = http_req_json['message']

            # Use api access token as authorization token -- this may involve
            # overwriting the current authorization token
            msg_json['headers']['Authorization'] = \
                'Bearer ' + http_req_json['securityContext']['apiAccessToken']
        else:
            msg_json = json.loads(request_msg.decode(fsencoding))[0]
            request_id = msg_json['id']

        thread_local_data.set_thread_local_data(ThreadLocalData.REQUEST_ID, request_id)  # noqa: E501
        thread_local_data.set_thread_local_data(ThreadLocalData.USER_AGENT, msg_json['headers'].get('User-Agent'))  # noqa: E501
        result = request_dispatcher.process_request(msg_json, mqtt_publisher=mqtt_publisher)  # noqa: E501
        status_code = result['status_code']
        reply_body = result['body']

    except Exception as e:
        if isinstance(e, CseRequestError):
            status_code = e.status_code
        else:
            status_code = requests.codes.internal_server_error
        reply_body = {RESPONSE_MESSAGE_KEY: str(e)}

        tb = traceback.format_exc()
        LOGGER.error(tb)
    return msg_json, reply_body, status_code, request_id


def str_to_json(json_str, fsencoding):
    return json.loads(json_str.decode(fsencoding))


def format_response_body(body, fsencoding):
    return base64.b64encode(body.encode()).decode(fsencoding)


def get_task_href(body):
    if type(body) != dict:
        return None

    if body.get('entity') is not None and \
            body['entity'].get('status') is not None:
        rde = DefEntity(**body)
        return rde.entity.status.task_href
    return None


def get_task_path_from_reply_body(body):
    if type(body) != dict:
        return None

    task_href = get_task_href(body)
    if task_href is None:
        return None

    return re.search('/api/task/.*', task_href).group()
