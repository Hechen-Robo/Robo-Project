import asyncio
from io import BytesIO
from pathlib import Path
import unittest

from fastapi import HTTPException, UploadFile

from vda5050_fms.hmi.app import (
    get_lif_map,
    import_lif_map,
    list_lif_maps,
)
from vda5050_fms.hmi.map_store import (
    lif_map_store,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "minimal_valid_lif.json"
)


class HmiLifApiTests(unittest.TestCase):
    def setUp(self) -> None:
        lif_map_store.clear()
        self.valid_payload = FIXTURE_PATH.read_bytes()

    def tearDown(self) -> None:
        lif_map_store.clear()

    def _upload(
        self,
        content: bytes,
        filename: str = "warehouse.lif",
    ) -> dict[str, object]:
        upload = UploadFile(
            file=BytesIO(content),
            filename=filename,
        )

        return asyncio.run(import_lif_map(upload))

    def test_valid_lif_can_be_imported(self) -> None:
        result = self._upload(self.valid_payload)

        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["lifVersion"], "1.0.0")
        self.assertEqual(result["layoutCount"], 1)

    def test_imported_layout_is_listed(self) -> None:
        self._upload(self.valid_payload)

        result = list_lif_maps()

        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["layouts"][0]["layoutId"],
            "warehouse-floor-1",
        )

    def test_layout_detail_contains_graph(
        self,
    ) -> None:
        self._upload(self.valid_payload)

        result = get_lif_map(
            "warehouse-floor-1"
        )

        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(len(result["stations"]), 1)
        self.assertEqual(
            result["bounds"]["maxX"],
            5.0,
        )

    def test_invalid_lif_returns_422(self) -> None:
        with self.assertRaises(
            HTTPException
        ) as context:
            self._upload(b"{}")

        self.assertEqual(
            context.exception.status_code,
            422,
        )

    def test_wrong_extension_returns_400(
        self,
    ) -> None:
        with self.assertRaises(
            HTTPException
        ) as context:
            self._upload(
                self.valid_payload,
                filename="warehouse.txt",
            )

        self.assertEqual(
            context.exception.status_code,
            400,
        )

    def test_unknown_layout_returns_404(
        self,
    ) -> None:
        with self.assertRaises(
            HTTPException
        ) as context:
            get_lif_map("UNKNOWN")

        self.assertEqual(
            context.exception.status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()