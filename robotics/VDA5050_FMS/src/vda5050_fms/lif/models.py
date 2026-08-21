from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LifMetaInformation:
    project_identification: str
    creator: str
    export_timestamp: str
    lif_version: str


@dataclass(frozen=True, slots=True)
class LifPosition:
    x: float
    y: float
    theta: float | None = None


@dataclass(frozen=True, slots=True)
class LifNode:
    node_id: str
    position: LifPosition
    vehicle_type_ids: tuple[str, ...]
    node_name: str | None = None
    map_id: str | None = None


@dataclass(frozen=True, slots=True)
class LifEdge:
    edge_id: str
    start_node_id: str
    end_node_id: str
    vehicle_type_ids: tuple[str, ...]
    edge_name: str | None = None


@dataclass(frozen=True, slots=True)
class LifStation:
    station_id: str
    interaction_node_ids: tuple[str, ...]
    station_name: str | None = None
    position: LifPosition | None = None


@dataclass(frozen=True, slots=True)
class LifBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @classmethod
    def from_positions(
        cls,
        positions: Iterable[LifPosition],
    ) -> LifBounds:
        position_list = tuple(positions)

        if not position_list:
            raise ValueError(
                "At least one position is required"
            )

        return cls(
            min_x=min(item.x for item in position_list),
            min_y=min(item.y for item in position_list),
            max_x=max(item.x for item in position_list),
            max_y=max(item.y for item in position_list),
        )


@dataclass(frozen=True, slots=True)
class LifLayout:
    layout_id: str
    layout_version: str
    nodes: tuple[LifNode, ...]
    edges: tuple[LifEdge, ...]
    stations: tuple[LifStation, ...]
    layout_name: str | None = None
    layout_level_id: str | None = None
    layout_description: str | None = None

    @property
    def bounds(self) -> LifBounds:
        positions = [
            node.position for node in self.nodes
        ]
        positions.extend(
            station.position
            for station in self.stations
            if station.position is not None
        )
        return LifBounds.from_positions(positions)

    @property
    def map_ids(self) -> frozenset[str]:
        return frozenset(
            node.map_id
            for node in self.nodes
            if node.map_id is not None
        )

    def node_by_id(self, node_id: str) -> LifNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node

        raise KeyError(node_id)


@dataclass(frozen=True, slots=True)
class LifDocument:
    meta_information: LifMetaInformation
    layouts: tuple[LifLayout, ...]

    def layout_by_id(
        self,
        layout_id: str,
    ) -> LifLayout:
        for layout in self.layouts:
            if layout.layout_id == layout_id:
                return layout

        raise KeyError(layout_id)