from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import re
from typing import cast

_UINT32_MAX = 4_294_967_295

_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)$"
)

_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?Z$"
)

_HEADER_FIELDS = (
    "headerId",
    "timestamp",
    "version",
    "manufacturer",
    "serialNumber",
)


class MessageValidationError(ValueError):
    """Raised when a VDA 5050 message is invalid."""


def _validate_utc_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise MessageValidationError(
            "timestamp must be a string"
        )

    if not _TIMESTAMP_PATTERN.fullmatch(value):
        raise MessageValidationError(
            "timestamp must use ISO 8601 UTC format ending in Z"
        )

    try:
        datetime.fromisoformat(
            value.removesuffix("Z") + "+00:00"
        )
    except ValueError as exc:
        raise MessageValidationError(
            "timestamp contains an invalid date or time"
        ) from exc


def _validate_non_empty_string(
    field_name: str,
    value: object,
) -> None:
    if not isinstance(value, str):
        raise MessageValidationError(
            f"{field_name} must be a string"
        )

    if not value:
        raise MessageValidationError(
            f"{field_name} must not be empty"
        )


@dataclass(frozen=True, slots=True)
class Vda5050Header:
    """Common header fields included in every VDA 5050 message."""

    header_id: int
    timestamp: str
    version: str
    manufacturer: str
    serial_number: str

    def __post_init__(self) -> None:
        if type(self.header_id) is not int:
            raise MessageValidationError(
                "headerId must be an integer"
            )

        if not 0 <= self.header_id <= _UINT32_MAX:
            raise MessageValidationError(
                "headerId must be a uint32 value"
            )

        _validate_utc_timestamp(self.timestamp)
        _validate_non_empty_string("version", self.version)
        _validate_non_empty_string(
            "manufacturer",
            self.manufacturer,
        )
        _validate_non_empty_string(
            "serialNumber",
            self.serial_number,
        )

        if not _VERSION_PATTERN.fullmatch(self.version):
            raise MessageValidationError(
                "version must use Major.Minor.Patch format"
            )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, object],
    ) -> Vda5050Header:
        missing_fields = [
            field_name
            for field_name in _HEADER_FIELDS
            if field_name not in payload
        ]

        if missing_fields:
            raise MessageValidationError(
                "Missing required header field(s): "
                + ", ".join(missing_fields)
            )

        return cls(
            header_id=cast(int, payload["headerId"]),
            timestamp=cast(str, payload["timestamp"]),
            version=cast(str, payload["version"]),
            manufacturer=cast(str, payload["manufacturer"]),
            serial_number=cast(str, payload["serialNumber"]),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "headerId": self.header_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "manufacturer": self.manufacturer,
            "serialNumber": self.serial_number,
        }