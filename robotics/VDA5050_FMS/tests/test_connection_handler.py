import json
import unittest

from vda5050_fms.connection_handler import (
    ConnectionMessageHandler,
    UnexpectedConnectionMessageError,
)
from vda5050_fms.models import (
    ConnectionState,
    MessageValidationError,
)


class ConnectionMessageHandlerTests(unittest.TestCase):
    """Tests for connection message identity checks."""

    def setUp(self) -> None:
        self.handler = ConnectionMessageHandler(
            expected_version="2.1.0",
            expected_manufacturer="TEST",
            expected_serial_number="AGV-001",
        )

        self.payload: dict[str, object] = {
            "headerId": 1,
            "timestamp": "2026-08-19T12:00:00.000Z",
            "version": "2.1.0",
            "manufacturer": "TEST",
            "serialNumber": "AGV-001",
            "connectionState": "ONLINE",
        }

    def encode_payload(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def test_expected_message_is_accepted(self) -> None:
        message = self.handler.parse_payload(
            self.encode_payload()
        )

        self.assertEqual(
            message.connection_state,
            ConnectionState.ONLINE,
        )

    def test_unexpected_version_is_rejected(
        self,
    ) -> None:
        self.payload["version"] = "2.0.0"

        with self.assertRaisesRegex(
            UnexpectedConnectionMessageError,
            "Unexpected VDA 5050 version",
        ):
            self.handler.parse_payload(
                self.encode_payload()
            )

    def test_unexpected_manufacturer_is_rejected(
        self,
    ) -> None:
        self.payload["manufacturer"] = "OTHER"

        with self.assertRaisesRegex(
            UnexpectedConnectionMessageError,
            "Unexpected manufacturer",
        ):
            self.handler.parse_payload(
                self.encode_payload()
            )

    def test_unexpected_serial_number_is_rejected(
        self,
    ) -> None:
        self.payload["serialNumber"] = "AGV-999"

        with self.assertRaisesRegex(
            UnexpectedConnectionMessageError,
            "Unexpected serialNumber",
        ):
            self.handler.parse_payload(
                self.encode_payload()
            )

    def test_invalid_json_error_is_preserved(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            MessageValidationError,
            "not valid JSON",
        ):
            self.handler.parse_payload(b"{")


if __name__ == "__main__":
    unittest.main()