# Running on HPC with Submitit

This guide explains how to run py2rely pipelines on a SLURM cluster using **Submitit**. Submitit lets py2rely submit and manage Relion jobs directly from your login session without writing `sbatch` scripts by hand.

## Overview

!!! info "Two ways to run on SLURM"
    py2rely supports two modes for HPC:

    - **Submitit (recommended for pipelines)** – Use `--submitit True` with `py2rely pipelines sta`. Jobs are submitted and waited on automatically from a single command. No manual `sbatch` needed.
    - **Shell scripts** – Use the `py2rely-slurm` CLI to generate `sbatch` scripts (e.g. for individual routines or slab workflows), then run `sbatch script.sh` yourself.

    This page focuses on **Submitit** for the STA pipeline and related configuration.

When you run the STA pipeline with Submitit enabled, each Relion step (e.g. Refine3D, Class3D) is launched as a SLURM job via Submitit. The pipeline waits for each job to finish before starting the next, so you can run the full STA workflow from one invocation.

!!! tip "When to use Submitit"
    - You want to run the full **STA pipeline** on the cluster without managing many `sbatch` scripts.
    - Your cluster has SLURM and supports Submitit (Python runs on the login node; jobs run on compute nodes).
    - You prefer a single command with options (GPUs, timeout, partition) over maintaining shell scripts.

!!! warning "Requirements"
    - **SLURM** cluster with a `gpu` partition (or the partition you specify).
    - **Relion** and **Python** available on compute nodes (often via environment modules; see [Environment configuration](#environment-configuration)).
    - **submitit** is included in py2rely’s dependencies; no extra install is needed.

---

## Environment configuration

Before using Submitit, tell py2rely how to load Python and Relion on the compute nodes. These commands are written into the SLURM job script so each job gets the correct environment.

**Set load commands with `py2rely config`**

Run once (or when your cluster environment changes):

```bash
py2rely config
```

You will be prompted for:

- **python_load** – Commands to load your Python environment (e.g. `module load anaconda` or `source /path/to/conda/bin/activate py2rely`). Multi-line is OK; press Enter on an empty line when done. Press Enter with nothing to skip.
- **relion_load** – Commands to load Relion (e.g. `module load relion/5.0` or a short script). Same multi-line and skip behavior.

!!! example "Example: module load"
    If your cluster uses environment modules:

    ```
    python_load:  module load anaconda
    relion_load: module load relion/5.0
    ```

Values are saved under the py2rely package `envs/` directory and reused for all Submitit (and `py2rely-slurm`) jobs until you run `py2rely config` again.

!!! info "Viewing or updating config"
    - **Show current config only:** `py2rely config --show-only`
    - **Update later:** run `py2rely config` again; you can press Enter to keep the current value for a field.

---

## Running the STA pipeline with Submitit

Use the same `py2rely pipelines sta` command as for local runs, and turn on Submitit with `--submitit True`. Add optional SLURM options as needed.

### Basic example

```bash
py2rely pipelines sta \
    --parameter sta_parameters.json \
    --reference-template reference.mrc \
    --submitit True
```

This runs the full STA pipeline on the cluster: each step is submitted via Submitit, and the pipeline waits for completion before continuing.

### Example with SLURM options

```bash
py2rely pipelines sta \
    --parameter sta_parameters.json \
    --reference-template reference.mrc \
    --submitit True \
    --num-gpus 4 \
    --gpu-constraint "a100|h100" \
    --cpu-constraint 8,32 \
    --timeout 72
```

??? note "📋 Submitit-related options for `py2rely pipelines sta`"
    | Option | Short | Description | Default |
    |--------|-------|-------------|---------|
    | `--submitit` | `-s` | Use Submitit to submit jobs to SLURM | `False` |
    | `--num-gpus` | `-ng` | Number of GPUs per GPU job (must be even) | `4` |
    | `--gpu-constraint` | `-gc` | GPU type(s), e.g. `a100` or `a100\|h100` | none |
    | `--cpu-constraint` | `-cc` | CPUs and memory: `"ncpus,mem_gb_per_cpu"` | `4,16` |
    | `--timeout` | `-t` | Time limit for each pipeline step (in hours) | `48` |

!!! tip "Multiple GPU types"
    Use `--gpu-constraint "a100|h100"` to allow either A100 or H100. The pipeline checks your partition’s Slurm features and uses only valid options; invalid ones are dropped with a warning.

!!! warning "Even number of GPUs"
    `--num-gpus` must be an even number (e.g. 2, 4, 8). The pipeline will report an error otherwise.

!!! example "Generate a Slurm Submission Script with py2rely"

    You can easily generate a shell script that can be submitted to SLURM with the `py2rely prepare relion5-pipeline` command.


---

!!! success "Next steps"
    - [Installation](../getting-started/installation.md) – Prerequisites and optional dependencies.
    - [Quick Start](../getting-started/quick-start.md) – End-to-end workflow including optional Submitit usage.
    - [3D Sub-tomogram Averaging](3d-subtomogram-averaging.md) – Full STA pipeline options (reference, de novo, Class3D).
