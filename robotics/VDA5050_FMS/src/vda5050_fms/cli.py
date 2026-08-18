from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from dotenv import load_dotenv

from vda5050_fms import __version__
from vda5050_fms.config import Settings
from vda5050_fms.messages import build_demo_order
from vda5050_fms.monitor import BrokerMonitor
from vda5050_fms.mqtt_client import JsonMqttClient
from vda5050_fms.simulator import RobotSimulator
from vda5050_fms.topics import TopicLayout
from vda5050_fms.validation import SCHEMA_FILES, SchemaRegistry


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vda5050-fms",
        description="VDA 5050 MQTT monitor, validator, and single-robot simulator",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    monitor = subcommands.add_parser(
        "monitor", description="Read and validate robot-to-FMS MQTT traffic"
    )
    monitor.add_argument(
        "--verbose", action="store_true", help="Log complete valid and invalid payloads"
    )

    subcommands.add_parser(
        "simulator", description="Run one VDA 5050 robot on the configured broker"
    )

    validate = subcommands.add_parser(
        "validate", description="Validate one JSON file against an official schema"
    )
    validate.add_argument("topic", choices=sorted(SCHEMA_FILES))
    validate.add_argument("json_file", type=Path)

    demo = subcommands.add_parser(
        "demo-order",
        description="Publish a two-node test order; explicit opt-in is required",
    )
    demo.add_argument("--target-manufacturer", required=True)
    demo.add_argument("--target-serial", required=True)
    demo.add_argument("--map-id", default=None)
    demo.add_argument("--start-node", default="N0")
    demo.add_argument("--target-node", default="N1")
    demo.add_argument("--start-x", type=float, default=0.0)
    demo.add_argument("--start-y", type=float, default=0.0)
    demo.add_argument("--target-x", type=float, default=1.0)
    demo.add_argument("--target-y", type=float, default=0.0)
    demo.add_argument(
        "--allow-command",
        action="store_true",
        help="Confirm that publishing an order to this exact target is intentional",
    )
    return parser


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def _validate_file(settings: Settings, topic: str, json_file: Path) -> int:
    payload = json.loads(json_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("The JSON document must contain an object at its root")
    SchemaRegistry(settings.vda_version).validate(topic, payload)
    print(f"VALID: {json_file} conforms to the VDA {settings.vda_version} {topic} schema")
    return 0


def _publish_demo_order(settings: Settings, arguments: argparse.Namespace) -> int:
    if not arguments.allow_command:
        raise ValueError(
            "Refusing to publish: add --allow-command after verifying the exact target"
        )

    map_id = arguments.map_id or settings.simulation_map_id
    order = build_demo_order(
        version=settings.vda_version,
        manufacturer=arguments.target_manufacturer,
        serial_number=arguments.target_serial,
        map_id=map_id,
        start_node_id=arguments.start_node,
        target_node_id=arguments.target_node,
        start_x=arguments.start_x,
        start_y=arguments.start_y,
        target_x=arguments.target_x,
        target_y=arguments.target_y,
    )
    SchemaRegistry(settings.vda_version).validate("order", order)
    layout = TopicLayout(
        settings.interface_name,
        settings.vda_version,
        arguments.target_manufacturer,
        arguments.target_serial,
    )
    topic = layout.robot_topic("order")
    client = JsonMqttClient(settings)
    client.connect()
    try:
        client.publish_json(topic, order, qos=0, retain=False, wait=True)
    finally:
        client.disconnect()
    print(f"Published order {order['orderId']} to {topic}")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        settings = Settings.from_env(arguments.command)
        _configure_logging(settings.log_level)

        if arguments.command == "monitor":
            BrokerMonitor(settings, verbose=arguments.verbose).run()
            return 0
        if arguments.command == "simulator":
            RobotSimulator(settings).run()
            return 0
        if arguments.command == "validate":
            return _validate_file(settings, arguments.topic, arguments.json_file)
        if arguments.command == "demo-order":
            return _publish_demo_order(settings, arguments)
    except (OSError, RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("%s", exc)
        return 2

    parser.error(f"Unsupported command: {arguments.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

