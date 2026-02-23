# User Guide Overview

Welcome to the py2rely user guide! This section provides comprehensive documentation for all py2rely workflows and features.

## Workflows

py2rely is designed around a two-stage strategy:

1. **Screen fast** with 2D classification to validate and isolate high-quality particles
2. **Refine thoroughly** with 3D sub-tomogram averaging for high-resolution structures

You can use either workflow independently, but combining them gives the best results.

---

🧪 [2D Slab Classification](2d-slab-classification.md) - Fast Particle Screening

Rapidly validate particle picks and isolate coordinates for your protein of interest:

- Extract thin slabs from tomograms (avoids missing wedge artifacts)
- Run 2D classification in minutes to hours (vs. days for 3D)
- Visually inspect class averages to identify your target protein
- Select high-confidence particles for downstream processing
- Export cleaned coordinates back to Copick or STAR files

**Typical use cases:**

- ✅ Validate a new picking algorithm or template
- ✅ Separate your protein from contaminants
- ✅ Identify different conformational states
- ✅ Quality control before investing in 3D refinement

---

🔬 [3D Sub-tomogram Averaging](3d-subtomogram-averaging.md) - High-Resolution 3D Refinement

Process validated particles through the complete sub-tomogram averaging pipeline:

- Initial model generation (de novo, reference-based, or reconstruction)
- CTF refinement and Bayesian polishing
- Post-processing and resolution estimation

**Typical use cases:**

- ✅ Determine high-resolution structures
- ✅ Generate publication-quality maps
- ✅ Refine particle orientations and CTF parameters

---

🖥️ [Running on HPC with Submitit](running-on-hpc-with-submitit.md) - Cluster execution with Submitit

Run the STA pipeline on a SLURM cluster with `--submitit True` so each Relion step is submitted and waited on automatically. Configure Python and Relion load commands with `py2rely config`; optional GPU/CPU and timeout options are documented in the guide.

---

### Recommended Workflow

**For new or uncertain particle picks:**

Start with 2D classification to validate/clean particles, then run 3D STA on selected high-quality particles.

**For pre-validated particles:**

Go directly to 3D sub-tomogram averaging.

---

## Next Steps

1. **Import Data**: See [Importing Data](importing-data.md) for data preparation
2. **Screening with 2D Classification**: Check out [2D Slab Classification](2d-slab-classification.md)
3. **3D STA**: Read the [3D Sub-tomogram Averaging](3d-subtomogram-averaging.md) guide

**New to py2rely?** Start with the [Quick Start Guide](../getting-started/quick-start.md) for hands-on examples.