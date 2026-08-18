import unittest

from vda5050_fms.topics import (
    TOPIC_NAMES,
    TopicLayout,
)


class TopicLayoutTests(unittest.TestCase):
    """Tests for VDA 5050 MQTT topic generation."""

    def setUp(self) -> None:
        self.layout = TopicLayout(
            interface_name="uagv",
            version="2.1.0",
            manufacturer="TEST",
            serial_number="AGV-001",
        )

    def test_major_version_uses_only_v2(self) -> None:
        self.assertEqual(
            self.layout.major_version,
            "v2",
        )

    def test_state_topic(self) -> None:
        self.assertEqual(
            self.layout.build("state"),
            "uagv/v2/TEST/AGV-001/state",
        )

    def test_instant_actions_preserves_case(self) -> None:
        self.assertEqual(
            self.layout.build("instantActions"),
            "uagv/v2/TEST/AGV-001/instantActions",
        )

    def test_all_six_topics_are_generated(self) -> None:
        topics = self.layout.all_topics()

        self.assertEqual(
            tuple(topics),
            TOPIC_NAMES,
        )
        self.assertEqual(
            len(topics),
            6,
        )

    def test_unknown_topic_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported VDA 5050 topic",
        ):
            self.layout.build("unknown")

    def test_slash_in_manufacturer_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "manufacturer",
        ):
            TopicLayout(
                interface_name="uagv",
                version="2.1.0",
                manufacturer="BAD/NAME",
                serial_number="AGV-001",
            )

    def test_incomplete_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Major.Minor.Patch",
        ):
            TopicLayout(
                interface_name="uagv",
                version="2.1",
                manufacturer="TEST",
                serial_number="AGV-001",
            )


if __name__ == "__main__":
    unittest.main()