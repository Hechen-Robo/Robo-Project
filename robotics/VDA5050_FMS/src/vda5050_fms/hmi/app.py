import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .simulation import (
    MANUFACTURER,
    SERIAL_NUMBER,
    get_simulated_robot_snapshot,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"

WEBSOCKET_UPDATE_INTERVAL_SECONDS = 0.5


app = FastAPI(
    title="VDA 5050 Robot HMI",
    description="Read-only HMI for VDA 5050 robot monitoring.",
    version="0.1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


def is_known_robot(
    manufacturer: str,
    serial_number: str,
) -> bool:
    return (
        manufacturer == MANUFACTURER
        and serial_number == SERIAL_NUMBER
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    timestamp = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

    return {
        "status": "ok",
        "service": "vda5050-fms-hmi",
        "vda5050Version": "2.1.0",
        "dataSource": "simulation",
        "timestamp": timestamp,
    }


@app.get(
    "/api/robots/{manufacturer}/{serial_number}/snapshot"
)
def robot_snapshot(
    manufacturer: str,
    serial_number: str,
) -> dict[str, object]:
    if not is_known_robot(
        manufacturer,
        serial_number,
    ):
        raise HTTPException(
            status_code=404,
            detail="Robot was not found.",
        )

    return get_simulated_robot_snapshot()


@app.websocket(
    "/ws/robots/{manufacturer}/{serial_number}/snapshot"
)
async def robot_snapshot_websocket(
    websocket: WebSocket,
    manufacturer: str,
    serial_number: str,
) -> None:
    await websocket.accept()

    if not is_known_robot(
        manufacturer,
        serial_number,
    ):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Robot was not found.",
        )
        return

    try:
        while True:
            snapshot = get_simulated_robot_snapshot()

            await websocket.send_json(snapshot)

            await asyncio.sleep(
                WEBSOCKET_UPDATE_INTERVAL_SECONDS
            )
    except WebSocketDisconnect:
        return


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")