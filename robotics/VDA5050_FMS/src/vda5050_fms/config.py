from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


def _env_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True, slots=True)
class Settings:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_keepalive: int
    mqtt_transport: str
    mqtt_tls: bool
    mqtt_ca_cert: Path | None
    mqtt_client_cert: Path | None
    mqtt_client_key: Path | None
    mqtt_tls_insecure: bool
    mqtt_client_id: str
    interface_name: str
    vda_version: str
    manufacturer: str
    serial_number: str
    state_interval_seconds: float
    visualization_interval_seconds: float
    simulation_step_seconds: float
    simulation_map_id: str
    simulation_start_node_id: str
    simulation_start_x: float
    simulation_start_y: float
    simulation_start_theta: float
    log_level: str

    @classmethod
    def from_env(cls, role: str) -> "Settings":
        username = os.getenv("MQTT_USERNAME", "").strip() or None
        password = os.getenv("MQTT_PASSWORD") if username else None
        exact_client_id = os.getenv("MQTT_CLIENT_ID", "").strip()
        prefix = os.getenv("MQTT_CLIENT_ID_PREFIX", "vda5050-fms").strip()
        generated_client_id = f"{prefix}-{role}-{uuid4().hex[:8]}"

        settings = cls(
            mqtt_host=os.getenv("MQTT_HOST", "127.0.0.1").strip(),
            mqtt_port=_env_int("MQTT_PORT", 1883),
            mqtt_username=username,
            mqtt_password=password,
            mqtt_keepalive=_env_int("MQTT_KEEPALIVE", 30),
            mqtt_transport=os.getenv("MQTT_TRANSPORT", "tcp").strip().lower(),
            mqtt_tls=_env_bool("MQTT_TLS", False),
            mqtt_ca_cert=_env_path("MQTT_CA_CERT"),
            mqtt_client_cert=_env_path("MQTT_CLIENT_CERT"),
            mqtt_client_key=_env_path("MQTT_CLIENT_KEY"),
            mqtt_tls_insecure=_env_bool("MQTT_TLS_INSECURE", False),
            mqtt_client_id=exact_client_id or generated_client_id,
            interface_name=os.getenv("VDA_INTERFACE_NAME", "uagv").strip(),
            vda_version=os.getenv("VDA_VERSION", "2.1.0").strip(),
            manufacturer=os.getenv("VDA_MANUFACTURER", "SIMULATOR").strip(),
            serial_number=os.getenv("VDA_SERIAL_NUMBER", "SIM-001").strip(),
            state_interval_seconds=_env_float("STATE_INTERVAL_SECONDS", 1.0),
            visualization_interval_seconds=_env_float(
                "VISUALIZATION_INTERVAL_SECONDS", 0.5
            ),
            simulation_step_seconds=_env_float("SIMULATION_STEP_SECONDS", 2.0),
            simulation_map_id=os.getenv("SIMULATION_MAP_ID", "map-001").strip(),
            simulation_start_node_id=os.getenv(
                "SIMULATION_START_NODE_ID", "N0"
            ).strip(),
            simulation_start_x=_env_float("SIMULATION_START_X", 0.0),
            simulation_start_y=_env_float("SIMULATION_START_Y", 0.0),
            simulation_start_theta=_env_float("SIMULATION_START_THETA", 0.0),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.mqtt_host:
            raise ValueError("MQTT_HOST must not be empty")
        if not (1 <= self.mqtt_port <= 65535):
            raise ValueError("MQTT_PORT must be between 1 and 65535")
        if self.mqtt_transport not in {"tcp", "websockets"}:
            raise ValueError("MQTT_TRANSPORT must be 'tcp' or 'websockets'")
        if bool(self.mqtt_client_cert) != bool(self.mqtt_client_key):
            raise ValueError(
                "MQTT_CLIENT_CERT and MQTT_CLIENT_KEY must be configured together"
            )
        for path in (self.mqtt_ca_cert, self.mqtt_client_cert, self.mqtt_client_key):
            if path is not None and not path.is_file():
                raise ValueError(f"Configured certificate file does not exist: {path}")
        if self.state_interval_seconds <= 0:
            raise ValueError("STATE_INTERVAL_SECONDS must be greater than zero")
        if self.visualization_interval_seconds <= 0:
            raise ValueError(
                "VISUALIZATION_INTERVAL_SECONDS must be greater than zero"
            )
        if self.simulation_step_seconds <= 0:
            raise ValueError("SIMULATION_STEP_SECONDS must be greater than zero")

