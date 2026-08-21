import unittest
from datetime import datetime

from fastapi import HTTPException

from vda5050_fms.hmi.app import (
    STATIC_DIR,
    app,
    health,
    robot_snapshot,
)


class HmiAppTests(unittest.TestCase):
    def test_health_response(self) -> None:
        result = health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["service"],
            "vda5050-fms-hmi",
        )
        self.assertEqual(
            result["vda5050Version"],
            "2.1.0",
        )
        self.assertEqual(
            result["dataSource"],
            "simulation",
        )

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
        self.assertIn("/api/maps", registered_paths)
        self.assertIn("/api/maps/lif", registered_paths)
        self.assertIn(
            "/api/maps/{layout_id}",
            registered_paths,
        )

        self.assertIn("/", registered_paths)
        self.assertIn("/api/health", registered_paths)
        self.assertIn("/static", registered_paths)
        self.assertIn(
            (
                "/api/robots/{manufacturer}/"
                "{serial_number}/snapshot"
            ),
            registered_paths,
        )
        self.assertIn(
            (
                "/ws/robots/{manufacturer}/"
                "{serial_number}/snapshot"
            ),
            registered_paths,
        )

    def test_known_robot_returns_snapshot(self) -> None:
        result = robot_snapshot(
            manufacturer="TEST",
            serial_number="AGV-001",
        )

        self.assertEqual(
            result["manufacturer"],
            "TEST",
        )
        self.assertEqual(
            result["serialNumber"],
            "AGV-001",
        )

    def test_unknown_robot_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as context:
            robot_snapshot(
                manufacturer="UNKNOWN",
                serial_number="AGV-001",
            )

        self.assertEqual(
            context.exception.status_code,
            404,
        )
        self.assertEqual(
            context.exception.detail,
            "Robot was not found.",
        )

    def test_static_files_exist(self) -> None:
        required_files = [
            "index.html",
            "styles.css",
            "app.js",
            "lif-map.js",
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
            "/static/styles.css",
            index_html,
        )
        self.assertIn(
            "/static/app.js",
            index_html,
        )
        self.assertIn(
            "/static/lif-map.js",
            index_html,
        )

    def test_javascript_imports_and_renders_lif(
        self,
    ) -> None:
        lif_javascript = (
            STATIC_DIR / "lif-map.js"
        ).read_text(encoding="utf-8")

        required_fragments = [
            "/api/maps/lif",
            "/api/maps",
            "FormData",
            "renderLifLayout",
            "lifMapController",
            "acceptsRobotMapId",
            "createElementNS",
        ]

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(
                    fragment,
                    lif_javascript,
                )

    def test_index_contains_dashboard_elements(
        self,
        ) -> None:
        index_html = (
            STATIC_DIR / "index.html"
        ).read_text(encoding="utf-8")

        required_element_ids = [
            "warehouse-map",
            "map-layout-name",
            "map-layout-meta",
            "lif-file-input",
            "lif-import-button",
            "lif-layout-select",
            "lif-import-status",
            "lif-map-layer",
            "robot-marker",
            "robot-label",
            "live-badge",
            "stream-status",
            "connection-state",
            "operating-mode",
            "driving-state",
            "position-x",
            "position-y",
            "position-theta",
            "velocity-x",
            "battery-charge",
            "order-id",
            "last-node",
            "localization-score",
            "error-count",

        ]

        for element_id in required_element_ids:
            with self.subTest(element_id=element_id):
                self.assertIn(
                    f'id="{element_id}"',
                    index_html,
                )

    def test_javascript_connects_websocket(
        self,
    ) -> None:
        app_javascript = (
            STATIC_DIR / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "/ws/robots/",
            app_javascript,
        )
        self.assertIn(
            "new WebSocket",
            app_javascript,
        )
        self.assertIn(
            "connectRobotWebSocket",
            app_javascript,
        )
        self.assertIn(
            "scheduleWebSocketReconnect",
            app_javascript,
        )
        self.assertIn(
            "animateRobotTo",
            app_javascript,
        )



if __name__ == "__main__":
    unittest.main()