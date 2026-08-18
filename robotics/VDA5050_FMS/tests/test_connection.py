import json
import unittest

from vda5050_fms.models import (
    ConnectionMessage,
    ConnectionState,
    MessageValidationError,
)


class ConnectionMessageTests(unittest.TestCase):
    """Tests for VDA 5050 connection messages."""

    def setUp(self) -> None:
        self.payload: dict[str, object] = {
            "headerId": 1,
            "timestamp": "2026-08-18T12:34:56.123Z",
            "version": "2.1.0",
            "manufacturer": "TEST",
            "serialNumber": "AGV-001",
            "connectionState": "ONLINE",
        }

    def test_valid_connection_message(self) -> None:
        message = ConnectionMessage.from_mapping(
            self.payload
        )

        self.assertEqual(message.header.header_id, 1)
        self.assertEqual(
            message.header.manufacturer,
            "TEST",
        )
        self.assertEqual(
            message.header.serial_number,
            "AGV-001",
        )
        self.assertEqual(
            message.connection_state,
            ConnectionState.ONLINE,
        )

    def test_message_can_be_loaded_from_json(self) -> None:
        payload_json = json.dumps(self.payload)

        message = ConnectionMessage.from_json(
            payload_json
        )

        self.assertEqual(
            message.connection_state,
            ConnectionState.ONLINE,
        )

    def test_message_can_be_serialized_to_json(self) -> None:
        message = ConnectionMessage.from_mapping(
            self.payload
        )

        serialized_payload = json.loads(
            message.to_json()
        )

        self.assertEqual(
            serialized_payload,
            self.payload,
        )

    def test_missing_connection_state_is_rejected(
        self,
    ) -> None:
        del self.payload["connectionState"]

        with self.assertRaisesRegex(
            MessageValidationError,
            "connectionState",
        ):
            ConnectionMessage.from_mapping(self.payload)

    def test_unknown_connection_state_is_rejected(
        self,
    ) -> None:
        self.payload["connectionState"] = "UNKNOWN"

        with self.assertRaisesRegex(
            MessageValidationError,
            "ONLINE, OFFLINE, CONNECTIONBROKEN",
        ):
            ConnectionMessage.from_mapping(self.payload)

    def test_invalid_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            MessageValidationError,
            "not valid JSON",
        ):
            ConnectionMessage.from_json("{")

    def test_non_object_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            MessageValidationError,
            "must be a JSON object",
        ):
            ConnectionMessage.from_json("[]")

    def test_missing_header_field_is_rejected(
        self,
    ) -> None:
        del self.payload["serialNumber"]

        with self.assertRaisesRegex(
            MessageValidationError,
            "serialNumber",
        ):
            ConnectionMessage.from_mapping(self.payload)

    def test_invalid_header_id_is_rejected(
        self,
    ) -> None:
        self.payload["headerId"] = 4_294_967_296

        with self.assertRaisesRegex(
            MessageValidationError,
            "uint32",
        ):
            ConnectionMessage.from_mapping(self.payload)

    def test_timestamp_without_utc_z_is_rejected(
        self,
    ) -> None:
        self.payload["timestamp"] = (
            "2026-08-18T12:34:56+00:00"
        )

        with self.assertRaisesRegex(
            MessageValidationError,
            "ending in Z",
        ):
            ConnectionMessage.from_mapping(self.payload)


if __name__ == "__main__":
    unittest.main()