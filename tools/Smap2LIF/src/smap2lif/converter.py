"""Convert validated native 2D source maps to LIF 1.0.0 documents."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from smap2lif.lif_validator import validate_lif_document
from smap2lif.source_map import (
    Point2D,
    SourceMap,
    SourceMapBinLocation,
    SourceMapCurve,
    SourceMapPoint,
    SourceMapStationTask,
    load_source_map,
)


JsonObject = dict[str, Any]
LIF_VERSION = "1.0.0"
DEFAULT_CREATOR = "Smap2LIF"
DEFAULT_LAYOUT_DESCRIPTION = (
    "Topology converted from a native 2D source map. "
    "Non-topological occupancy, line and area data are not exported."
)


class ConversionError(ValueError):
    """Raised when validated source data cannot be mapped safely."""


class WarningLevel(str, Enum):
    """Severity assigned to one conversion warning."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ConversionWarning:
    """One inspectable conversion warning."""

    level: WarningLevel
    code: str
    message: str

    def format(self) -> str:
        """Return a concise log representation."""

        return f"[{self.level.value}] {self.code}: {self.message}"


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    """User-selectable values applied to one LIF export."""

    vehicle_type_id: str
    creator: str = DEFAULT_CREATOR
    project_identification: str | None = None
    layout_id: str | None = None
    layout_name: str | None = None
    layout_version: str | None = None
    map_id: str | None = None
    layout_description: str = DEFAULT_LAYOUT_DESCRIPTION
    include_stations: bool = True
    rotation_allowed: bool = False


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Converted LIF document together with a conversion report."""

    document: JsonObject
    node_count: int
    edge_count: int
    station_count: int
    trajectory_count: int
    action_count: int
    warnings: tuple[ConversionWarning, ...]
    schema_validated: bool

    @property
    def has_critical_warnings(self) -> bool:
        """Return whether explicit user review is required before export."""

        return any(
            warning.level is WarningLevel.CRITICAL
            for warning in self.warnings
        )


def convert_source_map(
    source_map: SourceMap,
    options: ConversionOptions,
    *,
    exported_at: datetime | None = None,
) -> ConversionResult:
    """Convert a validated source map into one LIF 1.0.0 document."""

    vehicle_type_id = _required_text(
        options.vehicle_type_id,
        "vehicle_type_id",
    )
    creator = _required_text(options.creator, "creator")
    layout_description = _required_text(
        options.layout_description,
        "layout_description",
    )
    project_identification = _optional_text(
        options.project_identification,
        source_map.map_name,
        "project_identification",
    )
    layout_name = _optional_text(
        options.layout_name,
        source_map.map_name,
        "layout_name",
    )
    layout_version = _optional_text(
        options.layout_version,
        source_map.source_version,
        "layout_version",
    )
    layout_id = _optional_text(
        options.layout_id,
        _default_layout_id(source_map.map_name),
        "layout_id",
    )
    map_id = _optional_text(
        options.map_id,
        source_map.map_name,
        "map_id",
    )

    _validate_supported_curve_modes(source_map)
    points_by_id = {
        point.point_id: point for point in source_map.points
    }
    node_actions, action_warnings = _build_node_actions(source_map)

    nodes = [
        _convert_node(
            point,
            map_id,
            vehicle_type_id,
            node_actions.get(point.point_id, ()),
        )
        for point in source_map.points
    ]
    edges = [
        _convert_edge(
            curve,
            points_by_id[curve.start.point_id],
            points_by_id[curve.end.point_id],
            vehicle_type_id,
            options.rotation_allowed,
        )
        for curve in source_map.curves
    ]

    if options.include_stations:
        stations = [
            _convert_station(
                point,
                source_map.bin_locations_for_point(point.point_id),
            )
            for point in source_map.points
            if _is_station_point(point, source_map)
        ]
    else:
        stations = []

    warnings = _build_warnings(
        source_map,
        options,
        layout_version,
        node_actions,
        action_warnings,
    )

    document: JsonObject = {
        "metaInformation": {
            "projectIdentification": project_identification,
            "creator": creator,
            "exportTimestamp": _format_export_timestamp(exported_at),
            "lifVersion": LIF_VERSION,
        },
        "layouts": [
            {
                "layoutId": layout_id,
                "layoutName": layout_name,
                "layoutVersion": layout_version,
                "layoutDescription": layout_description,
                "nodes": nodes,
                "edges": edges,
                "stations": stations,
            }
        ],
    }

    validate_lif_document(document)

    trajectory_count = sum(
        1
        for edge in edges
        if "trajectory" in edge["vehicleTypeEdgeProperties"][0]
    )
    action_count = sum(
        len(item.get("actions", []))
        for node in nodes
        for item in node["vehicleTypeNodeProperties"]
    )

    return ConversionResult(
        document=document,
        node_count=len(nodes),
        edge_count=len(edges),
        station_count=len(stations),
        trajectory_count=trajectory_count,
        action_count=action_count,
        warnings=warnings,
        schema_validated=True,
    )


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
    options: ConversionOptions,
    *,
    exported_at: datetime | None = None,
) -> ConversionResult:
    """Load, convert, validate and atomically write one LIF document."""

    source_map = load_source_map(input_path)
    result = convert_source_map(
        source_map,
        options,
        exported_at=exported_at,
    )
    write_lif_file(result.document, output_path)
    return result


def write_lif_file(document: JsonObject, output_path: str | Path) -> Path:
    """Atomically write an indented UTF-8 LIF JSON file."""

    validate_lif_document(document)
    target = Path(output_path)
    temporary_path: Path | None = None

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(
                document,
                stream,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(target)
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ConversionError(
            f"Could not write LIF file '{target}': {exc}"
        ) from exc

    return target


def _convert_node(
    point: SourceMapPoint,
    map_id: str,
    vehicle_type_id: str,
    actions: tuple[JsonObject, ...],
) -> JsonObject:
    vehicle_properties: JsonObject = {
        "vehicleTypeId": vehicle_type_id,
    }

    if point.theta is not None and not point.ignore_direction:
        vehicle_properties["theta"] = _normalize_angle(point.theta)
    if actions:
        vehicle_properties["actions"] = list(actions)

    return {
        "nodeId": point.point_id,
        "nodeName": point.point_id,
        "nodeDescription": f"Source point type: {point.class_name}",
        "mapId": map_id,
        "nodePosition": _point_to_json(point.position),
        "vehicleTypeNodeProperties": [vehicle_properties],
    }


def _convert_edge(
    curve: SourceMapCurve,
    start_point: SourceMapPoint,
    end_point: SourceMapPoint,
    vehicle_type_id: str,
    rotation_allowed: bool,
) -> JsonObject:
    vehicle_properties: JsonObject = {
        "vehicleTypeId": vehicle_type_id,
        "vehicleOrientation": _convert_direction(curve),
        "orientationType": "TANGENTIAL",
        "rotationAllowed": rotation_allowed,
    }

    start_rotation = _rotation_at_node(start_point)
    if start_rotation is not None:
        vehicle_properties["rotationAtStartNodeAllowed"] = start_rotation
    end_rotation = _rotation_at_node(end_point)
    if end_rotation is not None:
        vehicle_properties["rotationAtEndNodeAllowed"] = end_rotation

    maximum_speed = curve.property_value("maxspeed")
    if maximum_speed is not None:
        vehicle_properties["maxSpeed"] = _positive_or_zero_number(
            maximum_speed,
            f"curve '{curve.curve_id}' property 'maxspeed'",
        )

    maximum_rotation_speed = curve.property_value("maxrot")
    if maximum_rotation_speed is not None:
        vehicle_properties["maxRotationSpeed"] = _positive_or_zero_number(
            maximum_rotation_speed,
            f"curve '{curve.curve_id}' property 'maxrot'",
        )

    if curve.class_name == "DegenerateBezier":
        vehicle_properties["trajectory"] = _convert_trajectory(curve)

    return {
        "edgeId": curve.curve_id,
        "edgeName": curve.curve_id,
        "edgeDescription": f"Source curve type: {curve.class_name}",
        "startNodeId": curve.start.point_id,
        "endNodeId": curve.end.point_id,
        "vehicleTypeEdgeProperties": [vehicle_properties],
    }


def _convert_trajectory(curve: SourceMapCurve) -> JsonObject:
    if curve.control_point_1 is None or curve.control_point_2 is None:
        raise ConversionError(
            f"Curve '{curve.curve_id}' is missing control points."
        )

    return {
        "degree": 3,
        "knotVector": [
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
        ],
        "controlPoints": [
            _point_to_json(curve.start.position),
            _point_to_json(curve.control_point_1),
            _point_to_json(curve.control_point_2),
            _point_to_json(curve.end.position),
        ],
    }


def _convert_station(
    point: SourceMapPoint,
    bin_locations: tuple[SourceMapBinLocation, ...],
) -> JsonObject:
    position = (
        bin_locations[0].position
        if len(bin_locations) == 1
        else point.position
    )
    station_position = _point_to_json(position)
    if point.theta is not None and not point.ignore_direction:
        station_position["theta"] = _normalize_angle(point.theta)

    label = point.property_value("label")
    if isinstance(label, str) and label.strip():
        station_name = label.strip()
    else:
        station_name = point.point_id

    return {
        "stationId": point.point_id,
        "interactionNodeIds": [point.point_id],
        "stationName": station_name,
        "stationDescription": f"Source station type: {point.class_name}",
        "stationPosition": station_position,
    }


def _is_station_point(point: SourceMapPoint, source_map: SourceMap) -> bool:
    if point.class_name in {"ActionPoint", "ChargePoint"}:
        return True
    if source_map.bin_locations_for_point(point.point_id):
        return True
    label = point.property_value("label")
    return isinstance(label, str) and bool(label.strip())


def _build_node_actions(
    source_map: SourceMap,
) -> tuple[
    dict[str, tuple[JsonObject, ...]],
    tuple[ConversionWarning, ...],
]:
    actions_by_point: dict[str, list[JsonObject]] = defaultdict(list)
    warnings: list[ConversionWarning] = []
    ignored_parameter_count = 0

    for point in source_map.points:
        if point.class_name == "ChargePoint":
            actions_by_point[point.point_id].append(
                {
                    "actionType": "startCharging",
                    "actionDescription": "Charging is available at this node.",
                    "requirementType": "CONDITIONAL",
                    "blockingType": "HARD",
                }
            )

    for location in source_map.bin_locations:
        for task in location.tasks:
            action = _convert_station_task(task)
            if action is None:
                warnings.append(
                    ConversionWarning(
                        WarningLevel.CRITICAL,
                        "UNMAPPED_STATION_TASK",
                        (
                            f"Station '{location.point_id}' has unsupported "
                            f"task type '{task.task_type}'."
                        ),
                    )
                )
                continue
            if action not in actions_by_point[location.point_id]:
                actions_by_point[location.point_id].append(action)
            ignored_parameter_count += sum(
                parameter.name != "end_height"
                for parameter in task.parameters
            )

    if ignored_parameter_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.WARNING,
                "UNMAPPED_TASK_PARAMETERS",
                (
                    f"Skipped {ignored_parameter_count} source task parameters "
                    "that have no safe standard LIF mapping."
                ),
            )
        )

    return (
        {
            point_id: tuple(actions)
            for point_id, actions in actions_by_point.items()
        },
        tuple(warnings),
    )


def _convert_station_task(
    task: SourceMapStationTask,
) -> JsonObject | None:
    action_type_by_task = {
        "LOAD": "pick",
        "UNLOAD": "drop",
    }
    action_type = action_type_by_task.get(task.task_type)
    if action_type is None:
        return None

    action: JsonObject = {
        "actionType": action_type,
        "actionDescription": (
            f"Available station action converted from source task "
            f"{task.task_type}."
        ),
        "requirementType": "CONDITIONAL",
        "blockingType": "HARD",
    }
    height = task.parameter_value("end_height")
    if height is not None:
        height_number = _positive_or_zero_number(
            height,
            f"station task '{task.task_type}' parameter 'end_height'",
        )
        action["actionParameters"] = [
            {
                "key": "height",
                "value": _format_number(height_number),
            }
        ]
    return action


def _rotation_at_node(point: SourceMapPoint) -> str | None:
    spin = point.property_value("spin")
    if spin is None:
        return None
    if not isinstance(spin, bool):
        raise ConversionError(
            f"Point '{point.point_id}' property 'spin' must be boolean."
        )
    return "BOTH" if spin else "NONE"


def _convert_direction(curve: SourceMapCurve) -> float:
    direction = curve.property_value("direction")

    if isinstance(direction, bool) or not isinstance(direction, (int, float)):
        raise ConversionError(
            f"Curve '{curve.curve_id}' requires numeric property 'direction'."
        )
    if direction == 0:
        return 0.0
    if direction == 1:
        return math.pi
    raise ConversionError(
        f"Curve '{curve.curve_id}' has unsupported direction '{direction}'."
    )


def _validate_supported_curve_modes(source_map: SourceMap) -> None:
    for curve in source_map.curves:
        move_style = curve.property_value("movestyle")
        if move_style is not None and move_style != 0:
            raise ConversionError(
                f"Curve '{curve.curve_id}' has unsupported movestyle "
                f"'{move_style}'."
            )


def _positive_or_zero_number(value: object, description: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConversionError(f"{description} must be numeric.")

    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ConversionError(
            f"{description} must be a finite number greater than or equal to zero."
        )
    return number


def _point_to_json(point: Point2D) -> JsonObject:
    return {
        "x": point.x,
        "y": point.y,
    }


def _normalize_angle(value: float) -> float:
    normalized = (value + math.pi) % (2.0 * math.pi) - math.pi

    if math.isclose(normalized, -math.pi) and value > 0:
        return math.pi
    if math.isclose(normalized, 0.0, abs_tol=1e-15):
        return 0.0
    return normalized


def _format_export_timestamp(value: datetime | None) -> str:
    timestamp = value or datetime.now(timezone.utc)

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ConversionError("exported_at must include timezone information.")

    utc_timestamp = timestamp.astimezone(timezone.utc)
    return utc_timestamp.isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _format_number(value: float) -> str:
    return format(value, ".15g")


def _default_layout_id(map_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"urn:smap2lif:layout:{map_name}"))


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConversionError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _optional_text(
    value: str | None,
    fallback: str,
    field_name: str,
) -> str:
    if value is None:
        return _required_text(fallback, field_name)
    return _required_text(value, field_name)


def _build_warnings(
    source_map: SourceMap,
    options: ConversionOptions,
    layout_version: str,
    node_actions: dict[str, tuple[JsonObject, ...]],
    action_warnings: tuple[ConversionWarning, ...],
) -> tuple[ConversionWarning, ...]:
    warnings: list[ConversionWarning] = list(action_warnings)

    if source_map.counts.normal_positions:
        warnings.append(
            ConversionWarning(
                WarningLevel.INFO,
                "OCCUPANCY_DATA_SKIPPED",
                (
                    f"Skipped {source_map.counts.normal_positions} occupancy "
                    "positions; LIF contains routing topology, not occupancy data."
                ),
            )
        )

    line_counts = Counter(source_map.line_classes)
    forbidden_line_count = line_counts.pop("ForbiddenLine", 0)
    if forbidden_line_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.CRITICAL,
                "FORBIDDEN_LINES_SKIPPED",
                (
                    f"Skipped {forbidden_line_count} forbidden line object(s). "
                    "Confirm that the exported routing graph cannot cross them."
                ),
            )
        )
    feature_line_count = line_counts.pop("FeatureLine", 0)
    if feature_line_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.INFO,
                "FEATURE_LINES_SKIPPED",
                f"Skipped {feature_line_count} localization feature line(s).",
            )
        )
    if line_counts:
        warnings.append(
            ConversionWarning(
                WarningLevel.WARNING,
                "OTHER_LINES_SKIPPED",
                _format_class_counts("Skipped line types", line_counts),
            )
        )

    area_counts = Counter(source_map.area_classes)
    speed_area_count = area_counts.pop("SafeSpeedLimitArea", 0)
    if speed_area_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.CRITICAL,
                "SAFETY_SPEED_AREAS_SKIPPED",
                (
                    f"Skipped {speed_area_count} safety speed area(s). "
                    "Their polygon speed restrictions are not represented in "
                    "LIF 1.0.0."
                ),
            )
        )
    shielded_area_count = area_counts.pop("AreaShielded", 0)
    if shielded_area_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.CRITICAL,
                "SHIELDED_AREAS_SKIPPED",
                (
                    f"Skipped {shielded_area_count} shielded area(s). "
                    "Safety sensor behavior must remain configured outside LIF."
                ),
            )
        )
    if area_counts:
        warnings.append(
            ConversionWarning(
                WarningLevel.WARNING,
                "OTHER_AREAS_SKIPPED",
                _format_class_counts("Skipped area types", area_counts),
            )
        )

    if source_map.counts.external_devices:
        warnings.append(
            ConversionWarning(
                WarningLevel.INFO,
                "EXTERNAL_DEVICES_SKIPPED",
                (
                    f"Skipped {source_map.counts.external_devices} external "
                    "visualization device object(s)."
                ),
            )
        )

    width_count = sum(
        curve.property_value("width") is not None
        for curve in source_map.curves
    )
    if width_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.WARNING,
                "EDGE_WIDTH_SKIPPED",
                (
                    f"Skipped edge width on {width_count} curve(s); LIF 1.0.0 "
                    "has no standard corridor-width field."
                ),
            )
        )

    rotation_acceleration_count = sum(
        curve.property_value("maxrotacc") is not None
        for curve in source_map.curves
    )
    if rotation_acceleration_count:
        warnings.append(
            ConversionWarning(
                WarningLevel.WARNING,
                "ROTATION_ACCELERATION_SKIPPED",
                (
                    "Skipped maximum rotation acceleration on "
                    f"{rotation_acceleration_count} curve(s); LIF 1.0.0 has no "
                    "corresponding field."
                ),
            )
        )

    station_points = [
        point
        for point in source_map.points
        if _is_station_point(point, source_map)
    ]
    for point in station_points:
        locations = source_map.bin_locations_for_point(point.point_id)
        if len(locations) > 1:
            warnings.append(
                ConversionWarning(
                    WarningLevel.CRITICAL,
                    "AMBIGUOUS_STATION_POSITION",
                    (
                        f"Station '{point.point_id}' is linked to "
                        f"{len(locations)} physical source locations."
                    ),
                )
            )
        if not node_actions.get(point.point_id):
            warnings.append(
                ConversionWarning(
                    WarningLevel.WARNING,
                    "STATION_WITHOUT_ACTIONS",
                    (
                        f"Station '{point.point_id}' has no mapped action, so "
                        "its purpose is not machine-readable in LIF."
                    ),
                )
            )

    if not options.include_stations:
        warnings.append(
            ConversionWarning(
                WarningLevel.WARNING,
                "STATIONS_DISABLED",
                "Station export was disabled by the user.",
            )
        )

    if not layout_version.isdigit():
        warnings.append(
            ConversionWarning(
                WarningLevel.INFO,
                "NON_INTEGER_LAYOUT_VERSION",
                (
                    f"Layout version '{layout_version}' is valid, but LIF "
                    "recommends an incrementing integer string such as '1'."
                ),
            )
        )

    return tuple(warnings)


def _format_class_counts(
    prefix: str,
    counts: Counter[str],
) -> str:
    details = ", ".join(
        f"{class_name}={count}"
        for class_name, count in sorted(counts.items())
    )
    return f"{prefix}: {details}."


__all__ = [
    "ConversionError",
    "ConversionOptions",
    "ConversionResult",
    "ConversionWarning",
    "DEFAULT_CREATOR",
    "DEFAULT_LAYOUT_DESCRIPTION",
    "LIF_VERSION",
    "WarningLevel",
    "convert_file",
    "convert_source_map",
    "write_lif_file",
]
