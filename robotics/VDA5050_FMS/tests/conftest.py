from __future__ import annotations

from pathlib import Path

import pytest

from vda5050_fms.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        mqtt_keepalive=30,
        mqtt_transport="tcp",
        mqtt_tls=False,
        mqtt_ca_cert=None,
        mqtt_client_cert=None,
        mqtt_client_key=None,
        mqtt_tls_insecure=False,
        mqtt_client_id="test-client",
        interface_name="uagv",
        vda_version="2.1.0",
        manufacturer="SIMULATOR",
        serial_number="SIM-001",
        state_interval_seconds=1.0,
        visualization_interval_seconds=0.5,
        simulation_step_seconds=0.1,
        simulation_map_id="map-001",
        simulation_start_node_id="N0",
        simulation_start_x=0.0,
        simulation_start_y=0.0,
        simulation_start_theta=0.0,
        log_level="INFO",
    )

