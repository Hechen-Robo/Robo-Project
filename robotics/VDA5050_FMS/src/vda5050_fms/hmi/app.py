from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


STATIC_DIR = Path(__file__).resolve().parent / "static"

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


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")