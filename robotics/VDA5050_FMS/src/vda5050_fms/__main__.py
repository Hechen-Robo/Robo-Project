from __future__ import annotations

import argparse
import sys

from vda5050_fms import __version__
from vda5050_fms.config import Settings
from vda5050_fms.connection_subscriber import (
    ConnectionSubscriber,
    ConnectionSubscriberError,
)
from vda5050_fms.models import ConnectionMessage
from vda5050_fms.mqtt_client import (
    MqttConnectionError,
    check_mqtt_connection,
)
from vda5050_fms.topics import TopicLayout


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vda5050-fms",
        description="VDA 5050 fleet management system",
    )

    parser.add_argument(
        "--show-topics",
        action="store_true",
        help=(
            "display the six configured VDA 5050 topics "
            "without connecting to MQTT"
        ),
    )

    network_commands = (
        parser.add_mutually_exclusive_group()
    )

    network_commands.add_argument(
        "--check-mqtt",
        action="store_true",
        help=(
            "connect to the configured MQTT Broker once "
            "and disconnect without subscribing or publishing"
        ),
    )

    network_commands.add_argument(
        "--listen-connection",
        action="store_true",
        help=(
            "subscribe to the configured robot connection "
            "topic and wait for connection messages"
        ),
    )

    return parser


def print_settings(settings: Settings) -> None:
    tls_status = (
        "enabled" if settings.mqtt_tls else "disabled"
    )
    authentication_status = (
        "configured"
        if settings.mqtt_username
        else "not configured"
    )

    print("Configuration loaded successfully.")
    print(
        f"MQTT Broker: "
        f"{settings.mqtt_host}:{settings.mqtt_port}"
    )
    print(f"MQTT TLS: {tls_status}")
    print(
        "MQTT authentication: "
        f"{authentication_status}"
    )
    print(f"VDA 5050 version: {settings.vda_version}")
    print(
        "Robot identity: "
        f"{settings.vda_manufacturer}/"
        f"{settings.vda_serial_number}"
    )


def print_topics(topic_layout: TopicLayout) -> None:
    print("Configured VDA 5050 topics:")

    for topic_name, topic in (
        topic_layout.all_topics().items()
    ):
        print(f"  {topic_name:<14} {topic}")


def print_connection_message(
    message: ConnectionMessage,
) -> None:
    header = message.header

    print(
        "Connection update: "
        f"{header.manufacturer}/"
        f"{header.serial_number} -> "
        f"{message.connection_state.value} "
        f"(headerId={header.header_id}, "
        f"timestamp={header.timestamp})"
    )


def print_connection_error(error: Exception) -> None:
    print(
        f"Connection listener error: {error}",
        file=sys.stderr,
    )


def run_mqtt_check(settings: Settings) -> int:
    print("Checking MQTT Broker connection...")

    try:
        check_mqtt_connection(settings)
    except (
        MqttConnectionError,
        TimeoutError,
        OSError,
    ) as exc:
        print(
            f"MQTT connection failed: {exc}",
            file=sys.stderr,
        )
        return 3

    print(
        "MQTT connection succeeded "
        "and was closed cleanly."
    )
    return 0


def run_connection_listener(
    settings: Settings,
) -> int:
    subscriber = ConnectionSubscriber(
        settings=settings,
        on_connection_message=(
            print_connection_message
        ),
        on_error=print_connection_error,
    )

    print(
        "Listening for VDA 5050 connection "
        f"messages on:\n{subscriber.topic}"
    )
    print("Press Ctrl+C to stop.")

    try:
        subscriber.run()
    except KeyboardInterrupt:
        print("\nStopping connection listener...")
    except (
        ConnectionSubscriberError,
        OSError,
    ) as exc:
        print(
            f"Connection listener failed: {exc}",
            file=sys.stderr,
        )
        return 4
    finally:
        subscriber.stop()

    print("Connection listener stopped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = create_argument_parser()
    arguments = parser.parse_args(argv)

    print(f"VDA5050 FMS {__version__}")

    try:
        settings = Settings.from_env()
        topic_layout = TopicLayout.from_settings(
            settings
        )
    except ValueError as exc:
        print(
            f"Configuration error: {exc}",
            file=sys.stderr,
        )
        return 2

    print_settings(settings)

    if arguments.show_topics:
        print_topics(topic_layout)

    if arguments.check_mqtt:
        return run_mqtt_check(settings)

    if arguments.listen_connection:
        return run_connection_listener(settings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())