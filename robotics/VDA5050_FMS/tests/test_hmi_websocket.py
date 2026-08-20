import asyncio
import unittest
from typing import Any, cast

from fastapi import (
    WebSocket,
    WebSocketDisconnect,
    status,
)

from vda5050_fms.hmi.app import (
    robot_snapshot_websocket,
)


class DisconnectAfterFirstMessageWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent_messages: list[dict[str, Any]] = []
        self.close_code: int | None = None
        self.close_reason: str | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(
        self,
        data: dict[str, Any],
    ) -> None:
        self.sent_messages.append(data)

        raise WebSocketDisconnect(code=1000)

    async def close(
        self,
        code: int = 1000,
        reason: str | None = None,
    ) -> None:
        self.close_code = code
        self.close_reason = reason


class HmiWebSocketTests(unittest.TestCase):
    def test_known_robot_receives_snapshot(
        self,
    ) -> None:
        fake_websocket = (
            DisconnectAfterFirstMessageWebSocket()
        )

        asyncio.run(
            robot_snapshot_websocket(
                websocket=cast(
                    WebSocket,
                    fake_websocket,
                ),
                manufacturer="TEST",
                serial_number="AGV-001",
            )
        )

        self.assertTrue(
            fake_websocket.accepted
        )
        self.assertEqual(
            len(fake_websocket.sent_messages),
            1,
        )

        snapshot = (
            fake_websocket.sent_messages[0]
        )

        self.assertEqual(
            snapshot["manufacturer"],
            "TEST",
        )
        self.assertEqual(
            snapshot["serialNumber"],
            "AGV-001",
        )

    def test_unknown_robot_is_closed(
        self,
    ) -> None:
        fake_websocket = (
            DisconnectAfterFirstMessageWebSocket()
        )

        asyncio.run(
            robot_snapshot_websocket(
                websocket=cast(
                    WebSocket,
                    fake_websocket,
                ),
                manufacturer="UNKNOWN",
                serial_number="AGV-001",
            )
        )

        self.assertTrue(
            fake_websocket.accepted
        )
        self.assertEqual(
            fake_websocket.close_code,
            status.WS_1008_POLICY_VIOLATION,
        )
        self.assertEqual(
            fake_websocket.close_reason,
            "Robot was not found.",
        )
        self.assertEqual(
            fake_websocket.sent_messages,
            [],
        )


if __name__ == "__main__":
    unittest.main()