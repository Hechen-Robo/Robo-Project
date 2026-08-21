from copy import deepcopy
import json
from pathlib import Path
import unittest

from vda5050_fms.lif import (
    LifValidationError,
    load_lif_json,
    validate_lif_mapping,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "minimal_valid_lif.json"
)


class LifValidatorTests(unittest.TestCase):
    """Tests for LIF 1.0.0 JSON validation."""

    def setUp(self) -> None:
        self.payload = json.loads(
            FIXTURE_PATH.read_text(encoding="utf-8")
        )

    def test_valid_lif_file_is_accepted(self) -> None:
        document = load_lif_json(
            FIXTURE_PATH.read_text(encoding="utf-8")
        )

        self.assertEqual(
            document["metaInformation"]["lifVersion"],
            "1.0.0",
        )
        self.assertEqual(
            document["layouts"][0]["layoutId"],
            "warehouse-floor-1",
        )

    def test_invalid_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            LifValidationError,
            "not valid JSON",
        ):
            load_lif_json("{")

    def test_missing_layouts_is_rejected(self) -> None:
        payload = deepcopy(self.payload)
        del payload["layouts"]

        with self.assertRaisesRegex(
            LifValidationError,
            "layouts",
        ):
            validate_lif_mapping(payload)

    def test_invalid_node_coordinate_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        payload["layouts"][0]["nodes"][0][
            "nodePosition"
        ]["x"] = "invalid"

        with self.assertRaisesRegex(
            LifValidationError,
            "nodePosition.x",
        ):
            validate_lif_mapping(payload)

    def test_unsupported_version_is_rejected(
        self,
    ) -> None:
        payload = deepcopy(self.payload)
        payload["metaInformation"]["lifVersion"] = (
            "2.0.0"
        )

        with self.assertRaisesRegex(
            LifValidationError,
            "Unsupported LIF version",
        ):
            validate_lif_mapping(payload)


if __name__ == "__main__":
    unittest.main()