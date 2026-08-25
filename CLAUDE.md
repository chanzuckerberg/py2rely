# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

py2rely is a Python CLI that automates RELION-based sub-tomogram averaging (STA) workflows on SLURM HPC clusters. It integrates particle coordinates from [copick](https://github.com/copick/copick), tilt-series alignment from AreTomo, and drives RELION jobs via the `ccpem-pipeliner` package. Two console entry points are installed:

- `py2rely` — runs jobs directly (blocking, in-process)
- `py2rely-slurm` — generates `sbatch`-ready `.sh` scripts instead of running jobs directly

## Commands

Install (editable, with extras as needed):
```bash
pip install -e .                 # core
pip install -e ".[dashboard]"    # + FastAPI/uvicorn/watchdog for `py2rely ui`
pip install -e ".[web]"          # + gradio/pytz
pip install -e ".[gui]"          # + PyQt5/pyqtgraph
```

Lint / format / type-check (configured in `pyproject.toml`, not run in CI — run manually before committing):
```bash
ruff check .
black .
mypy py2rely
```

There is no automated test suite in this repo.

Build docs (MkDocs Material, source in `docs/`):
```bash
mkdocs build
mkdocs serve
```

Dashboard frontend (React + Vite, in `py2rely/dashboard/frontend/`), served by the FastAPI backend once built to `dist/`:
```bash
cd py2rely/dashboard/frontend
npm install
npm run dev      # local dev server
npm run build    # outputs to dist/, bundled into the wheel (see pyproject.toml [tool.hatch.build] include)
```

Explore the CLI itself for available commands and options — every group/command has `--help`:
```bash
py2rely --help
py2rely <group> <command> --help   # e.g. py2rely routines extract --help
py2rely-slurm --help
```

## Architecture

### CLI composition

`py2rely/main.py` assembles two top-level `rich_click` groups by importing each subsystem's `cli.py` and calling `.add_command(...)`:
- `routines` (the `py2rely` entry point) aggregates `prepare`, `routines` (subroutines), `export`, `converters`, `pipelines`, `slab`, `config`, `ui`/`create_mask`, `mcp`.
- `slurm_routines` (the `py2rely-slurm` entry point) aggregates only the SLURM-script-generating variants: `routines_slurm` and `slab_slurm`.

`py2rely/groups.py` is imported solely for its side effects: it configures `rich_click.COMMAND_GROUPS` / `OPTION_GROUPS` dictionaries that control how `--help` output is organized and grouped for specific commands (keyed by full command path, e.g. `"py2rely prepare particles"`). When adding new CLI options, add matching entries here or they'll fall outside the grouped sections in `--help`.

### Direct vs. SLURM dual-command pattern

Most RELION-job functionality is implemented twice, following the pattern in `routines/extract_subtomo.py`:
1. A `run_<thing>(...)` function holding the actual logic (builds a `Relion5Pipeline`/pipeliner job, sets parameters, executes it). This is reusable both by its own CLI command and by higher-level pipeline code (e.g. `pipelines/sta.py` calls into the same job-building utilities directly rather than shelling out).
2. A plain `@cli.command` wrapping `run_<thing>` for direct/blocking execution (the `py2rely` entry point).
3. A `*_slurm` `@cli.command` (the `py2rely-slurm` entry point) that does **not** execute anything — it calls `submit_slurm.build_command()` to construct the equivalent `py2rely ...` CLI invocation as a string, then `submit_slurm.create_shellsubmit()` to write it into a `.sh` file with the right `#SBATCH` directives (GPU/CPU partition, module loads). The user submits it themselves with `sbatch`.

`routines/submit_slurm.py` also has GPU/node-sizing helpers (`check_gpus`, `get_gpu_node_range`, `get_cpus_per_node`) that shell out to `sinfo` to validate `--gpu-constraint` values against real cluster feature flags and compute node counts for a requested GPU count.

### Module map (`py2rely/`)

- `prepare/` — fast, non-blocking data-import/setup commands: importing copick coordinates and AreTomo tilt series into RELION STAR files, generating the `sta_parameters.json` config, initializing a RELION pipeline directory.
- `routines/` — individual RELION job steps runnable standalone: `extract_subtomo`, `reconstruct`, `refine3d`, `class3d`, `post_process`, `mask_create`, `select` (export particles from chosen 2D/3D classes), plus shared helpers in `helper.py`.
- `pipelines/` — multi-step orchestrations built on top of `routines`/`utils.relion5_tools`: `sta.py` (`average` — the full iterative STA loop: pseudo-subtomo extraction → initial model → refine/reconstruct/mask/post-process loop across binning levels → optional bin1 high-resolution refinement + polishing), `bin1.py` (high-resolution refinement stage), `polishing.py`, `classify.py` (3D classification helper used mid-pipeline).
- `slabs/` — the 2D "slab" particle-filtering workflow (extract 2D slab projections from tomograms, run Class2D, visualize class galleries, rank/select classes); `slabs/slurm.py` holds its SLURM-script variants; `slabs/visualize/` has PDF gallery generation and both a PyQt GUI and a web GUI for browsing classes.
- `dashboard/` — FastAPI + React/Vite web UI (`py2rely ui`) for monitoring a RELION project's pipeline graph and job status live (via `watchdog`), plus an interactive MaskCreate tool (`py2rely mask-create`) for tuning solvent masks in-browser.
- `mcp/` — a FastMCP server (`py2rely mcp`) exposing the CLI as MCP tools so Claude Code/Desktop can drive STA workflows conversationally. See "MCP server" below.
- `utils/` — shared internals: `relion5_tools.py` (`Relion5Pipeline`, the central wrapper around `pipeliner.api.manage_project.PipelinerProject` that initializes/runs each RELION job type and supports both direct and `submitit`-based SLURM execution), `common.py` (shared `click.option` decorators reused across commands, e.g. `add_sta_options`, `add_submitit_options`), `relion3_tools.py`/`relion4_tools.py` (older RELION version support), `converters.py`, `map.py`, `progress.py`, `custom_jobs.py`, `sta_tools.py`.
- `config.py` — manages `py2rely/envs/env_config.json`, storing the `python_load`/`relion_load` shell snippets (e.g. `module load ...`) that get injected into every generated SLURM script. Prompted for interactively the first time a SLURM script is generated if missing; editable anytime via `py2rely config add/import/print`.

### Relion5Pipeline

`utils/relion5_tools.Relion5Pipeline` is the shared abstraction nearly everything routes through: it wraps a `PipelinerProject`, exposes one `initialize_<job>()`/`run_<job>()` pair per RELION job type (pseudo-subtomo extraction, auto-refine, tomo Class3D, reconstruct-particle, mask-create, post-process, initial-model), tracks per-binning-level state (`utils.binning`, `utils.binningList`), and can execute jobs either directly or via `submitit` when constructed with `use_submitit=True`. Both single-step `routines/*` commands and the full `pipelines/sta.py` loop build on this same class — changes to job parameter wiring here affect all of them.

### MCP server (`py2rely mcp`)

`mcp/server.py` defines a FastMCP server whose `instructions` field encodes two supported end-to-end workflows for an LLM client to follow:
- **Workflow A** (2D slab filtering): extract slabs → Class2D → inspect the class gallery PDF (`get_class2d_summary_pdf`) → `routines select` on chosen classes → map back to copick.
- **Workflow B** (3D STA): `prepare particles`/`tilt-series` → `pipelines sta` → optional `routines class3d` → `export star2copick`.

Class-selection steps are an explicit human-in-the-loop boundary — the instructions direct the assistant to *suggest* commands rather than execute them by default, and never to choose classes on the user's behalf. `docs/user-guide/claude-code-mcp.md` documents this in full with example conversations; keep it in sync with `PY2RELY_COMMANDS`/`PY2RELY_SLURM_COMMANDS`/`SLABPICK_TOOLS` in `server.py` if commands change.
