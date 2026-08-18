from __future__ import annotations

import sys

from vda5050_fms import __version__
from vda5050_fms.config import Settings


def main() -> int:
    """Load and display the non-sensitive application configuration."""

    print(f"VDA5050 FMS {__version__}")

    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    tls_status = "enabled" if settings.mqtt_tls else "disabled"
    authentication_status = (
        "configured"
        if settings.mqtt_username
        else "not configured"
    )

    print("Configuration loaded successfully.")
    print(
        f"MQTT broker: "
        f"{settings.mqtt_host}:{settings.mqtt_port}"
    )
    print(f"MQTT TLS: {tls_status}")
    print(f"MQTT authentication: {authentication_status}")
    print(f"VDA 5050 version: {settings.vda_version}")
    print(
        f"Robot identity: "
        f"{settings.vda_manufacturer}/"
        f"{settings.vda_serial_number}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())