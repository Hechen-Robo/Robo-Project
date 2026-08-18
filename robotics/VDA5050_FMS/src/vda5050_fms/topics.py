from __future__ import annotations

from dataclasses import dataclass
import re


KNOWN_TOPICS = frozenset(
    {
        "order",
        "instantActions",
        "state",
        "visualization",
        "connection",
        "factsheet",
    }
)

_TOPIC_ELEMENT = re.compile(r"^[^/+#$]+$")


@dataclass(frozen=True, slots=True)
class TopicParts:
    interface_name: str
    major_version: str
    manufacturer: str
    serial_number: str
    topic_name: str


@dataclass(frozen=True, slots=True)
class TopicLayout:
    interface_name: str
    version: str
    manufacturer: str
    serial_number: str

    def __post_init__(self) -> None:
        for name, value in (
            ("interface_name", self.interface_name),
            ("manufacturer", self.manufacturer),
            ("serial_number", self.serial_number),
        ):
            if not value or not _TOPIC_ELEMENT.fullmatch(value):
                raise ValueError(
                    f"{name} contains a character that is not allowed in a VDA topic: "
                    f"{value!r}"
                )

    @property
    def major_version(self) -> str:
        major = self.version.split(".", 1)[0]
        if not major.isdigit():
            raise ValueError(f"Invalid VDA version: {self.version!r}")
        return f"v{major}"

    def robot_topic(self, topic_name: str) -> str:
        self._validate_topic_name(topic_name)
        return "/".join(
            (
                self.interface_name,
                self.major_version,
                self.manufacturer,
                self.serial_number,
                topic_name,
            )
        )

    def wildcard_topic(
        self,
        topic_name: str,
        manufacturer: str = "+",
        serial_number: str = "+",
    ) -> str:
        self._validate_topic_name(topic_name)
        return "/".join(
            (
                self.interface_name,
                self.major_version,
                manufacturer,
                serial_number,
                topic_name,
            )
        )

    def parse(self, topic: str) -> TopicParts:
        parts = topic.split("/")
        if len(parts) != 5:
            raise ValueError(f"Expected five VDA topic levels, got {topic!r}")
        parsed = TopicParts(*parts)
        if parsed.interface_name != self.interface_name:
            raise ValueError(
                f"Unexpected interface {parsed.interface_name!r} in topic {topic!r}"
            )
        if parsed.major_version != self.major_version:
            raise ValueError(
                f"Unexpected major version {parsed.major_version!r} in topic {topic!r}"
            )
        self._validate_topic_name(parsed.topic_name)
        return parsed

    @staticmethod
    def _validate_topic_name(topic_name: str) -> None:
        if topic_name not in KNOWN_TOPICS:
            raise ValueError(f"Unsupported VDA 5050 topic: {topic_name!r}")

