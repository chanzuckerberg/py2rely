# Welcome to py2rely Documentation

**py2rely** - The Python Pipeline To Rely On for Relion Sub-tomogram Processing

py2rely simplifies and accelerates the execution of RELION-based sub-tomogram averaging (STA) workflows on SLURM-based high-performance computing (HPC) systems. Designed for rapid iteration and evaluation of particle picking strategies, py2rely integrates with existing tilt series alignment from AreTomo and particle coordinate storage from [copick](https://github.com/copick/copick).

## 📚 Documentation

### Getting Started
- [Installation](getting-started/installation.md) - Setup and dependencies
- [Quick Start](getting-started/quick-start.md) - Minimal commands to get started

### User Guides
- [Overview](user-guide/overview.md) - Workflow selection and command groups
- [Importing Data](user-guide/importing-data.md) - Data import from various sources
- [3D Sub-tomogram Averaging](user-guide/3d-subtomogram-averaging.md) - Complete STA pipeline guide
- [2D Slab Classification](user-guide/2d-slab-classification.md) - 2D class averaging workflow

### Reference
- [API Reference](api-reference/overview.md) - Detailed API documentation

## 💫 Key Features

- ⚙️ **Automated job preparation**: One-command setup of RELION STA workflows
- 🔄 **Copick integration**: Seamless import of particle coordinates
- 🧭 **Tilt series-aware**: Direct input from AreTomo processing pipelines
- 🚀 **SLURM-native execution**: Jobs launched and managed on HPC environments
- 🧠 **Validation-ready**: Quickly test particle picking algorithms

## 🎯 Workflows

### 3D Sub-tomogram Averaging
Complete pipeline from particle extraction to high-resolution reconstruction:

- Multi-resolution refinement
- CTF refinement and Bayesian polishing
- Post-processing and resolution estimation

[Learn more →](user-guide/3d-subtomogram-averaging.md)

### 2D Slab Classification
High-throughput 2D class averaging for particle validation:

- Slab extraction from tomograms
- 2D classification with Relion Class2D
- Interactive visualization (Gradio or PyQt5)
- Bootstrap validation

[Learn more →](user-guide/2d-slab-classification.md)

