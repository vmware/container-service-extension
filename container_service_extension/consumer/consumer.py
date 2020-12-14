# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.consumer.amqp_consumer import AMQPConsumer
from container_service_extension.consumer.mqtt_consumer import MQTTConsumer
import container_service_extension.server_constants as server_constants
from container_service_extension.server_constants import MQTTExtKey, \
    MQTTExtTokenKey
from container_service_extension.server_utils import should_use_mqtt_protocol


class MessageConsumer:
    """Returns the consumer class for the correct message protocol."""

    def __new__(cls, config, num_processors):
        """Create the correct message consumer class for the message protocol.

        :param dict config: content of the CSE config file.
        :param int num_processors: number of processors for thread pool
            executor

        :return: instance of appropriate message protocol consumer
        """
        if should_use_mqtt_protocol(config):
            mqtt = config['mqtt']
            return MQTTConsumer(
                url=config['vcd']['host'],
                listen_topic=mqtt[MQTTExtKey.EXT_LISTEN_TOPIC],
                respond_topic=mqtt[MQTTExtKey.EXT_RESPOND_TOPIC],
                verify_ssl=mqtt['verify_ssl'],
                token=mqtt[MQTTExtTokenKey.TOKEN],
                client_username=f'{server_constants.MQTT_EXTENSION_VENDOR}/'
                                f'{server_constants.CSE_SERVICE_NAME}/'
                                f'{server_constants.MQTT_EXTENSION_VERSION}',
                num_processors=num_processors)
        else:
            amqp = config['amqp']
            return AMQPConsumer(
                host=amqp['host'],
                port=amqp['port'],
                vhost=amqp['vhost'],
                username=amqp['username'],
                password=amqp['password'],
                exchange=amqp['exchange'],
                routing_key=amqp['routing_key'],
                num_processors=num_processors)
