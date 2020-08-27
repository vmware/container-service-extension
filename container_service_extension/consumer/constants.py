# Shared bewteen AMQP and MQTT consumers
TOO_MANY_REQUESTS_BODY = '[{"Server is handling too many requests. ' \
                         'Please wait and try again.":""}]'

# Used by MQTT consumer
MQTT_BROKER_PATH = '/messaging/mqtt'
MQTT_CLIENT_ID = 'pythonMQTT'
MQTT_CONNECT_PORT = 443
TRANSPORT_WSS = 'websockets'
QOS_LEVEL = 2  # No duplicate messages
