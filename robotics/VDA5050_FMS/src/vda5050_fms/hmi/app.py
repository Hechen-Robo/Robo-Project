import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from vda5050_fms.lif import (
    LifValidationError,
    parse_lif_json,
)

from .map_store import (
    lif_layout_summary,
    lif_layout_to_mapping,
    lif_map_store,
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .simulation import (
    MANUFACTURER,
    SERIAL_NUMBER,
    get_simulated_robot_snapshot,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_LIF_UPLOAD_BYTES = 5 * 1024 * 1024
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



@app.post(
    "/api/maps/lif",
    status_code=201,
)
async def import_lif_map(
    file: UploadFile = File(...),
) -> dict[str, object]:
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()

    try:
        if suffix not in {".lif", ".json"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "LIF file must use a .lif "
                    "or .json extension."
                ),
            )

        content = await file.read(
            MAX_LIF_UPLOAD_BYTES + 1
        )
    finally:
        await file.close()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="LIF file is empty.",
        )

    if len(content) > MAX_LIF_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="LIF file exceeds the 5 MB limit.",
        )

    try:
        document = parse_lif_json(content)
    except LifValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    lif_map_store.replace(document)

    return {
        "status": "imported",
        "fileName": filename,
        "projectIdentification": (
            document.meta_information
            .project_identification
        ),
        "lifVersion": (
            document.meta_information.lif_version
        ),
        "layoutCount": len(document.layouts),
        "layouts": [
            lif_layout_summary(layout)
            for layout in document.layouts
        ],
    }


@app.get("/api/maps")
def list_lif_maps() -> dict[str, object]:
    layouts = lif_map_store.list_layouts()

    return {
        "count": len(layouts),
        "layouts": [
            lif_layout_summary(layout)
            for layout in layouts
        ],
    }


@app.get("/api/maps/{layout_id}")
def get_lif_map(
    layout_id: str,
) -> dict[str, object]:
    layout = lif_map_store.get_layout(layout_id)

    if layout is None:
        raise HTTPException(
            status_code=404,
            detail="LIF layout was not found.",
        )

    return lif_layout_to_mapping(layout)


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