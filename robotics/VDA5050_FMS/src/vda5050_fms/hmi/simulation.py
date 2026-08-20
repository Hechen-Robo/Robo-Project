from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, hypot
from time import monotonic


MANUFACTURER = "TEST"
SERIAL_NUMBER = "AGV-001"
VDA5050_VERSION = "2.1.0"
MAP_ID = "WAREHOUSE_A"

SEGMENT_DURATION_SECONDS = 4.0


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


SIMULATION_START = monotonic()
SIMULATION_STARTED_AT = utc_timestamp()


@dataclass(frozen=True)
class RouteNode:
    node_id: str
    sequence_id: int
    x: float
    y: float


ROUTE = (
    RouteNode("N-01", 0, 1.5, 1.5),
    RouteNode("N-02", 2, 5.0, 1.5),
    RouteNode("N-03", 4, 5.0, 4.0),
    RouteNode("N-04", 6, 9.0, 4.0),
    RouteNode("N-05", 8, 9.0, 7.0),
    RouteNode("N-06", 10, 1.5, 7.0),
    RouteNode("N-07", 12, 1.5, 1.5),
)


def _header(
    header_id: int,
    timestamp: str,
) -> dict[str, object]:
    return {
        "headerId": header_id,
        "timestamp": timestamp,
        "version": VDA5050_VERSION,
        "manufacturer": MANUFACTURER,
        "serialNumber": SERIAL_NUMBER,
    }


def get_simulated_robot_snapshot() -> dict[str, object]:
    elapsed_seconds = monotonic() - SIMULATION_START

    segment_count = len(ROUTE) - 1
    cycle_duration = (
        segment_count * SEGMENT_DURATION_SECONDS
    )

    cycle_number = int(
        elapsed_seconds // cycle_duration
    )
    elapsed_in_cycle = elapsed_seconds % cycle_duration

    segment_index = min(
        int(
            elapsed_in_cycle
            // SEGMENT_DURATION_SECONDS
        ),
        segment_count - 1,
    )

    segment_progress = (
        elapsed_in_cycle % SEGMENT_DURATION_SECONDS
    ) / SEGMENT_DURATION_SECONDS

    current_node = ROUTE[segment_index]
    next_node = ROUTE[segment_index + 1]

    delta_x = next_node.x - current_node.x
    delta_y = next_node.y - current_node.y

    x = current_node.x + delta_x * segment_progress
    y = current_node.y + delta_y * segment_progress
    theta = atan2(delta_y, delta_x)

    segment_length = hypot(delta_x, delta_y)
    forward_velocity = (
        segment_length / SEGMENT_DURATION_SECONDS
    )

    timestamp = utc_timestamp()

    state_header_id = int(elapsed_seconds) + 1
    visualization_header_id = (
        int(elapsed_seconds * 2) + 1
    )

    remaining_nodes = [
        {
            "nodeId": node.node_id,
            "sequenceId": node.sequence_id,
            "released": True,
            "nodePosition": {
                "x": node.x,
                "y": node.y,
                "mapId": MAP_ID,
            },
        }
        for node in ROUTE[segment_index + 1:]
    ]

    remaining_edges = [
        {
            "edgeId": f"E-{edge_index + 1:02d}",
            "sequenceId": edge_index * 2 + 1,
            "released": True,
        }
        for edge_index in range(
            segment_index,
            segment_count,
        )
    ]

    agv_position = {
        "x": round(x, 3),
        "y": round(y, 3),
        "theta": round(theta, 3),
        "mapId": MAP_ID,
        "positionInitialized": True,
        "localizationScore": 0.987,
    }

    velocity = {
        "vx": round(forward_velocity, 3),
        "vy": 0.0,
        "omega": 0.0,
    }

    return {
        "dataSource": "simulation",
        "manufacturer": MANUFACTURER,
        "serialNumber": SERIAL_NUMBER,
        "connection": {
            **_header(
                header_id=1,
                timestamp=SIMULATION_STARTED_AT,
            ),
            "connectionState": "ONLINE",
        },
        "state": {
            **_header(
                header_id=state_header_id,
                timestamp=timestamp,
            ),
            "orderId": (
                f"DEMO-ORDER-{cycle_number + 1:03d}"
            ),
            "orderUpdateId": 0,
            "lastNodeId": current_node.node_id,
            "lastNodeSequenceId": (
                current_node.sequence_id
            ),
            "nodeStates": remaining_nodes,
            "edgeStates": remaining_edges,
            "driving": True,
            "paused": False,
            "newBaseRequest": False,
            "actionStates": [],
            "batteryState": {
                "batteryCharge": round(
                    max(
                        20.0,
                        87.0 - elapsed_seconds / 600.0,
                    ),
                    1,
                ),
                "charging": False,
            },
            "operatingMode": "AUTOMATIC",
            "errors": [],
            "information": [],
            "safetyState": {
                "eStop": "NONE",
                "fieldViolation": False,
            },
        },
        "visualization": {
            **_header(
                header_id=visualization_header_id,
                timestamp=timestamp,
            ),
            "agvPosition": agv_position,
            "velocity": velocity,
        },
    }