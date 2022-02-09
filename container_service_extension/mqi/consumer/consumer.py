# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
from container_service_extension.common.constants.server_constants import MQTTExtKey, MQTTExtTokenKey  # noqa: E501
from container_service_extension.common.utils.server_utils import should_use_mqtt_protocol  # noqa: E501
from container_service_extension.config.server_config import ServerConfig
from container_service_extension.mqi.consumer.amqp_consumer import AMQPConsumer
from container_service_extension.mqi.consumer.mqtt_consumer import MQTTConsumer


class MessageConsumer:
    """Returns the consumer class for the correct message protocol."""

    def __new__(cls, config: ServerConfig, num_processors: int):
        """Create the correct message consumer class for the message protocol.

        :param ServerConfig config: content of the CSE config file.
        :param int num_processors: number of processors for thread pool
            executor

        :return: instance of appropriate message protocol consumer
        """
        if should_use_mqtt_protocol(config):
            return MQTTConsumer(
                url=config.get_value_at('vcd.host'),
                listen_topic=config.get_value_at(f'mqtt.{MQTTExtKey.EXT_LISTEN_TOPIC}'),
                respond_topic=config.get_value_at(f'mqtt.{MQTTExtKey.EXT_RESPOND_TOPIC}'),
                verify_ssl=config.get_value_at(f'mqtt.verify_ssl'),
                token=config.get_value_at(f'mqtt.{MQTTExtTokenKey.TOKEN}'),
                client_username=f'{server_constants.MQTT_EXTENSION_VENDOR}/'
                                f'{server_constants.CSE_SERVICE_NAME}/'
                                f'{server_constants.MQTT_EXTENSION_VERSION}',
                num_processors=num_processors
            )
        else:
            return AMQPConsumer(
                host=config.get_value_at('amqp.host'),
                port=config.get_value_at('amqp.port'),
                vhost=config.get_value_at('amqp.vhost'),
                username=config.get_value_at('amqp.username'),
                password=config.get_value_at('amqp.password'),
                exchange=config.get_value_at('amqp.exchange'),
                routing_key=config.get_value_at('amqp.routing_key'),
                num_processors=num_processors
            )
