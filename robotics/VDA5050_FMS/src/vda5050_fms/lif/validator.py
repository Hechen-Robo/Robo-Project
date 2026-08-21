from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError


SUPPORTED_LIF_VERSION = "1.0.0"


class LifValidationError(ValueError):
    """Raised when imported LIF data is invalid."""


def _format_json_path(parts: object) -> str:
    path = "$"

    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"

    return path


@lru_cache(maxsize=1)
def _get_validator() -> Draft7Validator:
    try:
        schema_text = (
            files("vda5050_fms.lif.schemas")
            .joinpath("LIF.schema")
            .read_text(encoding="utf-8")
        )
        schema = json.loads(schema_text)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Bundled LIF schema could not be loaded"
        ) from exc

    if not isinstance(schema, dict):
        raise RuntimeError(
            "Bundled LIF schema must be a JSON object"
        )

    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as exc:
        raise RuntimeError(
            "Bundled LIF schema is invalid"
        ) from exc

    return Draft7Validator(schema)


def validate_lif_mapping(
    payload: Mapping[str, object],
) -> None:
    """Validate an already decoded LIF document."""

    errors = sorted(
        _get_validator().iter_errors(payload),
        key=lambda error: tuple(
            str(part) for part in error.absolute_path
        ),
    )

    if errors:
        first_error = errors[0]
        path = _format_json_path(
            first_error.absolute_path
        )
        raise LifValidationError(
            f"Invalid LIF at {path}: "
            f"{first_error.message}"
        )

    meta_information = payload["metaInformation"]
    assert isinstance(meta_information, Mapping)

    lif_version = meta_information["lifVersion"]

    if lif_version != SUPPORTED_LIF_VERSION:
        raise LifValidationError(
            "Unsupported LIF version: "
            f"{lif_version!r}; expected "
            f"{SUPPORTED_LIF_VERSION!r}"
        )

    layouts = payload["layouts"]
    assert isinstance(layouts, list)

    if not layouts:
        raise LifValidationError(
            "Invalid LIF at $.layouts: "
            "at least one layout is required"
        )


def _reject_non_standard_number(value: str) -> None:
    raise ValueError(
        f"Non-standard JSON number is not allowed: {value}"
    )


def load_lif_json(
    payload: str | bytes | bytearray,
) -> dict[str, object]:
    """Decode and validate a LIF JSON document."""

    try:
        decoded = json.loads(
            payload,
            parse_constant=_reject_non_standard_number,
        )
    except (ValueError, TypeError) as exc:
        raise LifValidationError(
            "LIF payload is not valid JSON"
        ) from exc

    if not isinstance(decoded, dict):
        raise LifValidationError(
            "LIF payload must be a JSON object"
        )

    validate_lif_mapping(decoded)
    return decoded