from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_FILES = {
    "connection": "connection.schema",
    "factsheet": "factsheet.schema",
    "instantActions": "instantActions.schema",
    "order": "order.schema",
    "state": "state.schema",
    "visualization": "visualization.schema",
}


class UnsupportedProtocolVersion(ValueError):
    pass


class SchemaValidationError(ValueError):
    def __init__(self, topic_name: str, errors: list[str]) -> None:
        self.topic_name = topic_name
        self.errors = errors
        super().__init__(f"Invalid {topic_name} message: {'; '.join(errors)}")


class SchemaRegistry:
    """Loads immutable official VDA 5050 schemas bundled with this package."""

    def __init__(self, version: str = "2.1.0") -> None:
        if version != "2.1.0":
            raise UnsupportedProtocolVersion(
                "Stage 1 supports VDA 5050 2.1.0 only. "
                f"Configured version was {version!r}."
            )
        self.version = version

    @lru_cache(maxsize=None)
    def validator(self, topic_name: str) -> Draft202012Validator:
        try:
            schema_file = SCHEMA_FILES[topic_name]
        except KeyError as exc:
            raise ValueError(f"No schema registered for topic {topic_name!r}") from exc

        resource = files("vda5050_fms").joinpath(
            "schemas", "v2_1", schema_file
        )
        schema = json.loads(resource.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, topic_name: str, payload: Mapping[str, Any]) -> None:
        validator = self.validator(topic_name)
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda error: "/".join(str(part) for part in error.absolute_path),
        )
        if not errors:
            return

        descriptions: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "." + ".".join(
                    str(part) for part in error.absolute_path
                )
            descriptions.append(f"{location}: {error.message}")
        if len(errors) > 10:
            descriptions.append(f"... and {len(errors) - 10} more errors")
        raise SchemaValidationError(topic_name, descriptions)

