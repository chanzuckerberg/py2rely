"""py2rely MCP Server — exposes py2rely and slabpick CLI commands as MCP tools."""

import glob
import logging
import os
import subprocess
import sys
from typing import Any

from fastmcp import FastMCP

logger = logging.getLogger("py2rely-mcp")
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

mcp = FastMCP(
    "py2rely MCP Server",
    instructions="""py2rely is a CLI tool for RELION sub-tomogram averaging (STA) workflows on HPC.

Always begin by asking the user which workflow they want to run before proceeding.

WORKFLOW A — 2D Slab Particle Filtering
Use this when the user wants to validate or clean picks from a copick project using 2D class averages.

  Step 1 (direct): make_minislabs then normalize_stack
      Extract slabs from tomograms and normalize the stack for RELION.
      Key params for make_minislabs: --out_dir, --in_coords (copick config or star file), --extract_shape,
                  --voxel_spacing, --tomo_type, --user_id, --particle_name, --make_stack
      Key params for normalize_stack: --in_stack, --out_stack, --apix
      If the user asks for a SLURM script instead, use: py2rely-slurm slab slabpick
          Generates slabpick.sh; user submits with: sbatch slabpick.sh

  Step 2 (direct): py2rely slab class2d
      Runs RELION Class2D directly (blocking).
      Key params: --particle-diameter, --num-classes (or --nr-classes), --tau-fudge, --class-algorithm
      If the user asks for a SLURM script instead, use: py2rely-slurm slab class2d
          Generates class2d.sh; user submits with: sbatch class2d.sh

  Step 3 (you do this): call get_class2d_summary_pdf to locate or generate the class gallery PDF.
      Read the PDF, inspect the class averages visually, and suggest which classes contain real signal.
      The user makes the final selection decision.

  Step 3b (direct): py2rely routines select -p <particles_star_path> -c <comma-separated class numbers>
      Export particles belonging to the selected classes. Use the class numbers as labeled in the PDF gallery.
      Example: py2rely routines select -p Class2D/job001/run_it025_data.star -c 1,3,5
      Use --output to write to a custom path; omit it to append a Select job to the RELION pipeline history.
      ALWAYS suggest this command after recommending classes — never skip this step.

  Step 4 (direct): rln_map_particles
      Maps selected RELION particles back to copick coordinates.
      Key params: --rln_file, --map_file, --particle_name, --user_id, --session_id,
                  --user_id_out, --session_id_out

WORKFLOW B — 3D Sub-Tomogram Averaging
Use this when the user wants to run a full 3D reconstruction from copick coordinates.

  Step 1 (direct): py2rely prepare particles
      Exports copick picks to a RELION star file.
      Key params: --config, --name, --session, --session-id, --user-id, --voxel-size

  Step 1b (direct, if needed): py2rely prepare tilt-series, combine-particles, filter-unused-tilts, relion5-parameters
      Run whichever prepare commands are needed to assemble the full input set.

  Step 2 (direct or SLURM via --submitit): py2rely pipelines sta
      Runs the full iterative STA pipeline.
      Key params: --parameter (sta_parameters.json), --reference-template, --submitit,
                  --run-class3d, --run-denovo-generation

  Step 3 (optional, direct): py2rely routines class3d
      Runs a single RELION Class3D job directly (blocking).
      HUMAN DECISION: which 3D class to keep is always the user's call — never choose for them.
      After the user decides, run: py2rely routines select -p <particles_star_path> -c <class number>
      Example: py2rely routines select -p Class3D/job001/run_it025_data.star -c 2
      ALWAYS suggest this command once the user has made their class decision.
      If the user asks for a SLURM script instead, use: py2rely-slurm routines class3d
          Generates class3d.sh; user submits with: sbatch class3d.sh

  Step 3b (optional, direct): py2rely routines extract
      Extract pseudo sub-tomograms from tilt-series data at a specific binning factor.
      Key params: --particles, --binfactor, --nthreads, --nprocesses
      Optional: --parameter (derives box/crop from JSON), --boxsize, --cropsize, --tomogram, --motion, --apex
      If the user asks for a SLURM script instead, use: py2rely-slurm routines extract-subtomo
          Generates extract-subtomo.sh; user submits with: sbatch extract-subtomo.sh

  Step 3c (optional, direct): py2rely routines reconstruct
      Back-project aligned sub-tomograms to produce a 3D map.
      Key params: --particles, --binfactor, --symmetry, --nthreads, --nprocesses
      Optional: --parameter, --boxsize, --cropsize, --tomograms, --motion
      If the user asks for a SLURM script instead, use: py2rely-slurm routines reconstruct
          Generates reconstruct-particle.sh; user submits with: sbatch reconstruct-particle.sh

  Step 3d (optional, direct): py2rely routines refine3d
      Run RELION gold-standard 3D auto-refinement on sub-tomograms.
      Key params: --particles, --reference, --diameter, --nthreads, --nprocesses
      Optional: --parameter, --mask, --tomogram, --motion, --symmetry, --low-pass,
                --sampling-angle (global search, default '7.5 degrees'),
                --local-sampling-angle (local search, default '1.8 degrees'),
                --ref-correct-greyscale, --continue-iter (resume from checkpoint)
      If the user asks for a SLURM script instead, use: py2rely-slurm routines refine3d
          Generates refine3d.sh; user submits with: sbatch refine3d.sh

  Step 3e (optional, direct): py2rely routines mask-create
      Build a soft solvent mask from a reconstructed map. Run this before post-process
      (or refine3d) when a --mask is needed.
      Key params: --map (path to map, e.g. Reconstruct/job001/half1.mrc)
      Optional: --threshold, --extend, --width, --low-pass, --nthreads

  Step 3f (optional, direct): py2rely routines post-process
      Apply FSC-based post-processing to a pair of half-maps.
      Key params: --half-map (path to half1), --mask
      Optional: --low-pass

  Step 4 (optional, direct or --submitit): py2rely pipelines polish
      Runs frame-based polishing. Key params: --parameter, --particles, --mask, --submitit

  Step 5 (direct): py2rely export star2copick
      Writes the final refined picks back to copick. This always ends the STA workflow.
      Key params: --particles, --configs, --sessions, --name, --user-id, --session-id

HOW TO RESPOND
- ALWAYS suggest the command as a copy-pasteable code block. NEVER call run_py2rely_command or run_slabpick_command unless the user says something like "run it", "go ahead and run it", "execute it", or "do it for me".
- Describing what they want ("I'd like to import particles") is NOT permission to run — suggest the command instead.
- Use get_command_help to look up flags before suggesting a command.
- If the user provides all required parameters, go straight to the suggestion without asking follow-up questions.
- For SLURM jobs, show both the script-generation command and the sbatch invocation.
""",
)

# Commands exposed via py2rely entry point
PY2RELY_COMMANDS = [
    # prepare group — fast data import/setup commands
    ("prepare particles", "Import coordinates from a copick project into a RELION star file"),
    ("prepare import-particles", "Import particles from an existing STAR file"),
    ("prepare combine-particles", "Combine multiple particle STAR files into one"),
    ("prepare tilt-series", "Import tilt series from AreTomo output"),
    ("prepare combine-tilt-series", "Combine multiple tilt series STAR files"),
    ("prepare filter-unused-tilts", "Remove tilts not referenced by any particle"),
    ("prepare relion5-parameters", "Generate a sta_parameters.json config file"),
    ("prepare relion5-pipeline", "Initialize a RELION pipeline from a parameters file"),
    ("prepare template", "Create a template from an MRC map"),
    # slab group — 2D class averaging on slab projections
    ("slab class2d", "Run RELION Class2D on slab projections (direct, blocking)"),
    ("slab summary", "Generate a PDF gallery of 2D class averages for inspection"),
    # export group — write results back to copick
    ("export star2copick", "Export a RELION particles star file back into copick projects"),
    # pipelines group — full multi-step STA workflows
    ("pipelines sta", "Run the full STA pipeline (use --submitit for SLURM)"),
    ("pipelines polish", "Run the frame-based polishing pipeline (use --submitit for SLURM)"),
    # routines group — individual RELION job steps
    ("routines extract", "Extract pseudo sub-tomograms from tilt-series data (direct, blocking)"),
    ("routines reconstruct", "Back-project aligned sub-tomograms to produce a 3D map (direct, blocking)"),
    ("routines refine3d", "Run RELION gold-standard 3D auto-refinement on sub-tomograms (direct, blocking)"),
    ("routines class3d", "Run a single RELION Class3D job (direct, blocking)"),
    ("routines mask-create", "Build a soft solvent mask from a reconstructed map (direct, blocking)"),
    ("routines post-process", "Apply FSC-based post-processing to a pair of half-maps (direct, blocking)"),
    ("routines select", "Export particles from selected 2D or 3D classes (-p particles.star -c 1,3,5)"),
]

# Commands exposed via py2rely-slurm entry point — these generate .sh scripts for sbatch
PY2RELY_SLURM_COMMANDS = [
    ("slab slabpick", "Generate a SLURM script running make_minislabs + normalize_stack"),
    ("slab class2d", "Generate a SLURM script running RELION Class2D"),
    ("routines class3d", "Generate a SLURM script running RELION Class3D"),
    ("routines refine3d", "Generate a SLURM script running RELION Refine3D"),
    ("routines reconstruct", "Generate a SLURM script running RELION ReconstructParticle"),
    ("routines extract-subtomo", "Generate a SLURM script running pseudo sub-tomogram extraction"),
]

# Slabpick CLI tools available as standalone commands
SLABPICK_TOOLS = [
    ("make_minislabs", "Extract slab projections from tomograms around picked coordinates"),
    ("normalize_stack", "Normalize an MRC particle stack to mean=0, std=1"),
    ("rln_map_particles", "Map picked particle coordinates into a RELION star file"),
]


# ============================================================================
# Discovery
# ============================================================================


@mcp.tool()
def list_py2rely_commands() -> dict[str, Any]:
    """List all py2rely, py2rely-slurm, and slabpick commands available via this MCP server."""
    return {
        "success": True,
        "py2rely": [{"command": f"py2rely {cmd}", "description": desc} for cmd, desc in PY2RELY_COMMANDS],
        "py2rely_slurm": [
            {"command": f"py2rely-slurm {cmd}", "description": desc} for cmd, desc in PY2RELY_SLURM_COMMANDS
        ],
        "slabpick": [{"command": tool, "description": desc} for tool, desc in SLABPICK_TOOLS],
        "tip": "Call get_command_help with a command path (e.g. 'prepare particles') to see all options.",
    }


@mcp.tool()
def get_command_help(command_path: str, use_slurm_entry: bool = False) -> dict[str, Any]:
    """Get the full --help output for a py2rely command.

    Args:
        command_path: Space-separated command path, e.g. 'prepare particles' or 'slab class2d'.
        use_slurm_entry: If True, use the py2rely-slurm entry point instead of py2rely.
    """
    entry = "py2rely-slurm" if use_slurm_entry else "py2rely"
    cmd = [entry] + command_path.split() + ["--help"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        help_text = result.stdout or result.stderr
        return {"success": True, "command": " ".join(cmd), "help": help_text}
    except FileNotFoundError:
        return {"success": False, "error": f"'{entry}' not found. Is py2rely installed in the active environment?"}
    except Exception as e:
        logger.exception("get_command_help failed")
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_slabpick_tool_help(tool_name: str) -> dict[str, Any]:
    """Get the --help output for a slabpick CLI tool.

    Args:
        tool_name: One of make_minislabs, normalize_stack, rln_map_particles.
    """
    valid = [t for t, _ in SLABPICK_TOOLS]
    if tool_name not in valid:
        return {"success": False, "error": f"Unknown tool '{tool_name}'. Valid tools: {valid}"}
    try:
        result = subprocess.run([tool_name, "--help"], capture_output=True, text=True, timeout=30)
        return {"success": True, "command": f"{tool_name} --help", "help": result.stdout or result.stderr}
    except FileNotFoundError:
        return {"success": False, "error": f"'{tool_name}' not found. Is slabpick installed in the active environment?"}
    except Exception as e:
        logger.exception("get_slabpick_tool_help failed")
        return {"success": False, "error": str(e)}


# ============================================================================
# Execution
# ============================================================================


@mcp.tool()
def run_py2rely_command(args: list[str], working_dir: str | None = None, use_slurm_entry: bool = False) -> dict[str, Any]:
    """Run a py2rely command and return its output.

    Use this for fast commands (prepare, slab auto-class-ranker, routines select).
    For long-running RELION jobs, set use_slurm_entry=True to generate a .sh script
    instead — the user can then submit it with sbatch.

    Args:
        args: Arguments after the entry point, e.g. ['prepare', 'particles', '-c', 'config.json', '-n', 'ribosome'].
        working_dir: Directory to run the command in. Defaults to cwd — do not ask the user unless they specify otherwise.
        use_slurm_entry: If True, use py2rely-slurm (generates a SLURM .sh script, does not block).
    """
    cwd = working_dir or os.getcwd()
    entry = "py2rely-slurm" if use_slurm_entry else "py2rely"
    cmd = [entry] + args
    logger.info("Running: %s (cwd=%s)", " ".join(cmd), cwd)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=600)
        return {
            "success": result.returncode == 0,
            "command": " ".join(cmd),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 600 seconds. Use use_slurm_entry=True for long-running jobs."}
    except FileNotFoundError:
        return {"success": False, "error": f"'{entry}' not found. Is py2rely installed in the active environment?"}
    except Exception as e:
        logger.exception("run_py2rely_command failed")
        return {"success": False, "error": str(e)}


@mcp.tool()
def run_slabpick_command(tool_name: str, args: list[str], working_dir: str | None = None) -> dict[str, Any]:
    """Run a slabpick CLI tool directly.

    Args:
        tool_name: One of make_minislabs, normalize_stack, rln_map_particles.
        args: Arguments to pass to the tool.
        working_dir: Directory to run the command in. Defaults to cwd — do not ask the user unless they specify otherwise.
    """
    cwd = working_dir or os.getcwd()
    valid = [t for t, _ in SLABPICK_TOOLS]
    if tool_name not in valid:
        return {"success": False, "error": f"Unknown tool '{tool_name}'. Valid tools: {valid}"}
    cmd = [tool_name] + args
    logger.info("Running slabpick: %s (cwd=%s)", " ".join(cmd), cwd)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=600)
        return {
            "success": result.returncode == 0,
            "command": " ".join(cmd),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 600 seconds."}
    except FileNotFoundError:
        return {"success": False, "error": f"'{tool_name}' not found. Is slabpick installed in the active environment?"}
    except Exception as e:
        logger.exception("run_slabpick_command failed")
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_class2d_summary_pdf(working_dir: str, job_name: str = "job001") -> dict[str, Any]:
    """Find the class average gallery PDF for a Class2D job and return its path for inspection.

    After Class2D finishes, call this tool to locate the PDF. Read the returned path with
    your file-reading tool to view the class averages and decide which classes to keep.
    If no gallery PDF exists yet, this tool generates one by running `py2rely slab summary`.

    Args:
        working_dir: The RELION project directory.
        job_name: The Class2D job folder name (e.g. 'job001').
    """
    # Gallery is saved alongside the final classes MRC
    class2d_dir = os.path.join(working_dir, "Class2D", job_name)
    if not os.path.isdir(class2d_dir):
        return {"success": False, "error": f"Class2D job directory not found: {class2d_dir}"}

    # Look for an existing gallery PDF
    existing = glob.glob(os.path.join(class2d_dir, "**", "image_gallery.pdf"), recursive=True)
    if existing:
        particles = sorted(glob.glob(os.path.join(class2d_dir, "run_it*_data.star")))
        particles_path = os.path.abspath(particles[-1]) if particles else f"{class2d_dir}/run_it###_data.star"
        return {
            "success": True,
            "pdf_path": os.path.abspath(existing[0]),
            "next_step": (
                f"After reviewing the PDF and deciding which classes to keep, run:\n"
                f"py2rely routines select -p {particles_path} -c <comma-separated class numbers>\n"
                f"Example: py2rely routines select -p {particles_path} -c 1,3,5"
            ),
        }

    # No PDF yet — find the final classes MRC and generate one
    mrcs_files = sorted(glob.glob(os.path.join(class2d_dir, "run_it*_classes.mrcs")))
    if not mrcs_files:
        return {"success": False, "error": f"No classes MRC files found in {class2d_dir}. Has the job finished?"}

    final_mrcs = mrcs_files[-1]
    logger.info("Generating class gallery for %s", final_mrcs)
    result = subprocess.run(
        ["py2rely", "slab", "summary", "--input", final_mrcs],
        capture_output=True, text=True, cwd=working_dir, timeout=120,
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr or result.stdout}

    pdf_path = os.path.join(os.path.dirname(final_mrcs), "image_gallery.pdf")
    if not os.path.exists(pdf_path):
        return {"success": False, "error": f"Gallery generation succeeded but PDF not found at {pdf_path}"}

    particles_candidates = sorted(glob.glob(os.path.join(class2d_dir, "run_it*_data.star")))
    particles_path = os.path.abspath(particles_candidates[-1]) if particles_candidates else f"{class2d_dir}/run_it###_data.star"
    return {
        "success": True,
        "pdf_path": os.path.abspath(pdf_path),
        "next_step": (
            f"After reviewing the PDF and deciding which classes to keep, run:\n"
            f"py2rely routines select -p {particles_path} -c <comma-separated class numbers>\n"
            f"Example: py2rely routines select -p {particles_path} -c 1,3,5"
        ),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
