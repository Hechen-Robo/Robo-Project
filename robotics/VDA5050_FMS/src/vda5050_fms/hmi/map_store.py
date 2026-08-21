from __future__ import annotations

from threading import RLock

from vda5050_fms.lif import (
    LifDocument,
    LifLayout,
    LifPosition,
)


class LifMapStore:
    """Thread-safe in-memory storage for one LIF document."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._document: LifDocument | None = None

    def replace(self, document: LifDocument) -> None:
        with self._lock:
            self._document = document

    def clear(self) -> None:
        with self._lock:
            self._document = None

    def list_layouts(self) -> tuple[LifLayout, ...]:
        with self._lock:
            if self._document is None:
                return ()

            return self._document.layouts

    def get_layout(
        self,
        layout_id: str,
    ) -> LifLayout | None:
        with self._lock:
            if self._document is None:
                return None

            try:
                return self._document.layout_by_id(
                    layout_id
                )
            except KeyError:
                return None


def _position_to_mapping(
    position: LifPosition | None,
) -> dict[str, float] | None:
    if position is None:
        return None

    result = {
        "x": position.x,
        "y": position.y,
    }

    if position.theta is not None:
        result["theta"] = position.theta

    return result


def lif_layout_summary(
    layout: LifLayout,
) -> dict[str, object]:
    return {
        "layoutId": layout.layout_id,
        "layoutName": layout.layout_name,
        "layoutVersion": layout.layout_version,
        "layoutLevelId": layout.layout_level_id,
        "mapIds": sorted(layout.map_ids),
        "nodeCount": len(layout.nodes),
        "edgeCount": len(layout.edges),
        "stationCount": len(layout.stations),
    }


def lif_layout_to_mapping(
    layout: LifLayout,
) -> dict[str, object]:
    bounds = layout.bounds

    return {
        **lif_layout_summary(layout),
        "layoutDescription": (
            layout.layout_description
        ),
        "bounds": {
            "minX": bounds.min_x,
            "minY": bounds.min_y,
            "maxX": bounds.max_x,
            "maxY": bounds.max_y,
            "width": bounds.width,
            "height": bounds.height,
        },
        "nodes": [
            {
                "nodeId": node.node_id,
                "nodeName": node.node_name,
                "mapId": node.map_id,
                "position": _position_to_mapping(
                    node.position
                ),
                "vehicleTypeIds": list(
                    node.vehicle_type_ids
                ),
            }
            for node in layout.nodes
        ],
        "edges": [
            {
                "edgeId": edge.edge_id,
                "edgeName": edge.edge_name,
                "startNodeId": edge.start_node_id,
                "endNodeId": edge.end_node_id,
                "vehicleTypeIds": list(
                    edge.vehicle_type_ids
                ),
            }
            for edge in layout.edges
        ],
        "stations": [
            {
                "stationId": station.station_id,
                "stationName": station.station_name,
                "interactionNodeIds": list(
                    station.interaction_node_ids
                ),
                "position": _position_to_mapping(
                    station.position
                ),
            }
            for station in layout.stations
        ],
    }


lif_map_store = LifMapStore()