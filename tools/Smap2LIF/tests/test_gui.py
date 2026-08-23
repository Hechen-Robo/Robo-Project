from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from smap2lif.converter import (
    ConversionOptions,
    convert_source_map,
)
from smap2lif.gui import (
    build_conversion_options,
    format_conversion_report,
    format_source_summary,
    suggested_output_path,
)
from smap2lif.source_map import load_source_map


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "minimal_source_map.json"

FIXED_TIMESTAMP = datetime(
    2026,
    8,
    23,
    19,
    0,
    0,
    tzinfo=timezone.utc,
)


class GuiHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_map = load_source_map(FIXTURE_PATH)

    def test_suggested_output_path_uses_input_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "factory-map.json"

            output_path = suggested_output_path(input_path)

            self.assertEqual(output_path.parent, input_path.parent)
            self.assertEqual(
                output_path.name,
                "factory-map_LIF_1.0.0.json",
            )

    def test_source_summary_contains_map_counts(self) -> None:
        summary = format_source_summary(self.source_map)

        self.assertIn("Map name: minimal-source-map", summary)
        self.assertIn("Topological points: 3", summary)
        self.assertIn("Topological curves: 2", summary)
        self.assertIn("Occupancy positions: 1", summary)
        self.assertIn("Non-topological lines: 1", summary)
        self.assertIn("Non-topological areas: 1", summary)
        self.assertIn("External devices: 1", summary)
        self.assertIn("Bin locations: 1", summary)
        self.assertIn("Source station tasks: 2", summary)

    def test_gui_fields_build_conversion_options(self) -> None:
        options = build_conversion_options(
            vehicle_type_id="  AGV.TYPE-01  ",
            creator="  Smap2LIF  ",
            project_identification="   ",
            layout_name="  Main Floor  ",
            layout_version="  7  ",
            map_id="  MAP-01  ",
            include_stations=True,
            rotation_allowed=False,
        )

        self.assertEqual(options.vehicle_type_id, "AGV.TYPE-01")
        self.assertEqual(options.creator, "Smap2LIF")
        self.assertIsNone(options.project_identification)
        self.assertEqual(options.layout_name, "Main Floor")
        self.assertEqual(options.layout_version, "7")
        self.assertEqual(options.map_id, "MAP-01")
        self.assertTrue(options.include_stations)
        self.assertFalse(options.rotation_allowed)

    def test_conversion_report_contains_result_and_warnings(self) -> None:
        result = convert_source_map(
            self.source_map,
            ConversionOptions(vehicle_type_id="AGV.TYPE-01"),
            exported_at=FIXED_TIMESTAMP,
        )

        report = format_conversion_report(
            result,
            Path("output") / "converted.json",
        )

        self.assertIn("Conversion completed successfully.", report)
        self.assertIn("Nodes: 3", report)
        self.assertIn("Edges: 2", report)
        self.assertIn("Stations: 2", report)
        self.assertIn("Trajectories: 1", report)
        self.assertIn("Node actions: 2", report)
        self.assertIn("Official LIF schema validation: PASSED", report)
        self.assertIn("Warnings:", report)


if __name__ == "__main__":
    unittest.main()
