import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

from vda5050_fms.config import Settings
from vda5050_fms.connection_subscriber import (
    ConnectionSubscriber,
    ConnectionSubscriberError,
)
from vda5050_fms.models import (
    ConnectionMessage,
    ConnectionState,
    MessageValidationError,
)


class ConnectionSubscriberTests(unittest.TestCase):
    """Tests for the MQTT connection subscriber."""

    def setUp(self) -> None:
        self.settings = Settings(
            mqtt_host="broker.test",
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
            mqtt_keepalive=60,
            mqtt_tls=False,
            vda_interface_name="uagv",
            vda_version="2.1.0",
            vda_manufacturer="TEST",
            vda_serial_number="AGV-001",
        )

        self.client = Mock()
        self.client.connect_async.return_value = None
        self.client.subscribe.return_value = (
            mqtt.MQTT_ERR_SUCCESS,
            1,
        )

        self.received_messages: list[
            ConnectionMessage
        ] = []
        self.errors: list[Exception] = []

        with patch(
            "vda5050_fms.connection_subscriber."
            "create_mqtt_client",
            return_value=self.client,
        ) as create_client:
            self.subscriber = ConnectionSubscriber(
                settings=self.settings,
                on_connection_message=(
                    self.received_messages.append
                ),
                on_error=self.errors.append,
            )

        create_client.assert_called_once_with(
            self.settings,
            reconnect_on_failure=True,
        )

    def valid_payload(self) -> bytes:
        payload = {
            "headerId": 1,
            "timestamp": "2026-08-19T12:00:00.000Z",
            "version": "2.1.0",
            "manufacturer": "TEST",
            "serialNumber": "AGV-001",
            "connectionState": "ONLINE",
        }
        return json.dumps(payload).encode("utf-8")

    def test_connection_topic_is_generated(self) -> None:
        self.assertEqual(
            self.subscriber.topic,
            "uagv/v2/TEST/AGV-001/connection",
        )

    def test_run_starts_mqtt_network_loop(self) -> None:
        self.subscriber.run()

        self.client.connect_async.assert_called_once_with(
            host="broker.test",
            port=1883,
            keepalive=60,
        )
        self.client.loop_forever.assert_called_once_with(
            retry_first_connection=True
        )

    def test_successful_connect_subscribes_with_qos_1(
        self,
    ) -> None:
        reason_code = SimpleNamespace(is_failure=False)

        self.client.on_connect(
            self.client,
            None,
            None,
            reason_code,
            None,
        )

        self.client.subscribe.assert_called_once_with(
            self.subscriber.topic,
            qos=1,
        )
        self.assertEqual(self.errors, [])

    def test_rejected_connection_reports_error(
        self,
    ) -> None:
        reason_code = SimpleNamespace(is_failure=True)

        self.client.on_connect(
            self.client,
            None,
            None,
            reason_code,
            None,
        )

        self.assertEqual(len(self.errors), 1)
        self.assertIsInstance(
            self.errors[0],
            ConnectionSubscriberError,
        )

    def test_valid_message_reaches_callback(self) -> None:
        mqtt_message = SimpleNamespace(
            topic=self.subscriber.topic,
            payload=self.valid_payload(),
        )

        self.client.on_message(
            self.client,
            None,
            mqtt_message,
        )

        self.assertEqual(len(self.received_messages), 1)
        self.assertEqual(
            self.received_messages[0].connection_state,
            ConnectionState.ONLINE,
        )
        self.assertEqual(self.errors, [])

    def test_invalid_payload_reports_error(self) -> None:
        mqtt_message = SimpleNamespace(
            topic=self.subscriber.topic,
            payload=b"{",
        )

        self.client.on_message(
            self.client,
            None,
            mqtt_message,
        )

        self.assertEqual(self.received_messages, [])
        self.assertEqual(len(self.errors), 1)
        self.assertIsInstance(
            self.errors[0],
            MessageValidationError,
        )

    def test_unexpected_topic_reports_error(self) -> None:
        mqtt_message = SimpleNamespace(
            topic="uagv/v2/OTHER/AGV-999/connection",
            payload=self.valid_payload(),
        )

        self.client.on_message(
            self.client,
            None,
            mqtt_message,
        )

        self.assertEqual(self.received_messages, [])
        self.assertEqual(len(self.errors), 1)
        self.assertIsInstance(
            self.errors[0],
            ConnectionSubscriberError,
        )

    def test_stop_disconnects_client(self) -> None:
        self.subscriber.stop()

        self.client.disconnect.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()