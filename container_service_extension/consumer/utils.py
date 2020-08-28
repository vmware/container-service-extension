import base64
import json
import traceback

import requests

from container_service_extension.exceptions import CseRequestError
from container_service_extension.exceptions import NotAcceptableRequestError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.request_processor as request_processor
from container_service_extension.shared_constants import RESPONSE_MESSAGE_KEY


def redact_http_req_debug_output(http_req_json):
    """Shorten the string format for the debug output."""
    if http_req_json.get('securityContext') is not None and \
            http_req_json['securityContext'].get('rights') is not None:
        # Form redacted output
        security_context_rights = http_req_json['securityContext']['rights']
        http_req_json['securityContext']['rights'] = \
            [f"redacted {len(security_context_rights)} rights"]
        debug_output = json.dumps(http_req_json)

        # Restore redacted field
        http_req_json['securityContext']['rights'] = security_context_rights
    else:
        debug_output = json.dumps(http_req_json)
    return debug_output


def str_to_json(json_str, fsencoding):
    return json.loads(json_str.decode(fsencoding))


def format_response_body(body, fsencoding):
    return base64.b64encode(body.encode()).decode(fsencoding)


def get_reply_body_and_status_code(msg_json):
    try:
        response_format = None
        accept_header = msg_json['headers']['Accept'].lower()
        accept_header = accept_header.split(';')[0]
        tokens = accept_header.split('/')
        if len(tokens) > 1:
            if tokens[0] in ('*', 'application'):
                response_format = tokens[1]
        if not response_format:
            response_format = tokens[0]
        response_format = response_format.replace('*+', '')

        if not ('json' in response_format or '*' == response_format):
            raise NotAcceptableRequestError(
                error_message="CSE can only serve response as json.")

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

    return reply_body, status_code
