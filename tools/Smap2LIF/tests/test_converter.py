from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
import unittest

from smap2lif.converter import (
    ConversionError,
    ConversionOptions,
    WarningLevel,
    convert_file,
    convert_source_map,
)
from smap2lif.source_map import load_source_map, parse_source_map


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "minimal_source_map.json"
)

FIXED_TIMESTAMP = datetime(
    2026,
    8,
    23,
    18,
    30,
    0,
    tzinfo=timezone.utc,
)


def load_fixture_data() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class ConverterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_map = load_source_map(FIXTURE_PATH)
        self.options = ConversionOptions(
            vehicle_type_id="AGV.TYPE-01",
            map_id="MAP-01",
        )

    def test_document_metadata_and_counts(self) -> None:
        result = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )

        metadata = result.document["metaInformation"]
        layout = result.document["layouts"][0]

        self.assertEqual(
            metadata["projectIdentification"],
            "minimal-source-map",
        )
        self.assertEqual(metadata["creator"], "Smap2LIF")
        self.assertEqual(
            metadata["exportTimestamp"],
            "2026-08-23T18:30:00.000Z",
        )
        self.assertEqual(metadata["lifVersion"], "1.0.0")
        self.assertEqual(layout["layoutName"], "minimal-source-map")
        self.assertEqual(layout["layoutVersion"], "1.0.0")
        self.assertEqual(result.node_count, 3)
        self.assertEqual(result.edge_count, 2)
        self.assertEqual(result.station_count, 2)
        self.assertEqual(result.trajectory_count, 1)
        self.assertEqual(result.action_count, 2)
        self.assertTrue(result.schema_validated)

    def test_layout_id_is_stable_for_same_map(self) -> None:
        first = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )
        second = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )

        first_id = first.document["layouts"][0]["layoutId"]
        second_id = second.document["layouts"][0]["layoutId"]

        self.assertEqual(first_id, second_id)

    def test_nodes_preserve_positions_and_orientation(self) -> None:
        result = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )
        nodes = result.document["layouts"][0]["nodes"]
        nodes_by_id = {node["nodeId"]: node for node in nodes}

        start = nodes_by_id["P-001"]
        ignored = nodes_by_id["P-003"]

        self.assertEqual(
            start["nodePosition"],
            {"x": 0.0, "y": 0.0},
        )
        self.assertEqual(
            start["vehicleTypeNodeProperties"][0]["vehicleTypeId"],
            "AGV.TYPE-01",
        )
        self.assertEqual(start["mapId"], "MAP-01")
        self.assertEqual(
            start["vehicleTypeNodeProperties"][0]["theta"],
            0.0,
        )
        self.assertNotIn(
            "theta",
            ignored["vehicleTypeNodeProperties"][0],
        )

    def test_edges_map_direction_speed_and_trajectory(self) -> None:
        result = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )
        edges = result.document["layouts"][0]["edges"]
        edges_by_id = {edge["edgeId"]: edge for edge in edges}

        straight_properties = edges_by_id[
            "E-001"
        ]["vehicleTypeEdgeProperties"][0]
        curve_properties = edges_by_id[
            "E-002"
        ]["vehicleTypeEdgeProperties"][0]

        self.assertEqual(
            straight_properties["vehicleOrientation"],
            0.0,
        )
        self.assertEqual(straight_properties["maxSpeed"], 1.2)
        self.assertEqual(straight_properties["maxRotationSpeed"], 0.4)
        self.assertEqual(
            straight_properties["rotationAtStartNodeAllowed"],
            "NONE",
        )
        self.assertEqual(
            straight_properties["rotationAtEndNodeAllowed"],
            "NONE",
        )
        self.assertNotIn("trajectory", straight_properties)

        self.assertEqual(
            curve_properties["vehicleOrientation"],
            math.pi,
        )
        self.assertEqual(curve_properties["trajectory"]["degree"], 3)
        self.assertEqual(
            curve_properties["trajectory"]["knotVector"],
            [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
        )
        self.assertEqual(
            curve_properties["trajectory"]["controlPoints"],
            [
                {"x": 5.0, "y": 0.0},
                {"x": 6.0, "y": 0.0},
                {"x": 9.0, "y": 5.0},
                {"x": 10.0, "y": 5.0},
            ],
        )
        self.assertEqual(
            curve_properties["rotationAtStartNodeAllowed"],
            "NONE",
        )
        self.assertNotIn(
            "rotationAtEndNodeAllowed",
            curve_properties,
        )

    def test_bin_tasks_become_standard_node_actions(self) -> None:
        result = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )
        nodes = result.document["layouts"][0]["nodes"]
        action_node = next(node for node in nodes if node["nodeId"] == "P-002")
        actions = action_node["vehicleTypeNodeProperties"][0]["actions"]

        self.assertEqual(
            [action["actionType"] for action in actions],
            ["pick", "drop"],
        )
        self.assertEqual(
            actions[0]["actionParameters"],
            [{"key": "height", "value": "0.3"}],
        )
        self.assertEqual(
            actions[1]["actionParameters"],
            [{"key": "height", "value": "0"}],
        )

    def test_action_and_label_points_become_stations(self) -> None:
        result = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )
        stations = result.document["layouts"][0]["stations"]
        stations_by_id = {
            station["stationId"]: station
            for station in stations
        }

        self.assertEqual(set(stations_by_id), {"P-001", "P-002"})
        self.assertEqual(
            stations_by_id["P-001"]["stationName"],
            "Start",
        )
        self.assertEqual(
            stations_by_id["P-002"]["interactionNodeIds"],
            ["P-002"],
        )
        self.assertEqual(
            stations_by_id["P-002"]["stationPosition"],
            {
                "x": 5.5,
                "y": 0.5,
                "theta": math.pi / 2,
            },
        )

    def test_non_topological_data_creates_warnings(self) -> None:
        result = convert_source_map(
            self.source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )

        warnings_by_code = {
            warning.code: warning for warning in result.warnings
        }

        self.assertIn("OCCUPANCY_DATA_SKIPPED", warnings_by_code)
        self.assertIn("FEATURE_LINES_SKIPPED", warnings_by_code)
        self.assertIn("OTHER_AREAS_SKIPPED", warnings_by_code)
        self.assertIn("EXTERNAL_DEVICES_SKIPPED", warnings_by_code)
        self.assertIn("ROTATION_ACCELERATION_SKIPPED", warnings_by_code)
        self.assertIn("UNMAPPED_TASK_PARAMETERS", warnings_by_code)
        self.assertIn("STATION_WITHOUT_ACTIONS", warnings_by_code)
        self.assertEqual(
            warnings_by_code["OTHER_AREAS_SKIPPED"].level,
            WarningLevel.WARNING,
        )

    def test_empty_vehicle_type_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ConversionError,
            "vehicle_type_id must be a non-empty string",
        ):
            convert_source_map(
                self.source_map,
                ConversionOptions(vehicle_type_id="   "),
                exported_at=FIXED_TIMESTAMP,
            )

    def test_unknown_direction_is_rejected(self) -> None:
        data = load_fixture_data()
        curve_items = data["advancedCurveList"]
        self.assertIsInstance(curve_items, list)

        first_curve = curve_items[0]
        self.assertIsInstance(first_curve, dict)

        property_items = first_curve["property"]
        self.assertIsInstance(property_items, list)

        direction = property_items[0]
        self.assertIsInstance(direction, dict)
        direction["int32Value"] = 2

        source_map = parse_source_map(data)

        with self.assertRaisesRegex(
            ConversionError,
            "unsupported direction",
        ):
            convert_source_map(
                source_map,
                self.options,
                exported_at=FIXED_TIMESTAMP,
            )

    def test_unknown_move_style_is_rejected(self) -> None:
        data = load_fixture_data()
        curve_items = data["advancedCurveList"]
        property_items = curve_items[0]["property"]
        move_style = next(
            item
            for item in property_items
            if item["key"] == "movestyle"
        )
        move_style["int32Value"] = 2
        source_map = parse_source_map(data)

        with self.assertRaisesRegex(
            ConversionError,
            "unsupported movestyle",
        ):
            convert_source_map(
                source_map,
                self.options,
                exported_at=FIXED_TIMESTAMP,
            )

    def test_safety_area_creates_critical_warning(self) -> None:
        data = load_fixture_data()
        data["advancedAreaList"][0]["className"] = "SafeSpeedLimitArea"
        source_map = parse_source_map(data)

        result = convert_source_map(
            source_map,
            self.options,
            exported_at=FIXED_TIMESTAMP,
        )

        self.assertTrue(result.has_critical_warnings)
        critical_codes = {
            warning.code
            for warning in result.warnings
            if warning.level is WarningLevel.CRITICAL
        }
        self.assertIn("SAFETY_SPEED_AREAS_SKIPPED", critical_codes)

    def test_convert_file_writes_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "converted.lif.json"

            result = convert_file(
                FIXTURE_PATH,
                output_path,
                self.options,
                exported_at=FIXED_TIMESTAMP,
            )

            saved_document = json.loads(
                output_path.read_text(encoding="utf-8")
            )

            self.assertTrue(output_path.is_file())
            self.assertEqual(saved_document, result.document)


if __name__ == "__main__":
    unittest.main()
