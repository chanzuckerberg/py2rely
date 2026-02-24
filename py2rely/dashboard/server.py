"""FastAPI application and uvicorn launcher for py2rely-dashboard."""

from __future__ import annotations

import asyncio
import json
import tarfile
import urllib.request
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from py2rely.dashboard.models import FileList, JobDetail, PipelineGraph
from py2rely.dashboard.parser import (
    get_command_history,
    get_job_type,
    parse_analysis,
    parse_job_detail,
    parse_pipeline,
)
from py2rely.dashboard.watcher import PipelineWatcher

# ---------------------------------------------------------------------------
# Module-level state (populated by launch() before uvicorn starts)
# ---------------------------------------------------------------------------
PROJECT_DIR = Path.cwd()
POLL_INTERVAL = 5

_connected: set[WebSocket] = set()


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------


async def _broadcast(message: dict) -> None:  # type: ignore[type-arg]
    dead: set[WebSocket] = set()
    for ws in _connected:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.add(ws)
    _connected.difference_update(dead)


async def _on_change() -> None:
    await _broadcast({"type": "pipeline_refresh"})


# ---------------------------------------------------------------------------
# Lifespan: start watcher on server boot
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    watcher = PipelineWatcher(PROJECT_DIR, POLL_INTERVAL, _on_change)
    task = asyncio.create_task(watcher.start())
    yield
    task.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="py2rely-dashboard", version="0.1.0", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/ping")
async def ping() -> dict:  # type: ignore[type-arg]
    return {"status": "ok", "project_dir": str(PROJECT_DIR)}


@app.get("/api/pipeline", response_model=PipelineGraph)
async def get_pipeline() -> PipelineGraph:
    try:
        return parse_pipeline(PROJECT_DIR)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Sub-resources use /api/log/, /api/files/, /api/file/, /api/mapinfo/ prefixes
# so the greedy {job_id:path} parameter always trails the route, avoiding
# the FastAPI path-swallowing issue with nested path parameters.


@app.get("/api/mapinfo/{filepath:path}")
async def get_map_info(filepath: str) -> dict:  # type: ignore[type-arg]
    """Return MRC header metadata (box size, voxel size) for the stats overlay."""
    file_path = (PROJECT_DIR / filepath).resolve()
    if not str(file_path).startswith(str(PROJECT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        import mrcfile
        with mrcfile.open(str(file_path), mode="r", permissive=True) as mrc:
            rms  = float(mrc.header.rms)  if float(mrc.header.rms)  > 0 else 1.0
            dmax = float(mrc.header.dmax) if float(mrc.header.dmax) > 0 else rms * 6
            origin = mrc.header.origin
            return {
                "nx":         int(mrc.header.nx),
                "ny":         int(mrc.header.ny),
                "nz":         int(mrc.header.nz),
                "voxel_size": float(mrc.voxel_size.x),
                "rms":        rms,
                "dmin":       float(mrc.header.dmin),
                "dmax":       dmax,
                "originX":    float(origin.x),
                "originY":    float(origin.y),
                "originZ":    float(origin.z),
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/log/{job_id:path}", response_class=PlainTextResponse)
async def get_job_log(job_id: str) -> str:
    log_file = PROJECT_DIR / job_id / "run.out"
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"No log found for {job_id}")
    return log_file.read_text(errors="replace")


@app.get("/api/files/{job_id:path}", response_model=FileList)
async def list_job_files(job_id: str) -> FileList:
    job_dir = PROJECT_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    files = sorted(
        f.name
        for f in job_dir.iterdir()
        if f.is_file() and not f.name.startswith(".")
    )
    return FileList(job_id=job_id, files=files)


@app.get("/api/file/{filepath:path}")
async def serve_file(filepath: str) -> FileResponse:
    """Serve any project file by its relative path (e.g. Refine3D/job003/run_class001.mrc)."""
    file_path = (PROJECT_DIR / filepath).resolve()
    # Reject path traversal outside the project directory
    if not str(file_path).startswith(str(PROJECT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    return FileResponse(str(file_path))


@app.get("/api/analysis/{job_id:path}")
async def get_analysis(job_id: str) -> dict:  # type: ignore[type-arg]
    """Return job-type-specific analysis data (FSC curves, convergence, CTF scatter, etc.)."""
    try:
        return parse_analysis(PROJECT_DIR, job_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Must come after the more-specific /api/* routes so the greedy path
# parameter doesn't shadow them.
@app.get("/api/job/{job_id:path}", response_model=JobDetail)
async def get_job(job_id: str) -> JobDetail:
    job_dir = PROJECT_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobDetail(
        id=job_id,
        type=get_job_type(PROJECT_DIR, job_id),
        parameters=parse_job_detail(PROJECT_DIR, job_id),
        command_history=get_command_history(PROJECT_DIR, job_id),
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _connected.add(websocket)
    try:
        while True:
            # Keep connection alive; we only push from server side.
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connected.discard(websocket)


# ---------------------------------------------------------------------------
# Frontend distribution
# ---------------------------------------------------------------------------

_DIST = Path(__file__).parent / "frontend" / "dist"

# URL to the pre-built frontend tarball on GitHub Releases.
# The tarball should contain a top-level dist/ folder
# (created with: cd py2rely/dashboard/frontend && tar czf dashboard-dist.tar.gz dist/)
_DIST_URL = "https://github.com/chanzuckerberg/py2rely/releases/download/v0.0.0/dashboard-dist.tar.gz"


def _ensure_frontend() -> None:
    """Download and extract the pre-built frontend into the package directory if missing."""
    if _DIST.exists():
        return
    print("[py2rely-dashboard] Frontend assets not found. Downloading...", flush=True)
    _DIST.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DIST.parent / "_dashboard-dist.tar.gz"
    try:
        urllib.request.urlretrieve(_DIST_URL, tmp)
        with tarfile.open(tmp) as tf:
            tf.extractall(_DIST.parent)
        print("[py2rely-dashboard] Frontend ready.", flush=True)
    except Exception as exc:
        raise SystemExit(
            f"\n[py2rely-dashboard] Failed to download frontend assets: {exc}\n"
            f"You can manually build them with:\n"
            f"  cd py2rely/dashboard/frontend && npm run build\n"
        ) from exc
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------


def launch(
    host: str = "127.0.0.1",
    port: int = 3000,
    open_browser: bool = True,
    poll_interval: int = 5,
) -> None:
    global PROJECT_DIR, POLL_INTERVAL
    PROJECT_DIR = Path.cwd()
    POLL_INTERVAL = poll_interval

    _ensure_frontend()
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")

    pipeline_star = PROJECT_DIR / "default_pipeline.star"
    if not pipeline_star.exists():
        print(
            f"\n[py2rely-dashboard] No 'default_pipeline.star' found in {PROJECT_DIR}\n"
            "Make sure you run 'py2rely ui' from inside a RELION project directory.\n"
        )
        raise SystemExit(1)

    url = f"http://{host}:{port}"
    print(f"\n[py2rely-dashboard] Running at {url}")

    if host in ("0.0.0.0", "::"):
        print(
            f"[py2rely-dashboard] If on a remote host, forward with:\n"
            f"            ssh -L {port}:localhost:{port} <your-hpc-host>"
        )

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run(app, host=host, port=port, log_level="warning")
