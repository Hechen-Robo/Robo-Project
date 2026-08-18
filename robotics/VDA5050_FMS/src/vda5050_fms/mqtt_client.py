from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
import ssl
import threading
from typing import Any

import paho.mqtt.client as mqtt

from vda5050_fms.config import Settings


LOGGER = logging.getLogger(__name__)

MessageHandler = Callable[[str, dict[str, Any], bool], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    topic_filter: str
    qos: int
    handler: MessageHandler


class JsonMqttClient:
    """Small paho wrapper that exchanges JSON objects and reconnects safely."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._connected = threading.Event()
        self._subscriptions: list[Subscription] = []
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            protocol=mqtt.MQTTv311,
            transport=settings.mqtt_transport,
        )
        self._client.enable_logger(LOGGER)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

        if settings.mqtt_username:
            self._client.username_pw_set(
                settings.mqtt_username, settings.mqtt_password
            )
        if settings.mqtt_tls:
            self._client.tls_set(
                ca_certs=(
                    str(settings.mqtt_ca_cert)
                    if settings.mqtt_ca_cert is not None
                    else None
                ),
                certfile=(
                    str(settings.mqtt_client_cert)
                    if settings.mqtt_client_cert is not None
                    else None
                ),
                keyfile=(
                    str(settings.mqtt_client_key)
                    if settings.mqtt_client_key is not None
                    else None
                ),
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self._client.tls_insecure_set(settings.mqtt_tls_insecure)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def add_subscription(
        self, topic_filter: str, qos: int, handler: MessageHandler
    ) -> None:
        if qos not in {0, 1, 2}:
            raise ValueError(f"Invalid MQTT QoS: {qos}")
        subscription = Subscription(topic_filter, qos, handler)
        self._subscriptions.append(subscription)
        if self.is_connected:
            self._client.subscribe(topic_filter, qos=qos)

    def set_will(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        qos: int = 1,
        retain: bool = True,
    ) -> None:
        self._client.will_set(
            topic,
            payload=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            qos=qos,
            retain=retain,
        )

    def connect(self, timeout: float = 10.0) -> None:
        LOGGER.info(
            "Connecting MQTT client %s to %s:%d",
            self.settings.mqtt_client_id,
            self.settings.mqtt_host,
            self.settings.mqtt_port,
        )
        self._client.connect(
            self.settings.mqtt_host,
            self.settings.mqtt_port,
            keepalive=self.settings.mqtt_keepalive,
        )
        self._client.loop_start()
        if not self._connected.wait(timeout):
            self._client.disconnect()
            self._client.loop_stop()
            raise TimeoutError(
                f"MQTT connection was not established within {timeout:.1f} seconds"
            )

    def publish_json(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        qos: int = 0,
        retain: bool = False,
        wait: bool = False,
        timeout: float = 5.0,
    ) -> None:
        if not self.is_connected:
            raise RuntimeError("MQTT client is not connected")
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        info = self._client.publish(topic, encoded, qos=qos, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"Publishing to {topic!r} failed with MQTT result {info.rc}"
            )
        if wait:
            info.wait_for_publish(timeout=timeout)
            if not info.is_published():
                raise TimeoutError(f"MQTT publish to {topic!r} timed out")

    def disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        self._connected.clear()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if getattr(reason_code, "is_failure", False):
            LOGGER.error("MQTT connection rejected: %s", reason_code)
            self._connected.clear()
            return

        LOGGER.info("MQTT connection established")
        self._connected.set()
        for subscription in self._subscriptions:
            result, _message_id = client.subscribe(
                subscription.topic_filter, qos=subscription.qos
            )
            if result != mqtt.MQTT_ERR_SUCCESS:
                LOGGER.error(
                    "Failed to subscribe to %s: MQTT result %s",
                    subscription.topic_filter,
                    result,
                )
            else:
                LOGGER.info("Subscribed to %s", subscription.topic_filter)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        self._connected.clear()
        if reason_code == 0:
            LOGGER.info("MQTT connection closed")
        else:
            LOGGER.warning("MQTT connection lost: %s", reason_code)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        try:
            decoded = message.payload.decode("utf-8")
            payload = json.loads(decoded)
            if not isinstance(payload, dict):
                raise ValueError("VDA MQTT payload must be a JSON object")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            LOGGER.error("Invalid JSON on %s: %s", message.topic, exc)
            return

        for subscription in tuple(self._subscriptions):
            if not mqtt.topic_matches_sub(subscription.topic_filter, message.topic):
                continue
            try:
                subscription.handler(message.topic, payload, message.retain)
            except Exception:
                LOGGER.exception("Message handler failed for %s", message.topic)

