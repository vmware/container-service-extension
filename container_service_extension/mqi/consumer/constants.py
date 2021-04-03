# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.shared_constants import CSE_SERVER_BUSY_KEY  # noqa: E501

# Shared between AMQP and MQTT consumers
TOO_MANY_REQUESTS_BODY = f'{{"{CSE_SERVER_BUSY_KEY}":' \
                         f'"Please wait and try again."}}'

# Used by MQTT consumer
MQTT_BROKER_PATH = '/messaging/mqtt'
MQTT_CLIENT_ID = 'cseMQTT'
MQTT_CONNECT_PORT = 443
TRANSPORT_WSS = 'websockets'
QOS_LEVEL = 2  # No duplicate messages

# Used by only AMQP consumer
MAX_PROCESSING_REQUEST_CACHE_SIZE = 1000
