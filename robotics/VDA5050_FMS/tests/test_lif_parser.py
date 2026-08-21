from copy import deepcopy
import json
from pathlib import Path
import unittest

from vda5050_fms.lif import (
    LifValidationError,
    parse_lif_file,
    parse_lif_mapping,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "minimal_valid_lif.json"
)


class LifParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(
            FIXTURE_PATH.read_text(encoding="utf-8")
        )

    def test_valid_file_is_converted_to_models(
        self,
    ) -> None:
        document = parse_lif_file(FIXTURE_PATH)
        layout = document.layout_by_id(
            "warehouse-floor-1"
        )

        self.assertEqual(
            document.meta_information.lif_version,
            "1.0.0",
        )
        self.assertEqual(len(layout.nodes), 2)
        self.assertEqual(len(layout.edges), 1)
        self.assertEqual(len(layout.stations), 1)
        self.assertEqual(
            layout.node_by_id("N2").position.x,
            5.0,
        )
        self.assertEqual(
            layout.map_ids,
            frozenset({"warehouse-map"}),
        )
        self.assertEqual(layout.bounds.min_x, 0.0)
        self.assertEqual(layout.bounds.max_x, 5.0)

    def test_duplicate_layout_id_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        payload["layouts"].append(
            deepcopy(payload["layouts"][0])
        )

        with self.assertRaisesRegex(
            LifValidationError,
            "Duplicate layoutId",
        ):
            parse_lif_mapping(payload)

    def test_duplicate_node_id_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        second_layout = deepcopy(
            payload["layouts"][0]
        )
        second_layout["layoutId"] = (
            "warehouse-floor-2"
        )
        payload["layouts"].append(second_layout)

        with self.assertRaisesRegex(
            LifValidationError,
            "Duplicate nodeId",
        ):
            parse_lif_mapping(payload)

    def test_unknown_edge_start_node_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        payload["layouts"][0]["edges"][0][
            "startNodeId"
        ] = "UNKNOWN"

        with self.assertRaisesRegex(
            LifValidationError,
            "startNodeId UNKNOWN",
        ):
            parse_lif_mapping(payload)

    def test_unknown_edge_end_node_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        payload["layouts"][0]["edges"][0][
            "endNodeId"
        ] = "UNKNOWN"

        with self.assertRaisesRegex(
            LifValidationError,
            "endNodeId UNKNOWN",
        ):
            parse_lif_mapping(payload)

    def test_unknown_station_node_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        payload["layouts"][0]["stations"][0][
            "interactionNodeIds"
        ] = ["UNKNOWN"]

        with self.assertRaisesRegex(
            LifValidationError,
            "unknown nodeId",
        ):
            parse_lif_mapping(payload)


if __name__ == "__main__":
    unittest.main()