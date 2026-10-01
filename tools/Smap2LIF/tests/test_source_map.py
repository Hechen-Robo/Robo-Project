from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from smap2lif.source_map import (
    SourceMapLoadError,
    SourceMapValidationError,
    load_source_map,
    parse_source_map,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "minimal_source_map.json"
)


def load_fixture_data() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class SourceMapTests(unittest.TestCase):
    def test_valid_file_is_loaded(self) -> None:
        source_map = load_source_map(FIXTURE_PATH)

        self.assertEqual(source_map.map_name, "minimal-source-map")
        self.assertEqual(source_map.map_type, "2D-Map")
        self.assertEqual(source_map.source_version, "1.0.0")
        self.assertEqual(source_map.resolution, 0.05)
        self.assertEqual(source_map.counts.points, 3)
        self.assertEqual(source_map.counts.curves, 2)
        self.assertEqual(source_map.counts.normal_positions, 1)
        self.assertEqual(source_map.counts.lines, 1)
        self.assertEqual(source_map.counts.areas, 1)
        self.assertEqual(source_map.counts.external_devices, 1)
        self.assertEqual(source_map.counts.bin_locations, 1)
        self.assertEqual(source_map.counts.bin_tasks, 2)
        self.assertEqual(source_map.line_classes, ("FeatureLine",))
        self.assertEqual(source_map.area_classes, ("FeatureArea",))
        self.assertEqual(source_map.external_device_classes, ("Image",))

    def test_typed_properties_are_decoded(self) -> None:
        source_map = load_source_map(FIXTURE_PATH)

        start = source_map.point_by_id("P-001")
        straight_path = source_map.curves[0]

        self.assertEqual(start.property_value("label"), "Start")
        self.assertIs(start.property_value("spin"), False)
        self.assertEqual(straight_path.property_value("direction"), 0)
        self.assertEqual(straight_path.property_value("maxspeed"), 1.2)
        self.assertIsNone(start.property_value("missing"))

    def test_bin_locations_and_tasks_are_decoded(self) -> None:
        source_map = load_source_map(FIXTURE_PATH)

        locations = source_map.bin_locations_for_point("P-002")

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].location_id, "B-001")
        self.assertEqual(locations[0].position.x, 5.5)
        self.assertEqual(
            [task.task_type for task in locations[0].tasks],
            ["LOAD", "UNLOAD"],
        )
        self.assertEqual(
            locations[0].tasks[0].parameter_value("end_height"),
            0.3,
        )

    def test_curve_geometry_is_preserved(self) -> None:
        source_map = load_source_map(FIXTURE_PATH)
        curve = source_map.curves[1]

        self.assertEqual(curve.start.point_id, "P-002")
        self.assertEqual(curve.end.point_id, "P-003")
        self.assertIsNotNone(curve.control_point_1)
        self.assertIsNotNone(curve.control_point_2)
        self.assertEqual(curve.control_point_1.x, 6.0)
        self.assertEqual(curve.control_point_2.y, 5.0)

    def test_duplicate_point_id_is_rejected(self) -> None:
        data = load_fixture_data()
        points = data["advancedPointList"]
        points[1]["instanceName"] = points[0]["instanceName"]

        with self.assertRaisesRegex(
            SourceMapValidationError, "duplicate instanceName"
        ):
            parse_source_map(data)

    def test_unknown_curve_endpoint_is_rejected(self) -> None:
        data = load_fixture_data()
        curves = data["advancedCurveList"]
        curves[0]["endPos"]["instanceName"] = "P-999"

        with self.assertRaisesRegex(
            SourceMapValidationError, "references unknown point"
        ):
            parse_source_map(data)

    def test_curve_endpoint_position_mismatch_is_rejected(self) -> None:
        data = load_fixture_data()
        curves = data["advancedCurveList"]
        curves[0]["startPos"]["pos"]["x"] = 99.0

        with self.assertRaisesRegex(
            SourceMapValidationError,
            "does not match point",
        ):
            parse_source_map(data)

    def test_missing_curve_control_point_is_rejected(self) -> None:
        data = load_fixture_data()
        curve = data["advancedCurveList"][1]
        del curve["controlPos1"]

        with self.assertRaisesRegex(
            SourceMapValidationError, "controlPos1"
        ):
            parse_source_map(data)

    def test_invalid_typed_property_is_rejected(self) -> None:
        data = load_fixture_data()
        point = data["advancedPointList"][0]
        point["property"][1]["boolValue"] = "false"

        with self.assertRaisesRegex(
            SourceMapValidationError, "boolValue must be a boolean"
        ):
            parse_source_map(data)

    def test_unknown_bin_location_point_is_rejected(self) -> None:
        data = load_fixture_data()
        groups = data["binLocationsList"]
        groups[0]["binLocationList"][0]["pointName"] = "P-999"

        with self.assertRaisesRegex(
            SourceMapValidationError,
            "references unknown point",
        ):
            parse_source_map(data)

    def test_invalid_bin_task_json_is_rejected(self) -> None:
        data = load_fixture_data()
        groups = data["binLocationsList"]
        properties = groups[0]["binLocationList"][0]["property"]
        properties[0]["stringValue"] = "{invalid"

        with self.assertRaisesRegex(
            SourceMapValidationError,
            "binTask contains invalid JSON",
        ):
            parse_source_map(data)

    def test_invalid_json_is_reported_as_load_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid_file = Path(directory) / "invalid.json"
            invalid_file.write_text("{invalid", encoding="utf-8")

            with self.assertRaisesRegex(
                SourceMapLoadError, "Invalid JSON"
            ):
                load_source_map(invalid_file)

    def test_lif_document_is_rejected_with_clear_message(self) -> None:
        lif_document = {
            "metaInformation": {
                "lifVersion": "1.0.0",
            },
            "layouts": [],
        }

        with self.assertRaisesRegex(
            SourceMapValidationError,
            "already a LIF document",
        ):
            parse_source_map(lif_document)


if __name__ == "__main__":
    unittest.main()
