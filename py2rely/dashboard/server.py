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

from py2rely.dashboard.models import (
    FileList,
    JobDetail,
    MapEntry,
    MaskFilterRequest,
    MaskFilterResponse,
    MaskGenerateRequest,
    MaskGenerateResponse,
    MaskSaveRequest,
    MaskSaveResponse,
    PipelineGraph,
)
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

# Mask Tuner: directory for generated preview masks + a per-generate cache token.
_MASKTUNE_DIR = ".py2rely_masktune"
_mask_token = 0


def _safe_path(filepath: str) -> Path:
    """Resolve a project-relative path, rejecting traversal outside PROJECT_DIR."""
    resolved = (PROJECT_DIR / filepath).resolve()
    if not str(resolved).startswith(str(PROJECT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return resolved


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
                "dmean":      float(mrc.header.dmean),
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


# ---------------------------------------------------------------------------
# Mask Tuner endpoints
# ---------------------------------------------------------------------------

# Filenames that are masks / auxiliary maps rather than density maps to tune against.
_MAP_SKIP = ("mask", "moment", "gridrec", "preview")


@app.get("/api/maps", response_model=list[MapEntry])
async def list_maps() -> list[MapEntry]:
    """Enumerate candidate input density maps from jobs that produced 3D output."""
    if not (PROJECT_DIR / "default_pipeline.star").exists():
        return []  # create-mask may run outside a full RELION project
    try:
        graph = parse_pipeline(PROJECT_DIR)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    entries: list[MapEntry] = []
    for node in graph.nodes:
        if not node.has_3d:
            continue
        job_dir = PROJECT_DIR / node.id
        if not job_dir.is_dir():
            continue
        for mrc in sorted(job_dir.glob("*.mrc")):
            name = mrc.name.lower()
            if any(skip in name for skip in _MAP_SKIP):
                continue
            entries.append(
                MapEntry(
                    path=f"{node.id}/{mrc.name}",
                    job_id=node.id,
                    job_type=node.type,
                    file=mrc.name,
                )
            )
    return entries


@app.post("/api/mask/generate", response_model=MaskGenerateResponse)
async def generate_mask(req: MaskGenerateRequest) -> MaskGenerateResponse:
    """Run the MaskCreate algorithm and write a preview mask under the project dir."""
    global _mask_token

    input_path = _safe_path(req.input_path)
    if not input_path.is_file():
        raise HTTPException(status_code=404, detail=f"Input map not found: {req.input_path}")

    try:
        import mrcfile

        from py2rely.dashboard.maskcreate import build_relion_command, create_mask

        with mrcfile.open(str(input_path), mode="r", permissive=True) as mrc:
            vol = mrc.data.astype("float32")
            header_angpix = float(mrc.voxel_size.x)
            origin = (float(mrc.header.origin.x), float(mrc.header.origin.y), float(mrc.header.origin.z))
            nstart = (int(mrc.header.nxstart), int(mrc.header.nystart), int(mrc.header.nzstart))

        result = create_mask(
            vol,
            header_angpix=header_angpix,
            ini_threshold=req.ini_threshold,
            extend_inimask=req.extend_inimask,
            width_soft_edge=req.width_soft_edge,
            lowpass=req.lowpass,
            angpix=req.angpix,
            invert=req.invert,
        )

        out_dir = PROJECT_DIR / _MASKTUNE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "preview.mrc"
        with mrcfile.new(str(out_file), overwrite=True) as mrc:
            mrc.set_data(result.mask)
            mrc.voxel_size = result.angpix
            # Preserve the input map's coordinate frame so the mask aligns with it
            # (both in RELION and in the 3D overlay): origin + starting indices.
            mrc.header.origin.x, mrc.header.origin.y, mrc.header.origin.z = origin
            mrc.header.nxstart, mrc.header.nystart, mrc.header.nzstart = nstart
            mrc.update_header_stats()

        _mask_token += 1
        nz, ny, nx = result.mask.shape
        return MaskGenerateResponse(
            mask_path=f"{_MASKTUNE_DIR}/preview.mrc",
            token=_mask_token,
            angpix=result.angpix,
            nx=nx,
            ny=ny,
            nz=nz,
            fraction=result.fraction,
            command=build_relion_command(
                req.input_path,
                "mask.mrc",
                ini_threshold=req.ini_threshold,
                extend_inimask=req.extend_inimask,
                width_soft_edge=req.width_soft_edge,
                lowpass=req.lowpass,
                angpix=req.angpix,
                invert=req.invert,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mask/filter", response_model=MaskFilterResponse)
async def filter_map(req: MaskFilterRequest) -> MaskFilterResponse:
    """Low-pass filter the input map for visualization.

    RELION binarizes the *filtered* map, so previewing this lets the user read
    the binarization threshold directly off the contour slider.
    """
    global _mask_token

    if req.lowpass <= 0:
        raise HTTPException(status_code=400, detail="Lowpass must be > 0 to preview a filtered map")

    input_path = _safe_path(req.input_path)
    if not input_path.is_file():
        raise HTTPException(status_code=404, detail=f"Input map not found: {req.input_path}")

    try:
        import mrcfile

        from py2rely.dashboard.maskcreate import lowpass_filter

        with mrcfile.open(str(input_path), mode="r", permissive=True) as mrc:
            vol = mrc.data.astype("float32")
            header_angpix = float(mrc.voxel_size.x)

        used_angpix = req.angpix if req.angpix > 0 else header_angpix
        if used_angpix <= 0:
            used_angpix = 1.0

        filtered = lowpass_filter(vol, req.lowpass, used_angpix).astype("float32")

        out_dir = PROJECT_DIR / _MASKTUNE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "filtered.mrc"
        with mrcfile.new(str(out_file), overwrite=True) as mrc:
            mrc.set_data(filtered)
            mrc.voxel_size = used_angpix
            mrc.update_header_stats()

        _mask_token += 1
        nz, ny, nx = filtered.shape
        return MaskFilterResponse(
            path=f"{_MASKTUNE_DIR}/filtered.mrc",
            token=_mask_token,
            angpix=used_angpix,
            nx=nx,
            ny=ny,
            nz=nz,
            rms=float(filtered.std()),
            dmin=float(filtered.min()),
            dmax=float(filtered.max()),
            dmean=float(filtered.mean()),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mask/save", response_model=MaskSaveResponse)
async def save_mask(req: MaskSaveRequest) -> MaskSaveResponse:
    """Copy the current preview mask to a user-chosen destination within the project."""
    preview = PROJECT_DIR / _MASKTUNE_DIR / "preview.mrc"
    if not preview.is_file():
        raise HTTPException(status_code=400, detail="No mask has been generated yet")

    dest = req.dest_path.strip()
    if not dest:
        raise HTTPException(status_code=400, detail="Destination path is empty")
    if not dest.lower().endswith(".mrc"):
        dest = dest + ".mrc"

    dest_path = _safe_path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    import shutil

    shutil.copyfile(preview, dest_path)
    rel = dest_path.relative_to(PROJECT_DIR.resolve())
    return MaskSaveResponse(saved_path=str(rel))


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
_NODE_MODULES = Path(__file__).parent / "frontend" / "node_modules"
_GITHUB_API = "https://api.github.com/repos/chanzuckerberg/py2rely/releases/latest"
_VERSION_FILE = _DIST / ".dashboard-version"


def _dist_url(tag: str) -> str:
    return f"https://github.com/chanzuckerberg/py2rely/releases/download/{tag}/dashboard-dist.tar.gz"


def _latest_release_info() -> tuple[str, str] | None:
    """Return (tag_name, asset_updated_at) for the latest release, or None if unreachable."""
    try:
        req = urllib.request.Request(_GITHUB_API, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name")
        asset = next(
            (a for a in data.get("assets", []) if a["name"] == "dashboard-dist.tar.gz"),
            None,
        )
        if tag and asset:
            return tag, asset["updated_at"]
        return None
    except Exception:
        return None


def _ensure_frontend(sync: bool = False) -> None:
    """Download the pre-built frontend if missing or the release asset has been updated.

    Skipped automatically when node_modules is present (local dev build), unless
    sync=True is passed explicitly via ``py2rely ui --sync``.
    """
    info = _latest_release_info()
    latest_tag = info[0] if info else None
    latest_ts = info[1] if info else None

    installed_ts = _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else None

    if _NODE_MODULES.exists() and not sync:
        if latest_ts and latest_ts != installed_ts:
            print(
                "[py2rely-dashboard] A newer frontend build is available on GitHub. "
                "Run 'py2rely ui --sync' to update.",
                flush=True,
            )
        return

    needs_update = not _DIST.exists() or (
        latest_ts is not None and latest_ts != installed_ts
    )

    if not needs_update:
        return

    tag = latest_tag or "0.1.0"

    if _DIST.exists() and latest_ts and latest_ts != installed_ts:
        print("[py2rely-dashboard] New frontend build available — updating …", flush=True)
    else:
        print("[py2rely-dashboard] Downloading frontend assets …", flush=True)

    _DIST.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DIST.parent / "_dashboard-dist.tar.gz"
    try:
        urllib.request.urlretrieve(_dist_url(tag), tmp)
        with tarfile.open(tmp) as tf:
            tf.extractall(_DIST.parent)
        if latest_ts:
            _VERSION_FILE.write_text(latest_ts)
        print("[py2rely-dashboard] Frontend ready. Please refresh the page to see the updated interface...", flush=True)
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
    sync: bool = False,
    open_path: str = "",
    project_dir: Path | None = None,
    require_project: bool = True,
) -> None:
    global PROJECT_DIR, POLL_INTERVAL
    PROJECT_DIR = (project_dir or Path.cwd()).resolve()
    POLL_INTERVAL = poll_interval

    _ensure_frontend(sync=sync)
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")

    pipeline_star = PROJECT_DIR / "default_pipeline.star"
    if require_project and not pipeline_star.exists():
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
        webbrowser.open(f"http://localhost:{port}{open_path}")

    uvicorn.run(app, host=host, port=port, log_level="warning")
