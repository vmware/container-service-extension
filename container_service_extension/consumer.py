from container_service_extension.amqp_consumer import AMQPConsumer
from container_service_extension.mqtt_consumer import MQTTConsumer
from container_service_extension.utils import should_use_mqtt_protocol


class MessageConsumer:
    """Returns the consumer class for the correct message protocol."""

    def __new__(cls, config):
        """Create the correct message consumer class for the message protocol.

        :param dict config: content of the CSE config file.

        :return: instance of appropriate message protocol consumer
        """
        if should_use_mqtt_protocol(config):
            return MQTTConsumer()
        else:
            amqp = config['amqp']
            return AMQPConsumer(
                amqp['host'], amqp['port'], amqp['ssl'], amqp['vhost'],
                amqp['username'], amqp['password'], amqp['exchange'],
                amqp['routing_key'])
