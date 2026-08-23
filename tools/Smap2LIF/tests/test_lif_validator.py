from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from smap2lif.converter import ConversionOptions, convert_source_map
from smap2lif.lif_validator import (
    LifValidationError,
    load_lif_schema,
    validate_lif_document,
)
from smap2lif.source_map import load_source_map


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "minimal_source_map.json"
)


class LifValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        source_map = load_source_map(FIXTURE_PATH)
        result = convert_source_map(
            source_map,
            ConversionOptions(
                vehicle_type_id="AGV.TYPE-01",
                map_id="MAP-01",
            ),
            exported_at=datetime(
                2026,
                8,
                23,
                20,
                0,
                0,
                tzinfo=timezone.utc,
            ),
        )
        self.document = result.document

    def test_bundled_schema_is_available(self) -> None:
        schema = load_lif_schema()

        self.assertEqual(schema["title"], "Layout Interchange Format")
        self.assertEqual(schema["$schema"], "http://json-schema.org/draft-07/schema#")

    def test_generated_document_passes_validation(self) -> None:
        validate_lif_document(self.document)

    def test_missing_required_field_is_rejected(self) -> None:
        document = deepcopy(self.document)
        del document["metaInformation"]["creator"]

        with self.assertRaisesRegex(
            LifValidationError,
            "creator",
        ):
            validate_lif_document(document)

    def test_non_utc_timestamp_is_rejected(self) -> None:
        document = deepcopy(self.document)
        document["metaInformation"]["exportTimestamp"] = (
            "2026-08-23T20:00:00+02:00"
        )

        with self.assertRaisesRegex(
            LifValidationError,
            "ending in 'Z'",
        ):
            validate_lif_document(document)

    def test_duplicate_node_id_is_rejected(self) -> None:
        document = deepcopy(self.document)
        nodes = document["layouts"][0]["nodes"]
        nodes[1]["nodeId"] = nodes[0]["nodeId"]

        with self.assertRaisesRegex(
            LifValidationError,
            "duplicate ID",
        ):
            validate_lif_document(document)

    def test_unknown_edge_reference_is_rejected(self) -> None:
        document = deepcopy(self.document)
        edge = document["layouts"][0]["edges"][0]
        edge["startNodeId"] = "UNKNOWN"

        with self.assertRaisesRegex(
            LifValidationError,
            "references unknown node",
        ):
            validate_lif_document(document)

    def test_invalid_trajectory_knot_count_is_rejected(self) -> None:
        document = deepcopy(self.document)
        edge = document["layouts"][0]["edges"][1]
        trajectory = edge["vehicleTypeEdgeProperties"][0]["trajectory"]
        trajectory["knotVector"].pop()

        with self.assertRaisesRegex(
            LifValidationError,
            "must contain 8 values",
        ):
            validate_lif_document(document)

    def test_negative_speed_is_rejected(self) -> None:
        document = deepcopy(self.document)
        edge_property = document["layouts"][0]["edges"][0][
            "vehicleTypeEdgeProperties"
        ][0]
        edge_property["maxSpeed"] = -1.0

        with self.assertRaisesRegex(
            LifValidationError,
            "must not be negative",
        ):
            validate_lif_document(document)


if __name__ == "__main__":
    unittest.main()
