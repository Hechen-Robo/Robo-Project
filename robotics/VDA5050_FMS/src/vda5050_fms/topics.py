from __future__ import annotations

from dataclasses import dataclass
import re

from vda5050_fms.config import Settings


TOPIC_NAMES = (
    "order",
    "instantActions",
    "state",
    "visualization",
    "connection",
    "factsheet",
)

_TOPIC_NAME_SET = frozenset(TOPIC_NAMES)

_TOPIC_LEVEL_PATTERN = re.compile(
    r"^[A-Za-z0-9_.:-]+$"
)

_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)$"
)


def _validate_topic_level(
    field_name: str,
    value: str,
) -> None:
    """Validate one concrete VDA 5050 MQTT topic level."""

    if not value:
        raise ValueError(f"{field_name} must not be empty")

    if not _TOPIC_LEVEL_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} may only contain "
            "A-Z, a-z, 0-9, underscore, hyphen, dot and colon"
        )


@dataclass(frozen=True, slots=True)
class TopicLayout:
    """Generate topics for one VDA 5050 robot."""

    interface_name: str
    version: str
    manufacturer: str
    serial_number: str

    def __post_init__(self) -> None:
        _validate_topic_level(
            "interface_name",
            self.interface_name,
        )
        _validate_topic_level(
            "manufacturer",
            self.manufacturer,
        )
        _validate_topic_level(
            "serial_number",
            self.serial_number,
        )

        if not _VERSION_PATTERN.fullmatch(self.version):
            raise ValueError(
                "version must use Major.Minor.Patch format"
            )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
    ) -> TopicLayout:
        """Create a topic layout from application settings."""

        return cls(
            interface_name=settings.vda_interface_name,
            version=settings.vda_version,
            manufacturer=settings.vda_manufacturer,
            serial_number=settings.vda_serial_number,
        )

    @property
    def major_version(self) -> str:
        """Return the VDA topic major version, for example v2."""

        match = _VERSION_PATTERN.fullmatch(self.version)

        if match is None:
            raise ValueError(
                "version must use Major.Minor.Patch format"
            )

        return f"v{match.group('major')}"

    @property
    def prefix(self) -> str:
        """Return the robot-specific topic prefix."""

        return "/".join(
            (
                self.interface_name,
                self.major_version,
                self.manufacturer,
                self.serial_number,
            )
        )

    def build(self, topic_name: str) -> str:
        """Build one complete VDA 5050 MQTT topic."""

        if topic_name not in _TOPIC_NAME_SET:
            raise ValueError(
                f"Unsupported VDA 5050 topic: {topic_name!r}"
            )

        return f"{self.prefix}/{topic_name}"

    def all_topics(self) -> dict[str, str]:
        """Return all supported topics for this robot."""

        return {
            topic_name: self.build(topic_name)
            for topic_name in TOPIC_NAMES
        }