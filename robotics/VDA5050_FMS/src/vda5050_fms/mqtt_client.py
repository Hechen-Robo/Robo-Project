from __future__ import annotations

from threading import Event
from uuid import uuid4

import paho.mqtt.client as mqtt

from vda5050_fms.config import Settings


class MqttConnectionError(RuntimeError):
    """Raised when an MQTT Broker rejects or cannot accept a connection."""


def create_mqtt_client(settings: Settings,*,reconnect_on_failure: bool = False,) -> mqtt.Client:
    """Create and configure an MQTT client without connecting it."""

    client_id = f"vda5050-fms-{uuid4().hex[:12]}"

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
        reconnect_on_failure=reconnect_on_failure,
    )

    if settings.mqtt_username:
        client.username_pw_set(
            username=settings.mqtt_username,
            password=settings.mqtt_password,
        )

    if settings.mqtt_tls:
        client.tls_set()

    return client


def check_mqtt_connection(
    settings: Settings,
    timeout: float = 10.0,
) -> None:
    """Connect to the Broker once and then disconnect without MQTT traffic."""

    client = create_mqtt_client(settings)

    connection_completed = Event()
    connection_errors: list[str] = []

    def on_connect(
        mqtt_client,
        userdata,
        connect_flags,
        reason_code,
        properties,
    ) -> None:
        if reason_code.is_failure:
            connection_errors.append(
                f"Broker rejected the connection: {reason_code}"
            )

        connection_completed.set()

    def on_connect_fail(
        mqtt_client,
        userdata,
    ) -> None:
        connection_errors.append(
            "TCP connection to the MQTT Broker failed"
        )
        connection_completed.set()

    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail

    client.connect_async(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        keepalive=settings.mqtt_keepalive,
    )

    client.loop_start()

    try:
        if not connection_completed.wait(timeout):
            raise TimeoutError(
                f"MQTT Broker did not respond within {timeout:.1f} seconds"
            )

        if connection_errors:
            raise MqttConnectionError(connection_errors[0])
    finally:
        if client.is_connected():
            client.disconnect()

        client.loop_stop()