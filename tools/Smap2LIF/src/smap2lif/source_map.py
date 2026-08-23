"""Load and validate native 2D source-map JSON files."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
PropertyValue = str | bool | int | float
TaskParameterValue = str | bool | int | float | None


class SourceMapError(ValueError):
    """Base exception raised while reading a source map."""


class SourceMapLoadError(SourceMapError):
    """Raised when a source-map file cannot be read or decoded."""


class SourceMapValidationError(SourceMapError):
    """Raised when source-map data has an invalid structure."""


@dataclass(frozen=True, slots=True)
class Point2D:
    """A finite two-dimensional coordinate."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class SourceMapProperty:
    """One typed source-map property."""

    name: str
    value_type: str
    value: PropertyValue


@dataclass(frozen=True, slots=True)
class SourceMapPoint:
    """A named topological point from the source map."""

    point_id: str
    class_name: str
    position: Point2D
    theta: float | None = None
    ignore_direction: bool = False
    properties: tuple[SourceMapProperty, ...] = field(default_factory=tuple)

    def property_value(
        self, name: str, default: PropertyValue | None = None
    ) -> PropertyValue | None:
        """Return a decoded property value by name."""

        for item in self.properties:
            if item.name == name:
                return item.value
        return default


@dataclass(frozen=True, slots=True)
class SourceMapTaskParameter:
    """One parameter attached to a source station task."""

    name: str
    value: TaskParameterValue


@dataclass(frozen=True, slots=True)
class SourceMapStationTask:
    """One task declared by a source-map bin location."""

    task_type: str
    operation: str | None
    parameters: tuple[SourceMapTaskParameter, ...] = field(
        default_factory=tuple
    )

    def parameter_value(
        self,
        name: str,
        default: TaskParameterValue = None,
    ) -> TaskParameterValue:
        """Return one decoded task parameter."""

        for item in self.parameters:
            if item.name == name:
                return item.value
        return default


@dataclass(frozen=True, slots=True)
class SourceMapBinLocation:
    """Physical station location and tasks linked to a topological point."""

    location_id: str
    point_id: str
    position: Point2D
    tasks: tuple[SourceMapStationTask, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SourceMapEndpoint:
    """One endpoint of a source-map curve."""

    point_id: str
    position: Point2D


@dataclass(frozen=True, slots=True)
class SourceMapCurve:
    """A topological connection between two source-map points."""

    curve_id: str
    class_name: str
    start: SourceMapEndpoint
    end: SourceMapEndpoint
    control_point_1: Point2D | None = None
    control_point_2: Point2D | None = None
    properties: tuple[SourceMapProperty, ...] = field(default_factory=tuple)

    def property_value(
        self, name: str, default: PropertyValue | None = None
    ) -> PropertyValue | None:
        """Return a decoded property value by name."""

        for item in self.properties:
            if item.name == name:
                return item.value
        return default


@dataclass(frozen=True, slots=True)
class SourceMapCounts:
    """Counts of source-map collections, including non-topological data."""

    normal_positions: int
    points: int
    curves: int
    lines: int
    areas: int
    external_devices: int
    bin_locations: int
    bin_tasks: int


@dataclass(frozen=True, slots=True)
class SourceMap:
    """Validated source-map data required by the LIF converter."""

    map_name: str
    map_type: str
    source_version: str
    resolution: float
    minimum_position: Point2D
    maximum_position: Point2D
    points: tuple[SourceMapPoint, ...]
    curves: tuple[SourceMapCurve, ...]
    bin_locations: tuple[SourceMapBinLocation, ...]
    line_classes: tuple[str, ...]
    area_classes: tuple[str, ...]
    external_device_classes: tuple[str, ...]
    counts: SourceMapCounts

    def point_by_id(self, point_id: str) -> SourceMapPoint:
        """Return one point by identifier or raise ``KeyError``."""

        for point in self.points:
            if point.point_id == point_id:
                return point
        raise KeyError(point_id)

    def bin_locations_for_point(
        self,
        point_id: str,
    ) -> tuple[SourceMapBinLocation, ...]:
        """Return bin locations associated with one topological point."""

        return tuple(
            location
            for location in self.bin_locations
            if location.point_id == point_id
        )


def load_source_map(path: str | Path) -> SourceMap:
    """Read a UTF-8 JSON file and return a validated source map."""

    source_path = Path(path)

    try:
        payload = source_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SourceMapLoadError(
            f"Could not read source-map file '{source_path}': {exc}"
        ) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SourceMapLoadError(
            "Invalid JSON in source-map file "
            f"'{source_path}' at line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}"
        ) from exc

    return parse_source_map(data)


def parse_source_map(data: object) -> SourceMap:
    """Validate an already decoded JSON value and build a source map."""

    root = _require_object(data, "$")

    if (
        "metaInformation" in root
        and "layouts" in root
        and "header" not in root
    ):
        raise SourceMapValidationError(
            "The selected file is already a LIF document. "
            "Select an unconverted source-map JSON file."
        )

    header = _require_object(root.get("header"), "$.header")

    map_type = _require_non_empty_string(header, "mapType", "$.header")
    if map_type != "2D-Map":
        raise SourceMapValidationError(
            "$.header.mapType must be '2D-Map'."
        )

    map_name = _require_non_empty_string(header, "mapName", "$.header")
    source_version = _require_non_empty_string(header, "version", "$.header")
    resolution = _require_finite_number(
        header.get("resolution"), "$.header.resolution"
    )
    if resolution <= 0:
        raise SourceMapValidationError(
            "$.header.resolution must be greater than zero."
        )

    minimum_position = _parse_position(
        header.get("minPos"), "$.header.minPos"
    )
    maximum_position = _parse_position(
        header.get("maxPos"), "$.header.maxPos"
    )
    if minimum_position.x > maximum_position.x:
        raise SourceMapValidationError(
            "$.header.minPos.x must not exceed $.header.maxPos.x."
        )
    if minimum_position.y > maximum_position.y:
        raise SourceMapValidationError(
            "$.header.minPos.y must not exceed $.header.maxPos.y."
        )

    point_items = _require_array(
        root.get("advancedPointList"), "$.advancedPointList"
    )
    if not point_items:
        raise SourceMapValidationError(
            "$.advancedPointList must contain at least one point."
        )

    points = tuple(
        _parse_point(item, index)
        for index, item in enumerate(point_items)
    )
    point_ids = _ensure_unique_ids(
        (point.point_id for point in points), "$.advancedPointList"
    )
    points_by_id = {point.point_id: point for point in points}

    curve_items = _require_array(
        root.get("advancedCurveList"), "$.advancedCurveList"
    )
    curves = tuple(
        _parse_curve(item, index)
        for index, item in enumerate(curve_items)
    )
    _ensure_unique_ids(
        (curve.curve_id for curve in curves), "$.advancedCurveList"
    )
    _validate_curve_references(curves, points_by_id)

    normal_positions = _optional_array(
        root, "normalPosList", "$.normalPosList"
    )
    lines = _optional_array(
        root, "advancedLineList", "$.advancedLineList"
    )
    areas = _optional_array(
        root, "advancedAreaList", "$.advancedAreaList"
    )
    external_devices = _optional_array(
        root, "externalDeviceList", "$.externalDeviceList"
    )
    bin_location_groups = _optional_array(
        root, "binLocationsList", "$.binLocationsList"
    )

    line_classes = _parse_class_names(lines, "$.advancedLineList")
    area_classes = _parse_class_names(areas, "$.advancedAreaList")
    external_device_classes = _parse_class_names(
        external_devices,
        "$.externalDeviceList",
    )
    bin_locations = _parse_bin_locations(
        bin_location_groups,
        point_ids,
    )

    return SourceMap(
        map_name=map_name,
        map_type=map_type,
        source_version=source_version,
        resolution=resolution,
        minimum_position=minimum_position,
        maximum_position=maximum_position,
        points=points,
        curves=curves,
        bin_locations=bin_locations,
        line_classes=line_classes,
        area_classes=area_classes,
        external_device_classes=external_device_classes,
        counts=SourceMapCounts(
            normal_positions=len(normal_positions),
            points=len(points),
            curves=len(curves),
            lines=len(lines),
            areas=len(areas),
            external_devices=len(external_devices),
            bin_locations=len(bin_locations),
            bin_tasks=sum(
                len(location.tasks) for location in bin_locations
            ),
        ),
    )


def _parse_point(value: object, index: int) -> SourceMapPoint:
    path = f"$.advancedPointList[{index}]"
    item = _require_object(value, path)

    point_id = _require_non_empty_string(item, "instanceName", path)
    class_name = _require_non_empty_string(item, "className", path)
    position = _parse_position(item.get("pos"), f"{path}.pos")

    theta: float | None = None
    if "dir" in item and item["dir"] is not None:
        theta = _require_finite_number(item["dir"], f"{path}.dir")

    ignore_direction = item.get("ignoreDir", False)
    if not isinstance(ignore_direction, bool):
        raise SourceMapValidationError(
            f"{path}.ignoreDir must be a boolean."
        )

    properties = _parse_properties(item.get("property", []), f"{path}.property")

    return SourceMapPoint(
        point_id=point_id,
        class_name=class_name,
        position=position,
        theta=theta,
        ignore_direction=ignore_direction,
        properties=properties,
    )


def _parse_curve(value: object, index: int) -> SourceMapCurve:
    path = f"$.advancedCurveList[{index}]"
    item = _require_object(value, path)

    curve_id = _require_non_empty_string(item, "instanceName", path)
    class_name = _require_non_empty_string(item, "className", path)
    start = _parse_endpoint(item.get("startPos"), f"{path}.startPos")
    end = _parse_endpoint(item.get("endPos"), f"{path}.endPos")

    control_point_1: Point2D | None = None
    control_point_2: Point2D | None = None
    if class_name == "DegenerateBezier":
        control_point_1 = _parse_position(
            item.get("controlPos1"), f"{path}.controlPos1"
        )
        control_point_2 = _parse_position(
            item.get("controlPos2"), f"{path}.controlPos2"
        )
    elif class_name != "StraightPath":
        raise SourceMapValidationError(
            f"{path}.className has unsupported value '{class_name}'."
        )

    properties = _parse_properties(item.get("property", []), f"{path}.property")

    return SourceMapCurve(
        curve_id=curve_id,
        class_name=class_name,
        start=start,
        end=end,
        control_point_1=control_point_1,
        control_point_2=control_point_2,
        properties=properties,
    )


def _parse_endpoint(value: object, path: str) -> SourceMapEndpoint:
    item = _require_object(value, path)
    point_id = _require_non_empty_string(item, "instanceName", path)
    position = _parse_position(item.get("pos"), f"{path}.pos")
    return SourceMapEndpoint(point_id=point_id, position=position)


def _parse_position(value: object, path: str) -> Point2D:
    item = _require_object(value, path)
    x = _require_finite_number(item.get("x"), f"{path}.x")
    y = _require_finite_number(item.get("y"), f"{path}.y")
    return Point2D(x=x, y=y)


def _parse_properties(
    value: object, path: str
) -> tuple[SourceMapProperty, ...]:
    items = _require_array(value, path)
    properties: list[SourceMapProperty] = []
    names: set[str] = set()

    value_fields = {
        "string": "stringValue",
        "bool": "boolValue",
        "int": "int32Value",
        "int32": "int32Value",
        "uint32": "uint32Value",
        "double": "doubleValue",
        "json": "stringValue",
        "checkBoxGroup": "stringValue",
    }

    for index, value in enumerate(items):
        item_path = f"{path}[{index}]"
        item = _require_object(value, item_path)
        name = _require_non_empty_string(item, "key", item_path)
        value_type = _require_non_empty_string(item, "type", item_path)

        if name in names:
            raise SourceMapValidationError(
                f"{path} contains duplicate property key '{name}'."
            )
        names.add(name)

        value_field = value_fields.get(value_type)
        if value_field is None:
            raise SourceMapValidationError(
                f"{item_path}.type has unsupported value '{value_type}'."
            )

        decoded_value = item.get(value_field)
        value_path = f"{item_path}.{value_field}"
        if value_type in {"string", "json", "checkBoxGroup"}:
            if not isinstance(decoded_value, str):
                raise SourceMapValidationError(
                    f"{value_path} must be a string."
                )
        elif value_type == "bool":
            if not isinstance(decoded_value, bool):
                raise SourceMapValidationError(
                    f"{value_path} must be a boolean."
                )
        elif value_type in {"int", "int32", "uint32"}:
            if isinstance(decoded_value, bool) or not isinstance(
                decoded_value, int
            ):
                raise SourceMapValidationError(
                    f"{value_path} must be an integer."
                )
            if value_type == "uint32" and decoded_value < 0:
                raise SourceMapValidationError(
                    f"{value_path} must not be negative."
                )
        else:
            decoded_value = _require_finite_number(decoded_value, value_path)

        properties.append(
            SourceMapProperty(
                name=name,
                value_type=value_type,
                value=decoded_value,
            )
        )

    return tuple(properties)


def _parse_class_names(
    items: list[object],
    path: str,
) -> tuple[str, ...]:
    class_names: list[str] = []
    for index, value in enumerate(items):
        item_path = f"{path}[{index}]"
        item = _require_object(value, item_path)
        class_names.append(
            _require_non_empty_string(item, "className", item_path)
        )
    return tuple(class_names)


def _parse_bin_locations(
    groups: list[object],
    point_ids: set[str],
) -> tuple[SourceMapBinLocation, ...]:
    locations: list[SourceMapBinLocation] = []
    location_ids: set[str] = set()

    for group_index, group_value in enumerate(groups):
        group_path = f"$.binLocationsList[{group_index}]"
        group = _require_object(group_value, group_path)
        location_items = _require_array(
            group.get("binLocationList"),
            f"{group_path}.binLocationList",
        )

        for location_index, location_value in enumerate(location_items):
            location_path = (
                f"{group_path}.binLocationList[{location_index}]"
            )
            item = _require_object(location_value, location_path)
            location_id = _require_non_empty_string(
                item,
                "instanceName",
                location_path,
            )
            if location_id in location_ids:
                raise SourceMapValidationError(
                    "$.binLocationsList contains duplicate bin location "
                    f"instanceName '{location_id}'."
                )
            location_ids.add(location_id)

            point_id = _require_non_empty_string(
                item,
                "pointName",
                location_path,
            )
            if point_id not in point_ids:
                raise SourceMapValidationError(
                    f"{location_path}.pointName references unknown point "
                    f"'{point_id}'."
                )

            position = _parse_position(
                item.get("pos"),
                f"{location_path}.pos",
            )
            tasks = _parse_bin_tasks(
                item.get("property", []),
                f"{location_path}.property",
            )
            locations.append(
                SourceMapBinLocation(
                    location_id=location_id,
                    point_id=point_id,
                    position=position,
                    tasks=tasks,
                )
            )

    return tuple(locations)


def _parse_bin_tasks(
    value: object,
    path: str,
) -> tuple[SourceMapStationTask, ...]:
    items = _require_array(value, path)
    task_payload: str | None = None

    for index, value in enumerate(items):
        item_path = f"{path}[{index}]"
        item = _require_object(value, item_path)
        key = _require_non_empty_string(item, "key", item_path)
        if key != "binTask":
            continue
        if task_payload is not None:
            raise SourceMapValidationError(
                f"{path} contains duplicate property key 'binTask'."
            )
        raw_payload = item.get("stringValue")
        if not isinstance(raw_payload, str):
            raise SourceMapValidationError(
                f"{item_path}.stringValue must be a string."
            )
        task_payload = raw_payload

    if task_payload is None or not task_payload.strip():
        return ()

    try:
        decoded = json.loads(task_payload)
    except json.JSONDecodeError as exc:
        raise SourceMapValidationError(
            f"{path} binTask contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc

    task_items = _require_array(decoded, f"{path}.binTask")
    tasks: list[SourceMapStationTask] = []
    for index, value in enumerate(task_items):
        task_path = f"{path}.binTask[{index}]"
        task_wrapper = _require_object(value, task_path)
        if len(task_wrapper) != 1:
            raise SourceMapValidationError(
                f"{task_path} must contain exactly one task type."
            )

        task_type_value, definition_value = next(iter(task_wrapper.items()))
        if not isinstance(task_type_value, str) or not task_type_value.strip():
            raise SourceMapValidationError(
                f"{task_path} task type must be a non-empty string."
            )
        definition = _require_object(
            definition_value,
            f"{task_path}.{task_type_value}",
        )

        operation_value = definition.get("operation")
        if operation_value is not None and (
            not isinstance(operation_value, str)
            or not operation_value.strip()
        ):
            raise SourceMapValidationError(
                f"{task_path}.{task_type_value}.operation must be a "
                "non-empty string when provided."
            )
        operation = (
            operation_value.strip()
            if isinstance(operation_value, str)
            else None
        )

        parameters: list[SourceMapTaskParameter] = []
        for name, parameter_value in definition.items():
            if name == "operation":
                continue
            if not isinstance(name, str) or not name:
                raise SourceMapValidationError(
                    f"{task_path}.{task_type_value} contains an invalid "
                    "parameter name."
                )
            if parameter_value is not None and not isinstance(
                parameter_value,
                (str, bool, int, float),
            ):
                raise SourceMapValidationError(
                    f"{task_path}.{task_type_value}.{name} must be a JSON "
                    "scalar."
                )
            if isinstance(parameter_value, float) and not math.isfinite(
                parameter_value
            ):
                raise SourceMapValidationError(
                    f"{task_path}.{task_type_value}.{name} must be finite."
                )
            parameters.append(
                SourceMapTaskParameter(name=name, value=parameter_value)
            )

        tasks.append(
            SourceMapStationTask(
                task_type=task_type_value.strip().upper(),
                operation=operation,
                parameters=tuple(parameters),
            )
        )

    return tuple(tasks)


def _validate_curve_references(
    curves: tuple[SourceMapCurve, ...],
    points_by_id: dict[str, SourceMapPoint],
) -> None:
    for index, curve in enumerate(curves):
        for endpoint_name, endpoint in (
            ("startPos", curve.start),
            ("endPos", curve.end),
        ):
            point = points_by_id.get(endpoint.point_id)
            if point is None:
                raise SourceMapValidationError(
                    f"$.advancedCurveList[{index}].{endpoint_name}.instanceName "
                    f"references unknown point '{endpoint.point_id}'."
                )
            if not _same_position(endpoint.position, point.position):
                raise SourceMapValidationError(
                    f"$.advancedCurveList[{index}].{endpoint_name}.pos "
                    f"does not match point '{endpoint.point_id}'."
                )


def _same_position(first: Point2D, second: Point2D) -> bool:
    return math.isclose(first.x, second.x, abs_tol=1e-9) and math.isclose(
        first.y,
        second.y,
        abs_tol=1e-9,
    )


def _ensure_unique_ids(values: Iterable[str], path: str) -> set[str]:
    identifiers: set[str] = set()
    for identifier in values:
        if identifier in identifiers:
            raise SourceMapValidationError(
                f"{path} contains duplicate instanceName '{identifier}'."
            )
        identifiers.add(identifier)
    return identifiers


def _require_object(value: object, path: str) -> JsonObject:
    if not isinstance(value, dict):
        raise SourceMapValidationError(f"{path} must be a JSON object.")
    return value


def _require_array(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise SourceMapValidationError(f"{path} must be a JSON array.")
    return value


def _optional_array(root: JsonObject, key: str, path: str) -> list[object]:
    if key not in root:
        return []
    return _require_array(root[key], path)


def _require_non_empty_string(
    item: JsonObject, key: str, parent_path: str
) -> str:
    path = f"{parent_path}.{key}"
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceMapValidationError(
            f"{path} must be a non-empty string."
        )
    return value


def _require_finite_number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceMapValidationError(f"{path} must be a number.")

    number = float(value)
    if not math.isfinite(number):
        raise SourceMapValidationError(f"{path} must be finite.")
    return number


__all__ = [
    "Point2D",
    "SourceMap",
    "SourceMapBinLocation",
    "SourceMapCounts",
    "SourceMapCurve",
    "SourceMapEndpoint",
    "SourceMapError",
    "SourceMapLoadError",
    "SourceMapPoint",
    "SourceMapProperty",
    "SourceMapStationTask",
    "SourceMapTaskParameter",
    "SourceMapValidationError",
    "load_source_map",
    "parse_source_map",
]
