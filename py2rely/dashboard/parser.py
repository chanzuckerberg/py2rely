"""Parse default_pipeline.star into a PipelineGraph.

Accounts for the real RELION 5 / CCPEM pipeliner file structure:
- Status is stored as string labels ("Succeeded", "Running"), not integers.
- Sentinel files are RELION_JOB_EXIT_SUCCESS / PIPELINER_JOB_EXIT_SUCCESS.
- Edges are split across data_pipeline_input_edges and data_pipeline_output_edges;
  job→job edges are derived by matching output files to input files.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import starfile

from py2rely.dashboard.models import Edge, JobNode, PipelineGraph

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
    "relion.initialmodel.tomo": "InitialModel",
    "relion.reconstructparticletomo": "Reconstruct",
}

_BINFACTOR_TYPES = {"Extract", "Reconstruct"}
_RESOLUTION_TYPES = {"PostProcess", "Refine3D", "Class3D", "InitialModel"}

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
        return "finished"
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


def _read_resolution(job_dir: Path, disp_type: str) -> Optional[float]:
    """Read the best final resolution from job output star files."""
    try:
        if disp_type == "PostProcess":
            pp = job_dir / "postprocess.star"
            if not pp.exists():
                return None
            d = starfile.read(str(pp))
            gen = d.get("general", {})
            if isinstance(gen, pd.DataFrame):
                gen = gen.iloc[0].to_dict() if not gen.empty else {}
            val = float(gen.get("rlnFinalResolution", 0))
            return round(val, 2) if val > 0 else None

        elif disp_type == "Refine3D":
            files = sorted(job_dir.glob("run_it*_half1_model.star"))
            if not files:
                return None
            d = starfile.read(str(files[-1]))
            gen = d.get("model_general", {})
            if isinstance(gen, pd.DataFrame):
                gen = gen.iloc[0].to_dict() if not gen.empty else {}
            val = float(gen.get("rlnCurrentResolution", 0))
            return round(val, 2) if val > 0 and math.isfinite(val) else None

        elif disp_type == "Class3D":
            files = sorted(job_dir.glob("run_it*_model.star"))
            if not files:
                return None
            d = starfile.read(str(files[-1]))
            mc: pd.DataFrame = d.get("model_classes", pd.DataFrame())
            if isinstance(mc, pd.DataFrame) and not mc.empty and "rlnEstimatedResolution" in mc.columns:
                vals = [float(r) for r in mc["rlnEstimatedResolution"]
                        if math.isfinite(float(r)) and float(r) > 0]
                return round(min(vals), 2) if vals else None
    except Exception:
        return None
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
            if "DensityMap.mrc" in node_type or "Mask3D.mrc" in node_type:
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

            resolution = _read_resolution(job_dir, disp_type) if disp_type in _RESOLUTION_TYPES else None
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
                    resolution=resolution,
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
    """Return the command from the job's note.txt file."""
    note_file = project_dir / job_id / "note.txt"
    if not note_file.exists():
        return []
    try:
        lines = note_file.read_text().splitlines()
        for i, line in enumerate(lines):
            if "with the following command" in line and i + 1 < len(lines):
                cmd = lines[i + 1].strip()
                return [cmd] if cmd else []
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Analysis parsing
# ---------------------------------------------------------------------------


def parse_analysis(project_dir: Path, job_id: str) -> dict:  # type: ignore[type-arg]
    """Return job-type-specific analysis data for the Analysis tab."""
    job_type = get_job_type(project_dir, job_id)
    job_dir = project_dir / job_id
    dispatchers = {
        "Refine3D":    _parse_refine3d_analysis,
        "Class3D":     _parse_class3d_analysis,
        "InitialModel": _parse_class3d_analysis,
        "PostProcess": _parse_postprocess_analysis,
        "CtfFind":     _parse_ctffind_analysis,
        "Polish":      _parse_polish_analysis,
        "CtfRefine":   _parse_ctfrefine_analysis,
    }
    fn = dispatchers.get(job_type)
    if fn is None:
        return {"type": job_type, "available": False}
    try:
        return fn(job_dir)
    except Exception as exc:
        return {"type": job_type, "error": str(exc), "available": False}


def _parse_refine3d_analysis(job_dir: Path) -> dict:  # type: ignore[type-arg]
    """Convergence (resolution vs iteration) and gold-standard FSC for Refine3D."""
    model_files = sorted(job_dir.glob("run_it*_half1_model.star"))

    convergence = []
    for mf in model_files:
        m = re.search(r"run_it(\d+)_half1", mf.name)
        if not m:
            continue
        it = int(m.group(1))
        try:
            d = starfile.read(str(mf))
            mc: pd.DataFrame = d.get("model_classes", pd.DataFrame())
            if not mc.empty and "rlnEstimatedResolution" in mc.columns:
                res = float(mc.iloc[0]["rlnEstimatedResolution"])
                if math.isfinite(res) and res > 0:
                    convergence.append({"iter": it, "resolution": round(res, 3)})
        except Exception:
            continue

    fsc: list[dict] = []  # type: ignore[type-arg]
    summary: dict = {}  # type: ignore[type-arg]
    if model_files:
        try:
            d = starfile.read(str(model_files[-1]))

            # FSC curve from model_class_1
            class1: pd.DataFrame = d.get("model_class_1", pd.DataFrame())
            if not class1.empty:
                for _, row in class1.iterrows():
                    res_a = float(row.get("rlnAngstromResolution", 0))
                    fsc_v = float(row.get("rlnGoldStandardFsc", 0))
                    if math.isfinite(res_a) and res_a > 0:
                        fsc.append({"resolution_a": round(res_a, 3), "fsc": round(fsc_v, 4)})

            # Summary from model_general + model_classes
            gen = d.get("model_general", {})
            if isinstance(gen, dict):
                pixel_size = float(gen.get("rlnPixelSize", 0))
                summary = {
                    "final_resolution": round(float(gen.get("rlnCurrentResolution", 0)), 2),
                    "nyquist":          round(pixel_size * 2, 3) if pixel_size > 0 else None,
                    "pixel_size":       round(pixel_size, 3),
                    "box_size":         int(gen.get("rlnOriginalImageSize", 0)),
                    "avg_pmax":         round(float(gen.get("rlnAveragePmax", 0)), 3),
                    "iterations":       len(model_files),
                }
            mc: pd.DataFrame = d.get("model_classes", pd.DataFrame())
            if not mc.empty:
                row0 = mc.iloc[0]
                summary["acc_rot"]   = round(float(row0.get("rlnAccuracyRotations", 0)), 2)
                summary["acc_trans"] = round(float(row0.get("rlnAccuracyTranslationsAngst", 0)), 2)
        except Exception:
            pass

    fsc.sort(key=lambda x: x["resolution_a"], reverse=True)
    return {"type": "Refine3D", "convergence": convergence, "fsc": fsc, "summary": summary}


def _parse_class3d_analysis(job_dir: Path) -> dict:  # type: ignore[type-arg]
    """Class convergence, per-class FSC, angular distribution, and class stats for Class3D."""
    model_files = sorted(job_dir.glob("run_it*_model.star"))

    convergence = []
    for mf in model_files:
        m = re.search(r"run_it(\d+)_model", mf.name)
        if not m:
            continue
        it = int(m.group(1))
        try:
            d = starfile.read(str(mf))
            mc: pd.DataFrame = d.get("model_classes", pd.DataFrame())
            if mc.empty:
                continue
            dist_vals = [
                round(float(row.get("rlnClassDistribution", 0)), 4)
                for _, row in mc.iterrows()
            ]
            res_vals = [float(row.get("rlnEstimatedResolution", math.inf)) for _, row in mc.iterrows()]
            finite_res = [r for r in res_vals if math.isfinite(r) and r > 0]
            best_res = round(min(finite_res), 3) if finite_res else None
            convergence.append({"iter": it, "resolution": best_res, "class_dist": dist_vals})
        except Exception:
            continue

    fsc_per_class: dict[str, list] = {}  # type: ignore[type-arg]
    class_stats: list[dict] = []  # type: ignore[type-arg]
    if model_files:
        try:
            d = starfile.read(str(model_files[-1]))
            mc = d.get("model_classes", pd.DataFrame())
            if not mc.empty:
                for i, (_, row) in enumerate(mc.iterrows(), start=1):
                    res_raw = float(row.get("rlnEstimatedResolution", math.inf))
                    class_stats.append({
                        "class": i,
                        "distribution": round(float(row.get("rlnClassDistribution", 0)) * 100, 1),
                        "resolution": round(res_raw, 2) if math.isfinite(res_raw) and res_raw > 0 else None,
                        "acc_rot":   round(float(row.get("rlnAccuracyRotations", 0)), 2),
                        "acc_trans": round(float(row.get("rlnAccuracyTranslationsAngst", 0)), 2),
                    })
                    class_block: pd.DataFrame = d.get(f"model_class_{i}", pd.DataFrame())
                    if not class_block.empty:
                        shells = []
                        for _, srow in class_block.iterrows():
                            res_a = float(srow.get("rlnAngstromResolution", 0))
                            fsc_v = float(srow.get("rlnGoldStandardFsc", 0))
                            if math.isfinite(res_a) and res_a > 0:
                                shells.append({"resolution_a": round(res_a, 3), "fsc": round(fsc_v, 4)})
                        shells.sort(key=lambda x: x["resolution_a"], reverse=True)
                        fsc_per_class[str(i)] = shells
        except Exception:
            pass

    angular_dist = None
    data_files = sorted(job_dir.glob("run_it*_data.star"))
    if data_files:
        try:
            d = starfile.read(str(data_files[-1]))
            particles: pd.DataFrame = d.get("particles", pd.DataFrame())
            if not particles.empty and "rlnAngleRot" in particles.columns:
                rot  = particles["rlnAngleRot"].values.astype(float) % 360
                tilt = np.clip(particles["rlnAngleTilt"].values.astype(float), 0, 180)
                hist, _, _ = np.histogram2d(rot, tilt, bins=[36, 18], range=[[0, 360], [0, 180]])
                angular_dist = hist.tolist()
        except Exception:
            pass

    return {
        "type": "Class3D",
        "convergence": convergence,
        "fsc_per_class": fsc_per_class,
        "angular_dist": angular_dist,
        "class_stats": class_stats,
    }


def _parse_postprocess_analysis(job_dir: Path) -> dict:  # type: ignore[type-arg]
    """Masked/unmasked/phase-randomized FSC + summary for PostProcess."""
    pp_star = job_dir / "postprocess.star"
    fsc: list[dict] = []  # type: ignore[type-arg]
    summary: dict = {}  # type: ignore[type-arg]
    if pp_star.exists():
        try:
            d = starfile.read(str(pp_star))

            # FSC curve
            fsc_df: pd.DataFrame = d.get("fsc", pd.DataFrame())
            if not fsc_df.empty:
                for _, row in fsc_df.iterrows():
                    res_a = float(row.get("rlnAngstromResolution", 0))
                    if not math.isfinite(res_a) or res_a <= 0:
                        continue
                    fsc.append({
                        "resolution_a": round(res_a, 3),
                        "corrected":    round(float(row.get("rlnFourierShellCorrelationCorrected", 0)), 4),
                        "unmasked":     round(float(row.get("rlnFourierShellCorrelationUnmaskedMaps", 0)), 4),
                        "phase_rand":   round(float(row.get("rlnCorrectedFourierShellCorrelationPhaseRandomizedMaskedMaps", 0)), 4),
                    })

            # Summary from general block
            gen = d.get("general", {})
            if isinstance(gen, dict):
                mask_name = gen.get("rlnMaskName", "")
                summary = {
                    "final_resolution":  round(float(gen.get("rlnFinalResolution", 0)), 2),
                    "bfactor":           round(float(gen.get("rlnBfactorUsedForSharpening", 0)), 1),
                    "phase_rand_from":   round(float(gen.get("rlnRandomiseFrom", 0)), 2),
                    "solvent_fraction":  round(float(gen.get("rlnParticleBoxFractionSolventMask", 0)), 1),
                    "mask":              Path(mask_name).name if mask_name else "",
                }
        except Exception:
            pass

    fsc.sort(key=lambda x: x["resolution_a"], reverse=True)
    # Nyquist = smallest shell in the FSC data
    if fsc:
        summary["nyquist"] = fsc[-1]["resolution_a"]
    return {"type": "PostProcess", "fsc": fsc, "summary": summary}


def _parse_polish_analysis(job_dir: Path) -> dict:  # type: ignore[type-arg]
    """Per-particle motion statistics for Polish / FrameAlignTomo."""
    motion_star = job_dir / "motion.star"
    if not motion_star.exists():
        return {"type": "Polish", "available": False, "error": "motion.star not found"}
    try:
        d = starfile.read(str(motion_star))
        general = d.get("general", {})
        n_particles_expected = general.get("rlnParticleNumber", 0) if isinstance(general, dict) else 0

        rms_vals: list[float] = []
        for key, df in d.items():
            if key == "general" or not isinstance(df, pd.DataFrame):
                continue
            if not all(c in df.columns for c in ["rlnOriginXAngst", "rlnOriginYAngst", "rlnOriginZAngst"]):
                continue
            x = df["rlnOriginXAngst"].values.astype(float)
            y = df["rlnOriginYAngst"].values.astype(float)
            z = df["rlnOriginZAngst"].values.astype(float)
            # RMS displacement relative to mean position (motion jitter per particle)
            rms = float(np.sqrt(np.mean(
                (x - x.mean()) ** 2 + (y - y.mean()) ** 2 + (z - z.mean()) ** 2
            )))
            rms_vals.append(round(rms, 3))

        if not rms_vals:
            return {"type": "Polish", "available": False, "error": "No motion data found"}

        arr = np.array(rms_vals)
        counts, edges = np.histogram(arr, bins=30)
        histogram = [
            {"bin_center": round(float(edges[i] + edges[i + 1]) / 2, 3), "count": int(counts[i])}
            for i in range(len(counts))
        ]

        return {
            "type":      "Polish",
            "n_particles": len(rms_vals),
            "median":    round(float(np.median(arr)), 3),
            "mean":      round(float(np.mean(arr)), 3),
            "max":       round(float(np.max(arr)), 3),
            "histogram": histogram,
        }
    except Exception as exc:
        return {"type": "Polish", "available": False, "error": str(exc)}


def _parse_ctfrefine_analysis(job_dir: Path) -> dict:  # type: ignore[type-arg]
    """Per-tomogram refined defocus statistics from temp/defocus/*.star."""
    defocus_dir = job_dir / "temp" / "defocus"
    if not defocus_dir.is_dir():
        return {"type": "CtfRefine", "available": False, "error": "temp/defocus/ not found"}
    try:
        star_files = sorted(defocus_dir.glob("*.star"))
        if not star_files:
            return {"type": "CtfRefine", "available": False, "error": "No defocus star files found"}

        per_tomo = []
        n_tilts_total = 0
        for i, sf in enumerate(star_files):
            try:
                df: pd.DataFrame = starfile.read(str(sf))
                if df.empty or "rlnDefocusU" not in df.columns:
                    continue
                du = df["rlnDefocusU"].values.astype(float) / 10000  # Å → μm
                dv = df["rlnDefocusV"].values.astype(float) / 10000
                n_tilts_total += len(df)
                per_tomo.append({
                    "idx":          i,
                    "name":         sf.stem,
                    "defocusU":     round(float(np.mean(du)), 3),
                    "defocusV":     round(float(np.mean(dv)), 3),
                    "astigmatism":  round(float(np.mean(np.abs(du - dv))), 3),
                    "tilt_spread":  round(float(np.std(du)), 3),
                })
            except Exception:
                continue

        if not per_tomo:
            return {"type": "CtfRefine", "available": False, "error": "Could not parse defocus data"}

        return {
            "type":          "CtfRefine",
            "n_tomograms":   len(per_tomo),
            "n_tilts_total": n_tilts_total,
            "per_tomo":      per_tomo,
        }
    except Exception as exc:
        return {"type": "CtfRefine", "available": False, "error": str(exc)}


def _parse_ctffind_analysis(job_dir: Path) -> dict:  # type: ignore[type-arg]
    """Per-micrograph CTF parameters for CtfFind."""
    ctf_star = job_dir / "micrographs_ctf.star"
    micrographs: list[dict] = []  # type: ignore[type-arg]
    if ctf_star.exists():
        try:
            d = starfile.read(str(ctf_star))
            mic_df: pd.DataFrame = d.get("micrographs", pd.DataFrame())
            if not mic_df.empty:
                for i, (_, row) in enumerate(mic_df.iterrows()):
                    du = float(row.get("rlnDefocusU", 0))
                    dv = float(row.get("rlnDefocusV", 0))
                    micrographs.append({
                        "idx":         i,
                        "defocusU":    round(du / 10000, 3),   # Å → μm
                        "defocusV":    round(dv / 10000, 3),
                        "astigmatism": round(abs(du - dv) / 10000, 3),
                        "maxRes":      round(float(row.get("rlnCtfMaxResolution", 0)), 2),
                        "fom":         round(float(row.get("rlnCtfFigureOfMerit", 0)), 3),
                    })
        except Exception:
            pass
    return {"type": "CtfFind", "micrographs": micrographs}
