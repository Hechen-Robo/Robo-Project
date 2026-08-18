from __future__ import annotations

from collections.abc import Callable

import paho.mqtt.client as mqtt

from vda5050_fms.config import Settings
from vda5050_fms.connection_handler import (
    ConnectionMessageHandler,
    UnexpectedConnectionMessageError,
)
from vda5050_fms.models import (
    ConnectionMessage,
    MessageValidationError,
)
from vda5050_fms.mqtt_client import create_mqtt_client
from vda5050_fms.topics import TopicLayout

ConnectionMessageCallback = Callable[
    [ConnectionMessage],
    None,
]
ErrorCallback = Callable[[Exception], None]


class ConnectionSubscriberError(RuntimeError):
    """Raised when the MQTT subscriber cannot operate."""


class ConnectionSubscriber:
    """Subscribe to one robot's VDA 5050 connection topic."""

    def __init__(
        self,
        settings: Settings,
        on_connection_message: ConnectionMessageCallback,
        on_error: ErrorCallback,
    ) -> None:
        self._settings = settings
        self._on_connection_message = on_connection_message
        self._on_error = on_error

        topic_layout = TopicLayout.from_settings(settings)
        self._topic = topic_layout.build("connection")

        self._handler = (
            ConnectionMessageHandler.from_settings(settings)
        )

        self._client = create_mqtt_client(
            settings,
            reconnect_on_failure=True,
        )

        self._client.on_connect = self._handle_connect
        self._client.on_connect_fail = (
            self._handle_connect_fail
        )
        self._client.on_message = self._handle_message

    @property
    def topic(self) -> str:
        return self._topic

    def run(self) -> None:
        """Connect and block while processing MQTT messages."""

        self._client.connect_async(
            host=self._settings.mqtt_host,
            port=self._settings.mqtt_port,
            keepalive=self._settings.mqtt_keepalive,
        )

        self._client.loop_forever(
            retry_first_connection=True
        )

    def stop(self) -> None:
        """Request a clean MQTT disconnection."""

        self._client.disconnect()

    def _handle_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del userdata, flags, properties

        if reason_code.is_failure:
            self._on_error(
                ConnectionSubscriberError(
                    "MQTT connection was rejected: "
                    f"{reason_code}"
                )
            )
            return

        result, _message_id = client.subscribe(
            self._topic,
            qos=1,
        )

        if result != mqtt.MQTT_ERR_SUCCESS:
            self._on_error(
                ConnectionSubscriberError(
                    "MQTT subscription failed: "
                    f"{mqtt.error_string(result)}"
                )
            )

    def _handle_connect_fail(
        self,
        client: mqtt.Client,
        userdata: object,
    ) -> None:
        del client, userdata

        self._on_error(
            ConnectionSubscriberError(
                "MQTT Broker connection attempt failed"
            )
        )

    def _handle_message(
        self,
        client: mqtt.Client,
        userdata: object,
        mqtt_message: mqtt.MQTTMessage,
    ) -> None:
        del client, userdata

        if mqtt_message.topic != self._topic:
            self._on_error(
                ConnectionSubscriberError(
                    "Message received on unexpected topic: "
                    f"{mqtt_message.topic}"
                )
            )
            return

        try:
            connection_message = (
                self._handler.parse_payload(
                    mqtt_message.payload
                )
            )
        except (
            MessageValidationError,
            UnexpectedConnectionMessageError,
        ) as exc:
            self._on_error(exc)
            return

        self._on_connection_message(connection_message)