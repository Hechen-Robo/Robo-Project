from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from vda5050_fms.lif.models import (
    LifDocument,
    LifEdge,
    LifLayout,
    LifMetaInformation,
    LifNode,
    LifPosition,
    LifStation,
)
from vda5050_fms.lif.validator import (
    LifValidationError,
    load_lif_json,
    validate_lif_mapping,
)


def _as_mapping(
    value: object,
    path: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise LifValidationError(
            f"{path} must be an object"
        )
    return value


def _as_list(
    value: object,
    path: str,
) -> list[object]:
    if not isinstance(value, list):
        raise LifValidationError(
            f"{path} must be an array"
        )
    return value


def _required_string(
    payload: Mapping[str, object],
    key: str,
    path: str,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str):
        raise LifValidationError(
            f"{path}.{key} must be a string"
        )

    return value


def _optional_string(
    payload: Mapping[str, object],
    key: str,
) -> str | None:
    value = payload.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise LifValidationError(
            f"{key} must be a string"
        )

    return value


def _required_number(
    payload: Mapping[str, object],
    key: str,
    path: str,
) -> float:
    value = payload.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise LifValidationError(
            f"{path}.{key} must be a number"
        )

    return float(value)


def _parse_position(
    payload: Mapping[str, object],
    path: str,
) -> LifPosition:
    theta_value = payload.get("theta")

    theta = (
        None
        if theta_value is None
        else _required_number(payload, "theta", path)
    )

    return LifPosition(
        x=_required_number(payload, "x", path),
        y=_required_number(payload, "y", path),
        theta=theta,
    )


def _parse_vehicle_type_ids(
    raw_properties: object,
    path: str,
) -> tuple[str, ...]:
    properties = _as_list(raw_properties, path)

    if not properties:
        raise LifValidationError(
            f"{path} must not be empty"
        )

    vehicle_type_ids: list[str] = []

    for index, item in enumerate(properties):
        property_payload = _as_mapping(
            item,
            f"{path}[{index}]",
        )
        vehicle_type_id = _required_string(
            property_payload,
            "vehicleTypeId",
            f"{path}[{index}]",
        )

        if vehicle_type_id in vehicle_type_ids:
            raise LifValidationError(
                f"Duplicate vehicleTypeId at {path}: "
                f"{vehicle_type_id}"
            )

        vehicle_type_ids.append(vehicle_type_id)

    return tuple(vehicle_type_ids)


def _parse_node(
    payload: Mapping[str, object],
    path: str,
) -> LifNode:
    position_payload = _as_mapping(
        payload["nodePosition"],
        f"{path}.nodePosition",
    )

    return LifNode(
        node_id=_required_string(
            payload,
            "nodeId",
            path,
        ),
        node_name=_optional_string(
            payload,
            "nodeName",
        ),
        map_id=_optional_string(
            payload,
            "mapId",
        ),
        position=_parse_position(
            position_payload,
            f"{path}.nodePosition",
        ),
        vehicle_type_ids=_parse_vehicle_type_ids(
            payload["vehicleTypeNodeProperties"],
            f"{path}.vehicleTypeNodeProperties",
        ),
    )


def _parse_edge(
    payload: Mapping[str, object],
    path: str,
) -> LifEdge:
    return LifEdge(
        edge_id=_required_string(
            payload,
            "edgeId",
            path,
        ),
        edge_name=_optional_string(
            payload,
            "edgeName",
        ),
        start_node_id=_required_string(
            payload,
            "startNodeId",
            path,
        ),
        end_node_id=_required_string(
            payload,
            "endNodeId",
            path,
        ),
        vehicle_type_ids=_parse_vehicle_type_ids(
            payload["vehicleTypeEdgeProperties"],
            f"{path}.vehicleTypeEdgeProperties",
        ),
    )


def _parse_station(
    payload: Mapping[str, object],
    path: str,
) -> LifStation:
    raw_node_ids = _as_list(
        payload["interactionNodeIds"],
        f"{path}.interactionNodeIds",
    )

    interaction_node_ids = tuple(
        str(node_id) for node_id in raw_node_ids
    )

    if not interaction_node_ids:
        raise LifValidationError(
            f"{path}.interactionNodeIds "
            "must not be empty"
        )

    raw_position = payload.get("stationPosition")
    position = None

    if raw_position is not None:
        position_payload = _as_mapping(
            raw_position,
            f"{path}.stationPosition",
        )
        position = _parse_position(
            position_payload,
            f"{path}.stationPosition",
        )

    return LifStation(
        station_id=_required_string(
            payload,
            "stationId",
            path,
        ),
        interaction_node_ids=interaction_node_ids,
        station_name=_optional_string(
            payload,
            "stationName",
        ),
        position=position,
    )


def _parse_layout(
    payload: Mapping[str, object],
    path: str,
) -> LifLayout:
    raw_nodes = _as_list(
        payload["nodes"],
        f"{path}.nodes",
    )
    raw_edges = _as_list(
        payload["edges"],
        f"{path}.edges",
    )
    raw_stations = _as_list(
        payload["stations"],
        f"{path}.stations",
    )

    return LifLayout(
        layout_id=_required_string(
            payload,
            "layoutId",
            path,
        ),
        layout_version=_required_string(
            payload,
            "layoutVersion",
            path,
        ),
        layout_name=_optional_string(
            payload,
            "layoutName",
        ),
        layout_level_id=_optional_string(
            payload,
            "layoutLevelId",
        ),
        layout_description=_optional_string(
            payload,
            "layoutDescription",
        ),
        nodes=tuple(
            _parse_node(
                _as_mapping(
                    item,
                    f"{path}.nodes[{index}]",
                ),
                f"{path}.nodes[{index}]",
            )
            for index, item in enumerate(raw_nodes)
        ),
        edges=tuple(
            _parse_edge(
                _as_mapping(
                    item,
                    f"{path}.edges[{index}]",
                ),
                f"{path}.edges[{index}]",
            )
            for index, item in enumerate(raw_edges)
        ),
        stations=tuple(
            _parse_station(
                _as_mapping(
                    item,
                    f"{path}.stations[{index}]",
                ),
                f"{path}.stations[{index}]",
            )
            for index, item in enumerate(raw_stations)
        ),
    )


def _validate_document_semantics(
    document: LifDocument,
) -> None:
    layout_ids: set[str] = set()
    node_ids: set[str] = set()
    edge_ids: set[str] = set()
    station_ids: set[str] = set()

    for layout in document.layouts:
        if layout.layout_id in layout_ids:
            raise LifValidationError(
                f"Duplicate layoutId: {layout.layout_id}"
            )
        layout_ids.add(layout.layout_id)

        if not layout.nodes:
            raise LifValidationError(
                f"Layout {layout.layout_id} "
                "must contain at least one node"
            )

        for node in layout.nodes:
            if node.node_id in node_ids:
                raise LifValidationError(
                    f"Duplicate nodeId: {node.node_id}"
                )
            node_ids.add(node.node_id)

        for edge in layout.edges:
            if edge.edge_id in edge_ids:
                raise LifValidationError(
                    f"Duplicate edgeId: {edge.edge_id}"
                )
            edge_ids.add(edge.edge_id)

        for station in layout.stations:
            if station.station_id in station_ids:
                raise LifValidationError(
                    "Duplicate stationId: "
                    f"{station.station_id}"
                )
            station_ids.add(station.station_id)

    for layout in document.layouts:
        local_node_ids = {
            node.node_id for node in layout.nodes
        }

        for edge in layout.edges:
            if edge.start_node_id not in local_node_ids:
                raise LifValidationError(
                    f"Edge {edge.edge_id} startNodeId "
                    f"{edge.start_node_id} is not in "
                    f"layout {layout.layout_id}"
                )

            if edge.end_node_id not in node_ids:
                raise LifValidationError(
                    f"Edge {edge.edge_id} endNodeId "
                    f"{edge.end_node_id} does not exist"
                )

        for station in layout.stations:
            for node_id in station.interaction_node_ids:
                if node_id not in local_node_ids:
                    raise LifValidationError(
                        f"Station {station.station_id} "
                        "references unknown nodeId: "
                        f"{node_id}"
                    )


def _build_document(
    payload: Mapping[str, object],
) -> LifDocument:
    raw_meta = _as_mapping(
        payload["metaInformation"],
        "$.metaInformation",
    )
    raw_layouts = _as_list(
        payload["layouts"],
        "$.layouts",
    )

    document = LifDocument(
        meta_information=LifMetaInformation(
            project_identification=_required_string(
                raw_meta,
                "projectIdentification",
                "$.metaInformation",
            ),
            creator=_required_string(
                raw_meta,
                "creator",
                "$.metaInformation",
            ),
            export_timestamp=_required_string(
                raw_meta,
                "exportTimestamp",
                "$.metaInformation",
            ),
            lif_version=_required_string(
                raw_meta,
                "lifVersion",
                "$.metaInformation",
            ),
        ),
        layouts=tuple(
            _parse_layout(
                _as_mapping(
                    item,
                    f"$.layouts[{index}]",
                ),
                f"$.layouts[{index}]",
            )
            for index, item in enumerate(raw_layouts)
        ),
    )

    _validate_document_semantics(document)
    return document


def parse_lif_mapping(
    payload: Mapping[str, object],
) -> LifDocument:
    validate_lif_mapping(payload)
    return _build_document(payload)


def parse_lif_json(
    payload: str | bytes | bytearray,
) -> LifDocument:
    decoded = load_lif_json(payload)
    return _build_document(decoded)


def parse_lif_file(
    path: str | Path,
) -> LifDocument:
    return parse_lif_json(Path(path).read_bytes())