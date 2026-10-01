"""Validate generated LIF 1.0.0 documents before they are written."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import resources
import json
import math
import re
from typing import Any

from jsonschema import Draft7Validator, FormatChecker


JsonObject = dict[str, Any]
LIF_VERSION = "1.0.0"
UTC_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


@dataclass(frozen=True, slots=True)
class LifValidationIssue:
    """One schema or semantic validation failure."""

    path: str
    message: str

    def format(self) -> str:
        """Return a readable JSON-path validation message."""

        return f"{self.path}: {self.message}"


class LifValidationError(ValueError):
    """Raised when a generated LIF document is not safe to export."""

    def __init__(self, issues: tuple[LifValidationIssue, ...]) -> None:
        self.issues = issues
        details = "\n".join(f"- {issue.format()}" for issue in issues)
        super().__init__(f"LIF validation failed:\n{details}")


def load_lif_schema() -> JsonObject:
    """Load the bundled official LIF 1.0.0 JSON Schema."""

    schema_resource = resources.files("smap2lif.schemas").joinpath(
        "LIF.schema"
    )
    payload = schema_resource.read_text(encoding="utf-8")
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise RuntimeError("Bundled LIF schema must be a JSON object.")
    return decoded


def validate_lif_document(document: object) -> None:
    """Validate a decoded LIF document against schema and graph rules."""

    schema = load_lif_schema()
    validator = Draft7Validator(
        schema,
        format_checker=FormatChecker(),
    )
    schema_issues = tuple(
        LifValidationIssue(
            path=_json_path(error.absolute_path),
            message=error.message,
        )
        for error in sorted(
            validator.iter_errors(document),
            key=lambda item: (
                tuple(str(part) for part in item.absolute_path),
                item.message,
            ),
        )
    )
    if schema_issues:
        raise LifValidationError(schema_issues)

    if not isinstance(document, dict):
        raise LifValidationError(
            (LifValidationIssue("$", "must be a JSON object"),)
        )

    semantic_issues = _semantic_issues(document)
    if semantic_issues:
        raise LifValidationError(tuple(semantic_issues))


def _semantic_issues(document: JsonObject) -> list[LifValidationIssue]:
    issues: list[LifValidationIssue] = []
    metadata = document["metaInformation"]
    layouts = document["layouts"]

    if metadata["lifVersion"] != LIF_VERSION:
        issues.append(
            LifValidationIssue(
                "$.metaInformation.lifVersion",
                f"must be '{LIF_VERSION}'",
            )
        )
    _check_utc_timestamp(
        metadata["exportTimestamp"],
        "$.metaInformation.exportTimestamp",
        issues,
    )
    if not layouts:
        issues.append(
            LifValidationIssue(
                "$.layouts",
                "must contain at least one layout",
            )
        )
        return issues

    global_layout_ids: set[str] = set()
    global_node_ids: set[str] = set()
    global_edge_ids: set[str] = set()
    global_station_ids: set[str] = set()

    for layout_index, layout in enumerate(layouts):
        layout_path = f"$.layouts[{layout_index}]"
        _check_unique_non_empty_id(
            layout["layoutId"],
            f"{layout_path}.layoutId",
            global_layout_ids,
            issues,
        )

        nodes = layout["nodes"]
        edges = layout["edges"]
        stations = layout["stations"]
        local_nodes: dict[str, JsonObject] = {}

        for node_index, node in enumerate(nodes):
            node_path = f"{layout_path}.nodes[{node_index}]"
            node_id = node["nodeId"]
            _check_unique_non_empty_id(
                node_id,
                f"{node_path}.nodeId",
                global_node_ids,
                issues,
            )
            local_nodes[node_id] = node
            map_id = node.get("mapId")
            if map_id is not None and (
                not isinstance(map_id, str) or not map_id.strip()
            ):
                issues.append(
                    LifValidationIssue(
                        f"{node_path}.mapId",
                        "must be a non-empty string when provided",
                    )
                )
            properties = node["vehicleTypeNodeProperties"]
            if not properties:
                issues.append(
                    LifValidationIssue(
                        f"{node_path}.vehicleTypeNodeProperties",
                        "must contain at least one vehicle type",
                    )
                )
            _check_vehicle_types(
                properties,
                f"{node_path}.vehicleTypeNodeProperties",
                issues,
            )
            for property_index, vehicle_property in enumerate(properties):
                if "theta" in vehicle_property:
                    _check_angle(
                        vehicle_property["theta"],
                        (
                            f"{node_path}.vehicleTypeNodeProperties"
                            f"[{property_index}].theta"
                        ),
                        issues,
                    )

        for edge_index, edge in enumerate(edges):
            edge_path = f"{layout_path}.edges[{edge_index}]"
            _check_unique_non_empty_id(
                edge["edgeId"],
                f"{edge_path}.edgeId",
                global_edge_ids,
                issues,
            )
            start_id = edge["startNodeId"]
            end_id = edge["endNodeId"]
            if start_id not in local_nodes:
                issues.append(
                    LifValidationIssue(
                        f"{edge_path}.startNodeId",
                        f"references unknown node '{start_id}'",
                    )
                )
            if end_id not in local_nodes:
                issues.append(
                    LifValidationIssue(
                        f"{edge_path}.endNodeId",
                        f"references unknown node '{end_id}'",
                    )
                )

            properties = edge["vehicleTypeEdgeProperties"]
            if not properties:
                issues.append(
                    LifValidationIssue(
                        f"{edge_path}.vehicleTypeEdgeProperties",
                        "must contain at least one vehicle type",
                    )
                )
            _check_vehicle_types(
                properties,
                f"{edge_path}.vehicleTypeEdgeProperties",
                issues,
            )
            for property_index, vehicle_property in enumerate(properties):
                property_path = (
                    f"{edge_path}.vehicleTypeEdgeProperties"
                    f"[{property_index}]"
                )
                if "vehicleOrientation" in vehicle_property:
                    _check_angle(
                        vehicle_property["vehicleOrientation"],
                        f"{property_path}.vehicleOrientation",
                        issues,
                    )
                for field_name in ("maxSpeed", "maxRotationSpeed"):
                    if field_name in vehicle_property and (
                        vehicle_property[field_name] < 0
                    ):
                        issues.append(
                            LifValidationIssue(
                                f"{property_path}.{field_name}",
                                "must not be negative",
                            )
                        )
                trajectory = vehicle_property.get("trajectory")
                if trajectory is not None:
                    _check_trajectory(
                        trajectory,
                        property_path,
                        local_nodes.get(start_id),
                        local_nodes.get(end_id),
                        issues,
                    )

        for station_index, station in enumerate(stations):
            station_path = f"{layout_path}.stations[{station_index}]"
            _check_unique_non_empty_id(
                station["stationId"],
                f"{station_path}.stationId",
                global_station_ids,
                issues,
            )
            interaction_ids = station["interactionNodeIds"]
            if not interaction_ids:
                issues.append(
                    LifValidationIssue(
                        f"{station_path}.interactionNodeIds",
                        "must contain at least one node ID",
                    )
                )
            for reference_index, node_id in enumerate(interaction_ids):
                if node_id not in local_nodes:
                    issues.append(
                        LifValidationIssue(
                            (
                                f"{station_path}.interactionNodeIds"
                                f"[{reference_index}]"
                            ),
                            f"references unknown node '{node_id}'",
                        )
                    )
            station_position = station.get("stationPosition")
            if station_position is not None and "theta" in station_position:
                _check_angle(
                    station_position["theta"],
                    f"{station_path}.stationPosition.theta",
                    issues,
                )

    return issues


def _check_utc_timestamp(
    value: object,
    path: str,
    issues: list[LifValidationIssue],
) -> None:
    if not isinstance(value, str) or not UTC_TIMESTAMP_PATTERN.fullmatch(value):
        issues.append(
            LifValidationIssue(
                path,
                "must be an ISO 8601 UTC timestamp ending in 'Z'",
            )
        )
        return
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        issues.append(
            LifValidationIssue(path, "contains an invalid calendar value")
        )


def _check_unique_non_empty_id(
    value: object,
    path: str,
    identifiers: set[str],
    issues: list[LifValidationIssue],
) -> None:
    if not isinstance(value, str) or not value.strip():
        issues.append(LifValidationIssue(path, "must be a non-empty string"))
        return
    if value in identifiers:
        issues.append(LifValidationIssue(path, f"duplicate ID '{value}'"))
        return
    identifiers.add(value)


def _check_vehicle_types(
    properties: list[JsonObject],
    path: str,
    issues: list[LifValidationIssue],
) -> None:
    vehicle_type_ids: set[str] = set()
    for index, item in enumerate(properties):
        vehicle_type_id = item["vehicleTypeId"]
        _check_unique_non_empty_id(
            vehicle_type_id,
            f"{path}[{index}].vehicleTypeId",
            vehicle_type_ids,
            issues,
        )


def _check_angle(
    value: float,
    path: str,
    issues: list[LifValidationIssue],
) -> None:
    if not math.isfinite(value) or value < -math.pi or value > math.pi:
        issues.append(
            LifValidationIssue(path, "must be within [-Pi, Pi] radians")
        )


def _check_trajectory(
    trajectory: JsonObject,
    property_path: str,
    start_node: JsonObject | None,
    end_node: JsonObject | None,
    issues: list[LifValidationIssue],
) -> None:
    trajectory_path = f"{property_path}.trajectory"
    degree_value = trajectory.get("degree", 1)
    if not isinstance(degree_value, (int, float)) or isinstance(
        degree_value,
        bool,
    ):
        return
    degree = int(degree_value)
    if degree != degree_value:
        issues.append(
            LifValidationIssue(
                f"{trajectory_path}.degree",
                "must be an integer value",
            )
        )
        return

    control_points = trajectory["controlPoints"]
    knot_vector = trajectory["knotVector"]
    expected_knot_count = len(control_points) + degree + 1
    if len(knot_vector) != expected_knot_count:
        issues.append(
            LifValidationIssue(
                f"{trajectory_path}.knotVector",
                (
                    f"must contain {expected_knot_count} values for "
                    f"{len(control_points)} control points and degree {degree}"
                ),
            )
        )
    if any(
        knot_vector[index] > knot_vector[index + 1]
        for index in range(len(knot_vector) - 1)
    ):
        issues.append(
            LifValidationIssue(
                f"{trajectory_path}.knotVector",
                "must be monotonically non-decreasing",
            )
        )
    if not control_points:
        issues.append(
            LifValidationIssue(
                f"{trajectory_path}.controlPoints",
                "must contain at least one control point",
            )
        )
        return

    if start_node is not None and not _same_xy(
        control_points[0],
        start_node["nodePosition"],
    ):
        issues.append(
            LifValidationIssue(
                f"{trajectory_path}.controlPoints[0]",
                "must match the start node position",
            )
        )
    if end_node is not None and not _same_xy(
        control_points[-1],
        end_node["nodePosition"],
    ):
        issues.append(
            LifValidationIssue(
                f"{trajectory_path}.controlPoints[-1]",
                "must match the end node position",
            )
        )


def _same_xy(first: JsonObject, second: JsonObject) -> bool:
    return math.isclose(first["x"], second["x"], abs_tol=1e-9) and math.isclose(
        first["y"],
        second["y"],
        abs_tol=1e-9,
    )


def _json_path(parts: object) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


__all__ = [
    "LIF_VERSION",
    "LifValidationError",
    "LifValidationIssue",
    "load_lif_schema",
    "validate_lif_document",
]
