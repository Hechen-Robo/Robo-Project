from __future__ import annotations

from dataclasses import dataclass

from vda5050_fms.config import Settings
from vda5050_fms.models import ConnectionMessage


class UnexpectedConnectionMessageError(ValueError):
    """Raised when a valid message belongs to another robot."""


@dataclass(frozen=True, slots=True)
class ConnectionMessageHandler:
    """Parse and verify connection messages for one robot."""

    expected_version: str
    expected_manufacturer: str
    expected_serial_number: str

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
    ) -> ConnectionMessageHandler:
        return cls(
            expected_version=settings.vda_version,
            expected_manufacturer=(
                settings.vda_manufacturer
            ),
            expected_serial_number=(
                settings.vda_serial_number
            ),
        )

    def parse_payload(
        self,
        payload: str | bytes | bytearray,
    ) -> ConnectionMessage:
        message = ConnectionMessage.from_json(payload)
        header = message.header

        if header.version != self.expected_version:
            raise UnexpectedConnectionMessageError(
                "Unexpected VDA 5050 version: "
                f"expected {self.expected_version!r}, "
                f"received {header.version!r}"
            )

        if (
            header.manufacturer
            != self.expected_manufacturer
        ):
            raise UnexpectedConnectionMessageError(
                "Unexpected manufacturer: "
                f"expected {self.expected_manufacturer!r}, "
                f"received {header.manufacturer!r}"
            )

        if (
            header.serial_number
            != self.expected_serial_number
        ):
            raise UnexpectedConnectionMessageError(
                "Unexpected serialNumber: "
                f"expected {self.expected_serial_number!r}, "
                f"received {header.serial_number!r}"
            )

        return message