# relionui — Browser-Based Pipeline Visualizer

A browser-based monitor and visualizer for RELION sub-tomogram averaging projects.
Run it from any RELION project directory and inspect your pipeline in real time.

---

## Installation

relionui is an optional extra within `py2rely`. Install its Python dependencies with:

```bash
pip install -e ".[relionui]"
# or with uv
uv add py2rely[relionui]
```

**No Node.js required.** The pre-built frontend (`frontend/dist/`) is committed to the
repository and served directly by the Python backend, so a plain `pip install` is all
that end users need.

---

## Usage

Navigate to your RELION project directory and run:

```bash
cd /path/to/your/relion/project
py2rely ui
```

This starts a local web server (default: `http://127.0.0.1:3000`) and opens the browser
automatically.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `3000` | Port to serve on |
| `--host` | `127.0.0.1` | Host to bind. Use `0.0.0.0` to expose on all network interfaces (e.g. for SSH tunnelling to an HPC node) |
| `--no-browser` | off | Do not auto-open the browser |
| `--poll-interval` | `5` | Seconds between pipeline polls when filesystem watching is unavailable |

Example — serve on a remote node and tunnel to your laptop:

```bash
# On the HPC node
py2rely ui --host 0.0.0.0 --port 3000 --no-browser

# On your laptop
ssh -L 3000:localhost:3000 user@hpc-node
# Then open http://localhost:3000
```

---

## What you can see

| Tab | Available for |
|-----|---------------|
| **Params** | All job types — parameters used to run the job |
| **Analysis** | Refine3D, Class3D, PostProcess, CtfFind, Polish, CtfRefine — scientific plots and summary statistics |
| **Log** | All job types — live-streaming run log |
| **Outputs** | All job types — file browser for job outputs |
| **3D Map** | Refine3D, Class3D, PostProcess, Reconstruct, MaskCreate — interactive isosurface viewer |
| **2D Slices** | Same as above — orthogonal slice viewer with brightness/contrast controls |

The pipeline DAG in the left sidebar updates automatically as jobs start and finish.

---

## Developer workflow

If you are modifying the React frontend you need Node.js (≥18) and must rebuild the
bundle after any JS change:

```bash
cd py2rely/relionui/frontend
npm install          # first time only
npm run dev          # hot-reload dev server at http://localhost:5173
                     # (requires the Python backend running on port 3000)

npm run build        # rebuild dist/ for production use
```

The backend (running from the RELION project dir) should be started separately during
development:

```bash
cd /path/to/relion/project
PYTHONPATH=/path/to/py2rely python3 -m uvicorn py2rely.relionui.server:app \
    --port 3000 --log-level warning
```

After `npm run build`, commit the updated `frontend/dist/` so that the new bundle is
shipped to other users without requiring them to install Node.js.

> **Why PYTHONPATH?** If you have py2rely installed in your environment (via `pip install
> -e .`), Python will use that installed copy's `dist/`. Setting `PYTHONPATH` forces it
> to use your local source tree — including any freshly built frontend — instead.
