from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _required(name: str) -> str:
    """Read one required environment variable."""

    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(f"{name} is required")

    return value


def _optional(name: str) -> str | None:
    """Read one optional environment variable."""

    value = os.getenv(name)

    if value is None:
        return None

    value = value.strip()

    return value or None


def _integer(name: str) -> int:
    """Read and convert an integer environment variable."""

    value = _required(name)

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer, got {value!r}"
        ) from exc


def _boolean(name: str) -> bool:
    """Read and convert a Boolean environment variable."""

    value = _required(name).lower()

    if value in _TRUE_VALUES:
        return True

    if value in _FALSE_VALUES:
        return False

    raise ValueError(
        f"{name} must be true or false, got {value!r}"
    )


@dataclass(frozen=True, slots=True)
class Settings:
    """Application configuration loaded from environment variables."""

    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None = field(repr=False)
    mqtt_password: str | None = field(repr=False)
    mqtt_keepalive: int
    mqtt_tls: bool

    vda_interface_name: str
    vda_version: str
    vda_manufacturer: str
    vda_serial_number: str

    @classmethod
    def from_env(
        cls,
        env_file: str | Path = ".env",
    ) -> Settings:
        """Load settings from a dotenv file and the process environment."""

        load_dotenv(
            dotenv_path=Path(env_file),
            override=False,
        )

        settings = cls(
            mqtt_host=_required("MQTT_HOST"),
            mqtt_port=_integer("MQTT_PORT"),
            mqtt_username=_optional("MQTT_USERNAME"),
            mqtt_password=_optional("MQTT_PASSWORD"),
            mqtt_keepalive=_integer("MQTT_KEEPALIVE"),
            mqtt_tls=_boolean("MQTT_TLS"),
            vda_interface_name=_required("VDA_INTERFACE_NAME"),
            vda_version=_required("VDA_VERSION"),
            vda_manufacturer=_required("VDA_MANUFACTURER"),
            vda_serial_number=_required("VDA_SERIAL_NUMBER"),
        )

        settings.validate()

        return settings

    def validate(self) -> None:
        """Validate configuration values before they are used."""

        if not 1 <= self.mqtt_port <= 65535:
            raise ValueError(
                "MQTT_PORT must be between 1 and 65535"
            )

        if not 0 <= self.mqtt_keepalive <= 65535:
            raise ValueError(
                "MQTT_KEEPALIVE must be between 0 and 65535"
            )

        if self.vda_version != "2.1.0":
            raise ValueError(
                "The current implementation supports "
                "VDA 5050 version 2.1.0 only"
            )