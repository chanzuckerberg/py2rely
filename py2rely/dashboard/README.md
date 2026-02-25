# dashboard — Browser-Based Pipeline Visualizer

A browser-based monitor and visualizer for RELION sub-tomogram averaging projects.
Run it from any RELION project directory and inspect your pipeline in real time.

---

## Installation

dashboard is an optional extra within `py2rely`. Install its Python dependencies with:

```bash
pip install -e ".[dashboard]"
# or with uv
uv add py2rely[dashboard]
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

![dashboard](../../docs/assets/dashboard.png)

The dashboard provides a scrollable list of all ran jobs alongside a visualisation of the pipeline node structure. Clicking any job opens a detail panel with job-type-specific analysis tabs — showing relevant plots such as FSC curves and convergence statistics — as well as the ability to render output density maps interactively in 3D.

---

## Developer workflow

If you are modifying the React frontend you need Node.js (≥18) and must rebuild the
bundle after any JS change:

```bash
cd py2rely/dashboard/frontend
npm install          # first time only
npm run dev          # hot-reload dev server at http://localhost:5173
                     # (requires the Python backend running on port 3000)

npm run build        # rebuild dist/ for production use
```

The backend (running from the RELION project dir) should be started separately during
development:

```bash
cd /path/to/relion/project
PYTHONPATH=/path/to/py2rely python3 -m uvicorn py2rely.dashboard.server:app \
    --port 3000 --log-level warning
```

After `npm run build`, commit the updated `frontend/dist/` so that the new bundle is
shipped to other users without requiring them to install Node.js.

> **Why PYTHONPATH?** If you have py2rely installed in your environment (via `pip install
> -e .`), Python will use that installed copy's `dist/`. Setting `PYTHONPATH` forces it
> to use your local source tree — including any freshly built frontend — instead.

---

## Architecture

```
py2rely/dashboard/
├── cli.py                          # `py2rely ui` entry point — options, lazy-loads server
├── server.py                       # FastAPI app — REST + WebSocket, serves frontend dist/
├── parser.py                       # Parses RELION project (jobs, edges, params, star files)
├── models.py                       # Pydantic response models (JobNode, Pipeline, etc.)
├── watcher.py                      # Watchdog handler — pushes pipeline updates over WebSocket
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── dist/                       # Pre-built bundle (committed — no Node.js required)
    └── src/
        ├── main.jsx                # React entry point
        ├── App.jsx                 # Root component — layout, WebSocket subscription
        ├── theme.js                # Colour tokens and STATUS_COLOR / TYPE_COLOR maps
        ├── api/
        │   ├── http.js             # Fetch wrappers for REST endpoints
        │   └── socket.js           # WebSocket client
        └── components/
            ├── Topbar.jsx          # Header bar
            ├── Sidebar.jsx         # Job list with status badges
            ├── DAGCanvas.jsx       # SVG pipeline DAG — pan/zoom, node selection
            ├── DetailPanel.jsx     # Tabbed detail view — Params / Analysis / Log / Outputs / 3D / 2D
            ├── LogViewer.jsx       # Live-streaming job log
            ├── ResultsViewer.jsx   # Output file browser
            ├── Volume3DViewer.jsx  # Interactive 3D isosurface viewer (NGL)
            ├── Slice2DViewer.jsx   # Orthogonal 2D slice viewer
            ├── AnalysisPanel.jsx   # Dispatches to job-type-specific analysis component
            ├── Refine3DAnalysis.jsx    # Resolution convergence + gold-standard FSC
            ├── Class3DAnalysis.jsx     # Class distribution, per-class FSC, angular distribution
            ├── PostProcessAnalysis.jsx # Post-processing FSC (corrected / unmasked / phase-rand)
            ├── CtfFindAnalysis.jsx     # CTF defocus and fit diagnostics
            ├── CtfRefineAnalysis.jsx   # Per-tilt CTF refinement plots
            └── PolishAnalysis.jsx      # Particle polishing diagnostics
```
