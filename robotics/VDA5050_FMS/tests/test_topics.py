import pytest

from vda5050_fms.topics import TopicLayout


def test_vda_21_topic_layout() -> None:
    layout = TopicLayout("uagv", "2.1.0", "SEER", "AGV-001")

    assert layout.robot_topic("state") == "uagv/v2/SEER/AGV-001/state"
    assert layout.wildcard_topic("connection") == "uagv/v2/+/+/connection"
    parsed = layout.parse("uagv/v2/SEER/AGV-001/order")
    assert parsed.manufacturer == "SEER"
    assert parsed.serial_number == "AGV-001"
    assert parsed.topic_name == "order"


def test_topic_element_rejects_mqtt_wildcards() -> None:
    with pytest.raises(ValueError):
        TopicLayout("uagv", "2.1.0", "BAD+NAME", "001")


def test_unknown_topic_is_rejected() -> None:
    layout = TopicLayout("uagv", "2.1.0", "SEER", "001")
    with pytest.raises(ValueError):
        layout.robot_topic("unknown")

