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
