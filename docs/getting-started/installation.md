# Installation

This guide will help you install py2rely and all its dependencies.

## Prerequisites

Before installing py2rely, ensure you have:

- **Python 3.9+** (Python 3.10 recommended)
- **Relion 5.0** or later installed and accessible in your PATH
- **Conda** or **pip** for package management
- **SLURM (Optional)** (for HPC cluster usage)

!!! question "What version of Relion do I need?"
    py2rely requires **Relion 5.0** or later. Earlier versions (Relion 4.x) are not supported due to differences in the STAR file format and job options.

!!! warning "SLURM Required for HPC"
    `py2rely` supports submitting processing jobs through SLURM on HPC clusters.
    All commands can also be run **locally** via the CLI or Python API without SLURM.

!!! info "Submitit for pipeline execution on SLURM"
    On SLURM clusters you can run the full STA pipeline with **Submitit**: use `py2rely pipelines sta --submitit True` so each Relion step is submitted and managed automatically. Before first use, run `py2rely config` to set **python_load** and **relion_load** (e.g. `module load relion/5.0`) so compute nodes get the correct environment. See [Running on HPC with Submitit](../user-guide/running-on-hpc-with-submitit.md) for details and examples.

## Basic Installation

### Step 1: Create a Conda Environment

We recommend installing py2rely in a separate environment. This can be done with conda, venv, or any other virtual environment.

```bash
conda create -n py2rely python=3.10
conda activate py2rely
```

### Step 2: Install py2rely

Navigate to the py2rely directory and install:

```bash
cd py2rely
pip install -e .
```

## Optional Dependencies

### For 2D Slab Classification Workflow

The 2D slab classification workflow requires additional dependencies for visualization. Choose one of the following options:

=== "Gradio (Web-based GUI) 🌐"

    For the web-based interface to visualize and extract class averages:
    
    ```bash
    pip install gradio
    ```
    
    Or install with the web extra:
    
    ```bash
    pip install -e ".[web]"
    ```
    
    !!! tip "Best for Remote Servers"
        - No X11 forwarding needed
        - Easy to share via URL
        - Works on any machine with a browser
        - Accessible from multiple devices

=== "PyQt5 (Desktop GUI) 🖥️"

    For the desktop GUI application:
    
    ```bash
    pip install PyQt5 pyqtgraph
    ```
    
    Or install with the gui extra:
    
    ```bash
    pip install -e ".[gui]"
    ```
    
    !!! tip "Best for Local Workstations"
        - Native desktop experience
        - Better performance for large datasets
        - More responsive UI
        - Requires X11 on remote servers

!!! question "Do I need both?"
    No! You only need **one** visualization option. Choose based on your environment:
    
    - **Remote server/cluster**: Use Gradio
    - **Local workstation**: Use PyQt5
    - **Not using 2D slab workflow**: Neither is required

## Verify Installation

Test your installation:

```bash
py2rely
```

You should see the following output:

```ansi
py2rely - The Python Execution of Sub-Tomogram Refinement

╭─ Options ───────────────────────────────────────────╮
│ --help  -h  Show this message and exit.              │
╰─────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────╮
│ export     Export Coordinates from Relion5           │
│ pipelines  Run Pipeline Jobs                         │
│ prepare    Import data from aretomo and copick       │
│ routines   Run individual jobs                       │
│ slab       Run 2D slab classification                │
│ utils      Convert between formats                   │
╰─────────────────────────────────────────────────────╯
```


## Next Steps

Once installation is complete, proceed to the [Quick Start Guide](quick-start.md) to run your first workflow.

