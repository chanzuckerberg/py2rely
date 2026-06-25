"""Pydantic models for all relion-ui API responses."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class JobNode(BaseModel):
    id: str  # e.g. "Class3D/job009"
    type: str  # display name, e.g. "Class3D"
    alias: str
    status: str  # queued | running | finished | failed | aborted
    timestamp: Optional[str]
    has_results: bool
    has_3d: bool
    binfactor: Optional[str] = None  # only set for Extract / Reconstruct jobs
    resolution: Optional[float] = None  # only set for PostProcess / Refine3D / Class3D
    inputs: list[str] = []   # job IDs that directly feed into this job
    outputs: list[str] = []  # job IDs that directly consume this job's output


class Edge(BaseModel):
    source: str  # job id
    target: str  # job id


class PipelineGraph(BaseModel):
    project_dir: str
    nodes: list[JobNode]
    edges: list[Edge]


class JobDetail(BaseModel):
    id: str
    type: str
    parameters: dict[str, str]
    command_history: list[str]


class FileList(BaseModel):
    job_id: str
    files: list[str]


class WSMessage(BaseModel):
    type: str  # status_update | log_line | pipeline_refresh
    job_id: Optional[str] = None
    status: Optional[str] = None
    line: Optional[str] = None


# ---------------------------------------------------------------------------
# Mask Tuner models
# ---------------------------------------------------------------------------


class MapEntry(BaseModel):
    path: str       # project-relative path, e.g. "Refine3D/job021/run_class001.mrc"
    job_id: str     # e.g. "Refine3D/job021"
    job_type: str   # display type, e.g. "Refine3D"
    file: str       # bare filename, e.g. "run_class001.mrc"


class MaskGenerateRequest(BaseModel):
    input_path: str                       # project-relative .mrc path
    ini_threshold: float = 0.02
    extend_inimask: float = 3.0
    width_soft_edge: float = 3.0
    lowpass: float = -1.0                  # Å; <= 0 disables
    angpix: float = -1.0                   # Å; <= 0 uses header value
    invert: bool = False


class MaskGenerateResponse(BaseModel):
    mask_path: str          # project-relative path to the generated preview mask
    token: int              # cache-buster: increments on each generate
    angpix: float
    nx: int
    ny: int
    nz: int
    fraction: float         # fraction of the box occupied by the mask
    command: str            # equivalent relion_mask_create command line


class MaskSaveRequest(BaseModel):
    dest_path: str          # project-relative destination for mask.mrc


class MaskSaveResponse(BaseModel):
    saved_path: str


class MaskFilterRequest(BaseModel):
    input_path: str         # project-relative .mrc path
    lowpass: float          # Å; must be > 0
    angpix: float = -1.0    # Å; <= 0 uses header value


class MaskFilterResponse(BaseModel):
    path: str               # project-relative path to the filtered preview map
    token: int              # cache-buster
    angpix: float
    nx: int
    ny: int
    nz: int
    rms: float
    dmin: float
    dmax: float
    dmean: float
