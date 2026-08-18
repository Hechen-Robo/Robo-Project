from __future__ import annotations

import argparse
import sys

from vda5050_fms import __version__
from vda5050_fms.config import Settings
from vda5050_fms.mqtt_client import (
    MqttConnectionError,
    check_mqtt_connection,
)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="vda5050-fms",
        description="VDA 5050 fleet management system",
    )

    parser.add_argument(
        "--check-mqtt",
        action="store_true",
        help=(
            "connect to the configured MQTT Broker once "
            "and disconnect without subscribing or publishing"
        ),
    )

    return parser


def print_settings(settings: Settings) -> None:
    """Display non-sensitive application settings."""

    tls_status = "enabled" if settings.mqtt_tls else "disabled"
    authentication_status = (
        "configured"
        if settings.mqtt_username
        else "not configured"
    )

    print("Configuration loaded successfully.")
    print(f"MQTT Broker: {settings.mqtt_host}:{settings.mqtt_port}")
    print(f"MQTT TLS: {tls_status}")
    print(f"MQTT authentication: {authentication_status}")
    print(f"VDA 5050 version: {settings.vda_version}")
    print(
        f"Robot identity: "
        f"{settings.vda_manufacturer}/"
        f"{settings.vda_serial_number}"
    )


def main(argv: list[str] | None = None) -> int:
    """Run the VDA5050 FMS command-line program."""

    parser = create_argument_parser()
    arguments = parser.parse_args(argv)

    print(f"VDA5050 FMS {__version__}")

    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print_settings(settings)

    if not arguments.check_mqtt:
        return 0

    print("Checking MQTT Broker connection...")

    try:
        check_mqtt_connection(settings)
    except (MqttConnectionError, TimeoutError, OSError) as exc:
        print(f"MQTT connection failed: {exc}", file=sys.stderr)
        return 3

    print("MQTT connection succeeded and was closed cleanly.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())