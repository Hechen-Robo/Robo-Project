from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class HeaderFactory:
    """Maintains the VDA requirement that headerId increments per topic."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)

    def next(
        self,
        topic_name: str,
        version: str,
        manufacturer: str,
        serial_number: str,
    ) -> dict[str, Any]:
        header_id = self._counters[topic_name]
        self._counters[topic_name] = (header_id + 1) % (2**32)
        return {
            "headerId": header_id,
            "timestamp": utc_timestamp(),
            "version": version,
            "manufacturer": manufacturer,
            "serialNumber": serial_number,
        }


def build_demo_order(
    *,
    version: str,
    manufacturer: str,
    serial_number: str,
    map_id: str,
    start_node_id: str = "N0",
    target_node_id: str = "N1",
    start_x: float = 0.0,
    start_y: float = 0.0,
    target_x: float = 1.0,
    target_y: float = 0.0,
    order_id: str | None = None,
    header_id: int = 0,
) -> dict[str, Any]:
    return {
        "headerId": header_id,
        "timestamp": utc_timestamp(),
        "version": version,
        "manufacturer": manufacturer,
        "serialNumber": serial_number,
        "orderId": order_id or f"demo-{uuid4().hex[:12]}",
        "orderUpdateId": 0,
        "nodes": [
            {
                "nodeId": start_node_id,
                "sequenceId": 0,
                "released": True,
                "nodePosition": {
                    "x": start_x,
                    "y": start_y,
                    "theta": 0.0,
                    "mapId": map_id,
                },
                "actions": [],
            },
            {
                "nodeId": target_node_id,
                "sequenceId": 2,
                "released": True,
                "nodePosition": {
                    "x": target_x,
                    "y": target_y,
                    "theta": 0.0,
                    "mapId": map_id,
                },
                "actions": [],
            },
        ],
        "edges": [
            {
                "edgeId": f"{start_node_id}-{target_node_id}",
                "sequenceId": 1,
                "released": True,
                "startNodeId": start_node_id,
                "endNodeId": target_node_id,
                "actions": [],
            }
        ],
    }

