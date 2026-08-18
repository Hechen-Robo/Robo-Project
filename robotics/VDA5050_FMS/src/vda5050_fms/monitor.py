from __future__ import annotations

import json
import logging
import threading
from typing import Any

from vda5050_fms.config import Settings
from vda5050_fms.mqtt_client import JsonMqttClient
from vda5050_fms.topics import TopicLayout
from vda5050_fms.validation import SchemaRegistry, SchemaValidationError


LOGGER = logging.getLogger(__name__)

ROBOT_TO_FMS_TOPICS = {
    "state": 0,
    "visualization": 0,
    "connection": 1,
    "factsheet": 0,
}


class BrokerMonitor:
    """Read-only monitor for messages published by real or simulated robots."""

    def __init__(self, settings: Settings, *, verbose: bool = False) -> None:
        self.settings = settings
        self.verbose = verbose
        self.registry = SchemaRegistry(settings.vda_version)
        self.layout = TopicLayout(
            settings.interface_name,
            settings.vda_version,
            settings.manufacturer,
            settings.serial_number,
        )
        self.client = JsonMqttClient(settings)
        self._stopped = threading.Event()

        for topic_name, qos in ROBOT_TO_FMS_TOPICS.items():
            self.client.add_subscription(
                self.layout.wildcard_topic(topic_name), qos, self._handle_message
            )

    def run(self) -> None:
        self.client.connect()
        LOGGER.info("Read-only monitor started; press Ctrl+C to stop")
        try:
            self._stopped.wait()
        except KeyboardInterrupt:
            LOGGER.info("Stopping monitor")
        finally:
            self.client.disconnect()

    def stop(self) -> None:
        self._stopped.set()

    def _handle_message(
        self, topic: str, payload: dict[str, Any], retained: bool
    ) -> None:
        try:
            parts = self.layout.parse(topic)
            self.registry.validate(parts.topic_name, payload)
            self._verify_topic_identity(parts.manufacturer, parts.serial_number, payload)
        except (ValueError, SchemaValidationError) as exc:
            LOGGER.error("INVALID %s: %s", topic, exc)
            if self.verbose:
                LOGGER.error("Payload: %s", json.dumps(payload, ensure_ascii=False))
            return

        summary = self._summary(parts.topic_name, payload)
        retained_text = " retained" if retained else ""
        LOGGER.info(
            "VALID%s %s/%s %-13s %s",
            retained_text,
            parts.manufacturer,
            parts.serial_number,
            parts.topic_name,
            summary,
        )
        if self.verbose:
            LOGGER.info("Payload: %s", json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _verify_topic_identity(
        manufacturer: str,
        serial_number: str,
        payload: dict[str, Any],
    ) -> None:
        if payload.get("manufacturer") != manufacturer:
            raise ValueError(
                "manufacturer in payload does not match the MQTT topic"
            )
        if payload.get("serialNumber") != serial_number:
            raise ValueError("serialNumber in payload does not match the MQTT topic")

    @staticmethod
    def _summary(topic_name: str, payload: dict[str, Any]) -> str:
        if topic_name == "state":
            return (
                f"order={payload.get('orderId')!r} "
                f"update={payload.get('orderUpdateId')} "
                f"lastNode={payload.get('lastNodeId')!r} "
                f"driving={payload.get('driving')} "
                f"errors={len(payload.get('errors', []))}"
            )
        if topic_name == "connection":
            return f"connectionState={payload.get('connectionState')}"
        if topic_name == "visualization":
            position = payload.get("agvPosition", {})
            return f"x={position.get('x')} y={position.get('y')}"
        if topic_name == "factsheet":
            specification = payload.get("typeSpecification", {})
            return f"series={specification.get('seriesName')!r}"
        return ""
