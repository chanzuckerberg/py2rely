"""Parse default_pipeline.star into a PipelineGraph.

Accounts for the real RELION 5 / CCPEM pipeliner file structure:
- Status is stored as string labels ("Succeeded", "Running"), not integers.
- Sentinel files are RELION_JOB_EXIT_SUCCESS / PIPELINER_JOB_EXIT_SUCCESS.
- Edges are split across data_pipeline_input_edges and data_pipeline_output_edges;
  job→job edges are derived by matching output files to input files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import starfile

from py2rely.relionui.models import Edge, JobNode, PipelineGraph

# Map RELION internal type labels to human-readable display names.
_TYPE_LABEL_MAP: dict[str, str] = {
    "relion.import.other": "Import",
    "relion.import.tomo": "Import",
    "relion.motioncorr": "MotionCorr",
    "relion.ctffind": "CtfFind",
    "relion.manualpick": "ManualPick",
    "relion.autopick": "AutoPick",
    "relion.extract": "Extract",
    "relion.pseudosubtomo": "Extract",
    "relion.class2d": "Class2D",
    "relion.select": "Select",
    "relion.select.onvalue": "Select",
    "relion.class3d": "Class3D",
    "relion.class3d.tomo": "Class3D",
    "relion.refine3d": "Refine3D",
    "relion.refine3d.tomo": "Refine3D",
    "relion.postprocess": "PostProcess",
    "relion.ctfrefine": "CtfRefine",
    "relion.ctfrefinetomo": "CtfRefine",
    "relion.polish": "Polish",
    "relion.framealigntomo": "Polish",
    "relion.localres": "LocalRes",
    "relion.maskcreate": "MaskCreate",
    "relion.reconstructparticletomo": "Reconstruct",
}

_BINFACTOR_TYPES = {"Extract", "Reconstruct"}

_STAR_STATUS_MAP: dict[str, str] = {
    "Succeeded": "finished",
    "Running": "running",
    "Failed": "failed",
    "Aborted": "aborted",
}


def _strip_slash(name: str) -> str:
    return name.rstrip("/")


def _detect_status(job_dir: Path, star_status: str) -> str:
    """Determine job status by cross-referencing sentinel files with pipeline.star."""
    if (job_dir / "PIPELINER_JOB_EXIT_SUCCESS").exists():
        return "finished"
    if (job_dir / "RELION_JOB_EXIT_SUCCESS").exists():
        # RELION finished but pipeliner hasn't written its sentinel yet — treat as running.
        return "running"
    return _STAR_STATUS_MAP.get(star_status, "queued")


def _read_binfactor(job_dir: Path) -> Optional[str]:
    """Read the binfactor parameter from job.star for Extract / Reconstruct jobs."""
    job_star = job_dir / "job.star"
    if not job_star.exists():
        return None
    try:
        data = starfile.read(str(job_star))
        params_df: pd.DataFrame = data.get("joboptions_values", pd.DataFrame())
        if params_df.empty:
            return None
        row = params_df[params_df["rlnJobOptionVariable"] == "binfactor"]
        if row.empty:
            return None
        return str(row.iloc[0]["rlnJobOptionValue"]).strip()
    except Exception:
        return None


def _get_timestamp(job_dir: Path) -> Optional[str]:
    info_file = job_dir / ".CCPEM_pipeliner_jobinfo"
    if info_file.exists():
        try:
            return json.loads(info_file.read_text()).get("created")
        except Exception:
            pass
    return None


def _display_type(type_label: str) -> str:
    if type_label in _TYPE_LABEL_MAP:
        return _TYPE_LABEL_MAP[type_label]
    # Fall back to last segment, title-cased: "relion.foo.bar" → "Bar"
    return type_label.split(".")[-1].title()


def parse_pipeline(project_dir: Path) -> PipelineGraph:
    """Read default_pipeline.star and return a fully resolved PipelineGraph."""
    data: dict[str, pd.DataFrame] = starfile.read(str(project_dir / "default_pipeline.star"))

    processes: pd.DataFrame = data.get("pipeline_processes", pd.DataFrame())
    nodes_df: pd.DataFrame = data.get("pipeline_nodes", pd.DataFrame())
    input_edges: pd.DataFrame = data.get("pipeline_input_edges", pd.DataFrame())
    output_edges: pd.DataFrame = data.get("pipeline_output_edges", pd.DataFrame())

    # Build node-type lookup: file path → node type label
    node_type_map: dict[str, str] = {}
    if not nodes_df.empty:
        node_type_map = dict(
            zip(nodes_df["rlnPipeLineNodeName"], nodes_df["rlnPipeLineNodeTypeLabel"])
        )

    # Jobs that produce at least one DensityMap output → has_3d
    jobs_with_3d: set[str] = set()
    jobs_with_results: set[str] = set()
    if not output_edges.empty:
        for _, row in output_edges.iterrows():
            job_id = _strip_slash(row["rlnPipeLineEdgeProcess"])
            jobs_with_results.add(job_id)
            node_type = node_type_map.get(row["rlnPipeLineEdgeToNode"], "")
            if "DensityMap.mrc" in node_type:
                jobs_with_3d.add(job_id)

    # Build JobNode list
    job_nodes: list[JobNode] = []
    if not processes.empty:
        for _, row in processes.iterrows():
            job_id = _strip_slash(row["rlnPipeLineProcessName"])
            type_label = row.get("rlnPipeLineProcessTypeLabel", "")
            alias = row.get("rlnPipeLineProcessAlias", "None")
            star_status = row.get("rlnPipeLineProcessStatusLabel", "")

            disp_type = _display_type(type_label)
            job_dir = project_dir / job_id

            job_nodes.append(
                JobNode(
                    id=job_id,
                    type=disp_type,
                    alias=disp_type if alias == "None" else alias,
                    status=_detect_status(job_dir, star_status),
                    timestamp=_get_timestamp(job_dir),
                    has_results=job_id in jobs_with_results,
                    has_3d=job_id in jobs_with_3d,
                    binfactor=_read_binfactor(job_dir) if disp_type in _BINFACTOR_TYPES else None,
                )
            )

    # Build job→job edges via shared file intermediaries.
    # output_edges: job → file;  input_edges: file → job
    # Edge exists when file produced by job A is consumed by job B.
    file_to_producer: dict[str, str] = {}
    if not output_edges.empty:
        for _, row in output_edges.iterrows():
            file_to_producer[row["rlnPipeLineEdgeToNode"]] = _strip_slash(
                row["rlnPipeLineEdgeProcess"]
            )

    edges: list[Edge] = []
    seen: set[tuple[str, str]] = set()
    if not input_edges.empty:
        for _, row in input_edges.iterrows():
            consumer = _strip_slash(row["rlnPipeLineEdgeProcess"])
            producer = file_to_producer.get(row["rlnPipeLineEdgeFromNode"])
            if producer and producer != consumer:
                key = (producer, consumer)
                if key not in seen:
                    seen.add(key)
                    edges.append(Edge(source=producer, target=consumer))

    return PipelineGraph(project_dir=str(project_dir), nodes=job_nodes, edges=edges)


def parse_job_detail(project_dir: Path, job_id: str) -> dict[str, str]:
    """Return the job parameters from job.star as a flat key→value dict."""
    job_star = project_dir / job_id / "job.star"
    if not job_star.exists():
        return {}
    try:
        data = starfile.read(str(job_star))
        params_df: pd.DataFrame = data.get("joboptions_values", pd.DataFrame())
        if params_df.empty:
            return {}
        return dict(
            zip(params_df["rlnJobOptionVariable"], params_df["rlnJobOptionValue"].astype(str))
        )
    except Exception:
        return {}


def get_job_type(project_dir: Path, job_id: str) -> str:
    """Return the display type for a job (read from job.star)."""
    job_star = project_dir / job_id / "job.star"
    if not job_star.exists():
        return job_id.split("/")[0]
    try:
        data = starfile.read(str(job_star))
        job_block = data.get("job", {})
        if isinstance(job_block, pd.DataFrame):
            type_label = str(job_block.get("rlnJobTypeLabel", pd.Series([""]))[0])
        elif isinstance(job_block, dict):
            type_label = str(job_block.get("rlnJobTypeLabel", ""))
        else:
            type_label = ""
        return _display_type(type_label) if type_label else job_id.split("/")[0]
    except Exception:
        return job_id.split("/")[0]


def get_command_history(project_dir: Path, job_id: str) -> list[str]:
    """Return the command history from .CCPEM_pipeliner_jobinfo."""
    info_file = project_dir / job_id / ".CCPEM_pipeliner_jobinfo"
    if not info_file.exists():
        return []
    try:
        data = json.loads(info_file.read_text())
        return data.get("command_history", [])
    except Exception:
        return []
