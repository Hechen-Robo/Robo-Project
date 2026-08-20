import unittest
from datetime import datetime

from vda5050_fms.hmi.app import STATIC_DIR, app, health


class HmiAppTests(unittest.TestCase):
    def test_health_response(self) -> None:
        result = health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["service"], "vda5050-fms-hmi")
        self.assertEqual(result["vda5050Version"], "2.1.0")
        self.assertEqual(result["dataSource"], "simulation")

    def test_health_timestamp_is_utc(self) -> None:
        result = health()
        timestamp = result["timestamp"]

        self.assertTrue(timestamp.endswith("Z"))

        parsed_timestamp = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )

        self.assertIsNotNone(parsed_timestamp.tzinfo)

    def test_required_routes_are_registered(self) -> None:
        registered_paths = {
            route.path
            for route in app.routes
        }

        self.assertIn("/", registered_paths)
        self.assertIn("/api/health", registered_paths)
        self.assertIn("/static", registered_paths)

    def test_static_files_exist(self) -> None:
        required_files = [
            "index.html",
            "styles.css",
            "app.js",
        ]

        for filename in required_files:
            with self.subTest(filename=filename):
                self.assertTrue(
                    (STATIC_DIR / filename).is_file()
                )

    def test_index_references_static_assets(self) -> None:
        index_html = (
            STATIC_DIR / "index.html"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '/static/styles.css',
            index_html,
        )
        self.assertIn(
            '/static/app.js',
            index_html,
        )


if __name__ == "__main__":
    unittest.main()