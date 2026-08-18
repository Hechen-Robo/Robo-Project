import pytest

from vda5050_fms.simulator import RobotModel
from vda5050_fms.validation import (
    SchemaRegistry,
    SchemaValidationError,
    UnsupportedProtocolVersion,
)


def test_generated_messages_match_official_schemas(settings) -> None:
    model = RobotModel(settings)
    registry = SchemaRegistry("2.1.0")

    registry.validate("state", model.state_message())
    registry.validate("visualization", model.visualization_message())
    registry.validate("connection", model.connection_message("ONLINE"))
    registry.validate("factsheet", model.factsheet_message())


def test_missing_required_state_field_is_rejected(settings) -> None:
    model = RobotModel(settings)
    state = model.state_message()
    del state["safetyState"]

    with pytest.raises(SchemaValidationError):
        SchemaRegistry("2.1.0").validate("state", state)


def test_unsupported_protocol_version_fails_closed() -> None:
    with pytest.raises(UnsupportedProtocolVersion):
        SchemaRegistry("3.0.0")

