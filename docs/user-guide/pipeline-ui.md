# Pipeline UI

`py2rely ui` is a browser-based pipeline visualizer and job monitor for RELION projects.
It shows the full job DAG, live status, logs, output files, and 3D density maps — all in one place.

---

## Installation

The UI requires a small set of additional dependencies that are not installed by default.
Install them with the `relionui` extra:

=== "pip"

    ```bash
    pip install "py2rely[relionui]"
    ```

=== "uv"

    ```bash
    uv add "py2rely[relionui]"
    ```

This adds **FastAPI**, **uvicorn**, and **watchdog** to your environment.
No Node.js or npm is required — the web interface is pre-built and shipped with the package.

---

## Launching

Run `py2rely ui` from inside your RELION project directory (the folder containing `default_pipeline.star`):

```bash
cd /path/to/my-relion-project
py2rely ui
```

The server starts on port **3000** and opens your browser automatically:

```
[relion-ui] Running at http://127.0.0.1:3000
```

!!! tip "No `default_pipeline.star` found?"
    If py2rely cannot find `default_pipeline.star` in the current directory it will exit with
    a helpful message. Make sure you `cd` into the RELION project root before running the command.

---

## Remote / HPC Usage

When running on an HPC cluster, bind to localhost (the default) and forward the port over SSH
from your local machine:

```bash
# On the HPC node — start the server (no browser needed)
cd /path/to/my-relion-project
py2rely ui --no-browser

# On your laptop — open an SSH tunnel
ssh -L 3000:localhost:3000 your-hpc-host
```

Then open **http://localhost:3000** in your local browser.

!!! info "Exposing on all interfaces"
    If you need the UI accessible on the cluster network without a tunnel, pass `--host 0.0.0.0`.
    Only do this on a trusted network.

    ```bash
    py2rely ui --host 0.0.0.0 --no-browser
    ```

---

## Options

```
py2rely ui [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--port` | `3000` | Port to serve on |
| `--host` | `127.0.0.1` | Host to bind to (`0.0.0.0` to expose on all interfaces) |
| `--no-browser` | off | Suppress the automatic browser launch |
| `--poll-interval` | `5` | Seconds between status polls on filesystems where watchdog events are unavailable (e.g. NFS, Lustre) |

---

## Interface Overview

The UI is divided into three main areas:

**Sidebar (left)**
: Scrollable job list with status dots and type color labels.
  Jobs are grouped by binning factor — a `Binning X×` divider appears whenever an
  Extract or Reconstruct job introduces a new binning stage.
  Use the filter box at the top to search by job ID or type.

**DAG canvas (center-top)**
: A directed acyclic graph of the full pipeline.
  Pan by clicking and dragging; zoom with the scroll wheel or the `+` / `−` buttons.
  Edges into and out of the selected job are highlighted.
  Node colors reflect job type; a left-edge accent tracks the current selection.

**Detail panel (center-bottom)**
: Click any job node or sidebar entry to open its detail panel.
  The split between canvas and panel is draggable.

  | Tab | Contents |
  |-----|----------|
  | **Params** | All job parameters from `job.star` |
  | **Log** | Live `run.out` log; auto-scrolls while the job is running |
  | **Results** | Output files; Class3D/Refine3D show class map thumbnails |
  | **3D Map** | Interactive NGL isocontour viewer for density maps (`.mrc`) |

### 3D Map viewer

When a job produces a density map the **3D Map** tab becomes active.
The contour slider uses absolute density values; the current level is also shown
in σ units (multiples of the map RMS) as a reference.

Controls available:

- **Contour** — drag slider or type a value
- **Color** — choose from preset color swatches
- **View** — switch between surface (`3D`) and orthogonal slice views (`XY`, `XZ`, `YZ`)
- **Invert** — flip the isosurface sign (useful for negative-stain data)

---

## Live Updates

The server watches `default_pipeline.star` and sentinel files for changes using
**watchdog** (inotify / FSEvents). On networked filesystems that do not deliver
filesystem events (NFS, Lustre), it falls back to polling at the interval set by
`--poll-interval`.

When a job finishes or a new job starts the sidebar status dots, DAG node colors,
and open log views all update automatically over WebSocket — no page refresh needed.
