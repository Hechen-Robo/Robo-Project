from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import json

from vda5050_fms.models.common import (
    MessageValidationError,
    Vda5050Header,
)


class ConnectionState(StrEnum):
    """Connection states defined by VDA 5050."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    CONNECTIONBROKEN = "CONNECTIONBROKEN"


@dataclass(frozen=True, slots=True)
class ConnectionMessage:
    """Validated VDA 5050 connection message."""

    header: Vda5050Header
    connection_state: ConnectionState

    def __post_init__(self) -> None:
        if not isinstance(self.header, Vda5050Header):
            raise MessageValidationError(
                "header must be a Vda5050Header"
            )

        if not isinstance(
            self.connection_state,
            ConnectionState,
        ):
            raise MessageValidationError(
                "connectionState must be a ConnectionState"
            )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, object],
    ) -> ConnectionMessage:
        header = Vda5050Header.from_mapping(payload)

        if "connectionState" not in payload:
            raise MessageValidationError(
                "Missing required field: connectionState"
            )

        raw_connection_state = payload["connectionState"]

        if not isinstance(raw_connection_state, str):
            raise MessageValidationError(
                "connectionState must be a string"
            )

        try:
            connection_state = ConnectionState(
                raw_connection_state
            )
        except ValueError as exc:
            allowed_states = ", ".join(
                state.value for state in ConnectionState
            )
            raise MessageValidationError(
                "connectionState must be one of: "
                f"{allowed_states}"
            ) from exc

        return cls(
            header=header,
            connection_state=connection_state,
        )

    @classmethod
    def from_json(
        cls,
        payload: str | bytes | bytearray,
    ) -> ConnectionMessage:
        try:
            decoded_payload = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MessageValidationError(
                "Connection payload is not valid JSON"
            ) from exc

        if not isinstance(decoded_payload, dict):
            raise MessageValidationError(
                "Connection payload must be a JSON object"
            )

        return cls.from_mapping(decoded_payload)

    def to_mapping(self) -> dict[str, object]:
        payload = self.header.to_mapping()
        payload["connectionState"] = (
            self.connection_state.value
        )
        return payload

    def to_json(self) -> str:
        return json.dumps(
            self.to_mapping(),
            ensure_ascii=False,
            separators=(",", ":"),
        )