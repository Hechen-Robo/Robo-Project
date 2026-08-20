import unittest
from typing import Any, cast
from unittest.mock import patch

from vda5050_fms.hmi.simulation import (
    MANUFACTURER,
    SERIAL_NUMBER,
    SIMULATION_START,
    get_simulated_robot_snapshot,
)


class HmiSimulationTests(unittest.TestCase):
    def get_snapshot(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            get_simulated_robot_snapshot(),
        )

    def test_snapshot_contains_three_vda_messages(
        self,
    ) -> None:
        snapshot = self.get_snapshot()

        self.assertIn("connection", snapshot)
        self.assertIn("state", snapshot)
        self.assertIn("visualization", snapshot)

        for topic_name in (
            "connection",
            "state",
            "visualization",
        ):
            with self.subTest(topic=topic_name):
                message = snapshot[topic_name]

                self.assertEqual(
                    message["version"],
                    "2.1.0",
                )
                self.assertEqual(
                    message["manufacturer"],
                    MANUFACTURER,
                )
                self.assertEqual(
                    message["serialNumber"],
                    SERIAL_NUMBER,
                )
                self.assertTrue(
                    message["timestamp"].endswith("Z")
                )

    def test_state_contains_required_vda_fields(
        self,
    ) -> None:
        state = self.get_snapshot()["state"]

        required_fields = {
            "headerId",
            "timestamp",
            "version",
            "manufacturer",
            "serialNumber",
            "orderId",
            "orderUpdateId",
            "lastNodeId",
            "lastNodeSequenceId",
            "nodeStates",
            "edgeStates",
            "driving",
            "actionStates",
            "batteryState",
            "operatingMode",
            "errors",
            "safetyState",
        }

        self.assertTrue(
            required_fields.issubset(state)
        )
        self.assertEqual(
            state["operatingMode"],
            "AUTOMATIC",
        )
        self.assertEqual(
            state["safetyState"]["eStop"],
            "NONE",
        )

    def test_visualization_contains_valid_position(
        self,
    ) -> None:
        visualization = self.get_snapshot()[
            "visualization"
        ]
        position = visualization["agvPosition"]

        self.assertEqual(
            position["mapId"],
            "WAREHOUSE_A",
        )
        self.assertTrue(
            position["positionInitialized"]
        )
        self.assertGreaterEqual(
            position["localizationScore"],
            0.0,
        )
        self.assertLessEqual(
            position["localizationScore"],
            1.0,
        )

    def test_simulated_position_changes_over_time(
        self,
    ) -> None:
        monotonic_path = (
            "vda5050_fms.hmi.simulation.monotonic"
        )

        with patch(
            monotonic_path,
            return_value=SIMULATION_START,
        ):
            first_snapshot = self.get_snapshot()

        with patch(
            monotonic_path,
            return_value=SIMULATION_START + 2.0,
        ):
            second_snapshot = self.get_snapshot()

        first_position = first_snapshot[
            "visualization"
        ]["agvPosition"]

        second_position = second_snapshot[
            "visualization"
        ]["agvPosition"]

        self.assertNotEqual(
            first_position,
            second_position,
        )


if __name__ == "__main__":
    unittest.main()